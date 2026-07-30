from __future__ import annotations

import math

from .config import ScoringProfile
from .exceptions import EvaluatorContractError, ScoringConfigurationError
from .registry import EvaluatorRegistry
from .types import CRITICAL_GROUP, EvaluationStatus, EvaluatorResult


def validate_profile(profile: ScoringProfile, registry: EvaluatorRegistry) -> None:
    if not isinstance(profile, ScoringProfile):
        raise ScoringConfigurationError("profile must be a ScoringProfile instance.")
    if not profile.groups:
        raise ScoringConfigurationError("At least one scoring group is required.")

    group_keys: set[str] = set()
    enabled_groups: set[str] = set()
    group_orders: dict[str, int] = {}
    for group in profile.groups:
        key = str(group.key).strip()
        if not key:
            raise ScoringConfigurationError("Scoring group keys cannot be empty.")
        if key in group_keys:
            raise ScoringConfigurationError(
                f"Scoring group '{key}' is configured more than once."
            )
        group_keys.add(key)
        group_orders[key] = group.order
        _positive_weight(group.weight, f"Scoring group '{key}'")
        if group.enabled:
            enabled_groups.add(key)

    if str(CRITICAL_GROUP) not in enabled_groups:
        raise ScoringConfigurationError(
            "Exactly one enabled 'critical' gate group is required."
        )
    critical_order = group_orders[str(CRITICAL_GROUP)]
    if any(
        group.enabled
        and str(group.key) != str(CRITICAL_GROUP)
        and group.order < critical_order
        for group in profile.groups
    ):
        raise ScoringConfigurationError(
            "The critical group must execute before non-critical groups."
        )

    evaluator_keys: set[str] = set()
    enabled_by_group = {key: 0 for key in enabled_groups}
    for rule in profile.evaluators:
        key = str(rule.key).strip()
        if not key:
            raise ScoringConfigurationError("Evaluator keys cannot be empty.")
        if key in evaluator_keys:
            raise ScoringConfigurationError(
                f"Evaluator '{key}' is configured more than once."
            )
        evaluator_keys.add(key)
        _positive_weight(rule.weight, f"Evaluator '{key}'")

        group_key = str(rule.group_key)
        if group_key not in group_keys:
            raise ScoringConfigurationError(
                f"Evaluator '{key}' references unknown group '{group_key}'."
            )
        effectively_enabled = rule.enabled and group_key in enabled_groups
        if effectively_enabled:
            if not registry.contains(rule.key):
                raise ScoringConfigurationError(
                    f"Enabled evaluator '{key}' is not registered."
                )
            evaluator = registry.get(rule.key)
            if not isinstance(rule.settings, evaluator.settings_type):
                raise ScoringConfigurationError(
                    f"Evaluator '{key}' requires {evaluator.settings_type.__name__} settings."
                )
            enabled_by_group[group_key] += 1

        if group_key == str(CRITICAL_GROUP):
            if rule.minimum_score is None:
                raise ScoringConfigurationError(
                    f"Critical evaluator '{key}' requires minimum_score."
                )
            _score_value(
                rule.minimum_score, f"threshold for '{key}'", ScoringConfigurationError
            )
        elif rule.minimum_score is not None:
            raise ScoringConfigurationError(
                f"Non-critical evaluator '{key}' cannot define minimum_score."
            )

    empty_groups = [key for key, count in enabled_by_group.items() if count == 0]
    if empty_groups:
        raise ScoringConfigurationError(
            "Enabled scoring groups require at least one enabled evaluator: "
            + ", ".join(sorted(empty_groups))
        )


def validate_evaluator_result(expected_key: str, result: object) -> EvaluatorResult:
    if not isinstance(result, EvaluatorResult):
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' must return EvaluatorResult."
        )
    if str(result.evaluator_key) != expected_key:
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' returned a result for '{result.evaluator_key}'."
        )
    if not isinstance(result.status, EvaluationStatus):
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' returned an invalid evaluation status."
        )
    if result.status is EvaluationStatus.COMPLETED:
        if result.score is None:
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' completed without a score."
            )
        _score_value(
            result.score, f"score from '{expected_key}'", EvaluatorContractError
        )
    elif result.score is not None:
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' returned a score with status '{result.status.value}'."
        )

    metrics = list(result.metrics)
    for finding in result.findings:
        if not finding.code.strip() or not finding.message.strip():
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' returned an invalid finding."
            )
        metrics.extend(finding.metrics)
    for metric in metrics:
        if not metric.name.strip():
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' returned a metric with an empty name."
            )
        try:
            finite = not isinstance(metric.value, bool) and math.isfinite(
                float(metric.value)
            )
        except (TypeError, ValueError):
            finite = False
        if not finite:
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' returned non-finite metric '{metric.name}'."
            )
    return result


def _positive_weight(value: float, label: str) -> None:
    try:
        valid = (
            not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) > 0
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ScoringConfigurationError(f"{label} requires a finite positive weight.")


def _score_value(value: float, label: str, error_type: type[Exception]) -> None:
    try:
        numeric = float(value)
        valid = (
            not isinstance(value, bool)
            and math.isfinite(numeric)
            and 0.0 <= numeric <= 100.0
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise error_type(f"The {label} must be finite and between 0 and 100.")
