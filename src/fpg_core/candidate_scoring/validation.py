from __future__ import annotations

import math

from ..domain import ExecutionMode
from .config import EvaluatorRule, ScoringConfig
from .exceptions import (
    EvaluatorContractError,
    ScoringConfigurationError,
    ScoringInputError,
)
from .registry import EvaluatorRegistry
from .types import (
    MAX_EVALUATOR_SCORE,
    MIN_EVALUATOR_SCORE,
    CandidateScoringInput,
    EvaluationStatus,
    EvaluatorCategory,
    EvaluatorResult,
)


def validate_scoring_input(scoring_input: CandidateScoringInput) -> None:
    """Validate only framework-level structural requirements.

    Domain-specific checks belong in the project's context factory or in a
    dedicated validator supplied beside this framework.
    """

    if scoring_input.specification is None:
        raise ScoringInputError("Scoring specification cannot be None.")
    if scoring_input.candidate is None:
        raise ScoringInputError("Scoring candidate cannot be None.")


def validate_scoring_config(
    config: ScoringConfig,
    registry: EvaluatorRegistry,
) -> None:
    seen_keys: set[str] = set()
    enabled_quality_weight = 0.0

    if not config.evaluator_rules:
        raise ScoringConfigurationError("At least one evaluator rule is required.")

    for rule in config.evaluator_rules:
        _validate_rule(rule)

        key_value = str(rule.key)
        if key_value in seen_keys:
            raise ScoringConfigurationError(
                f"Evaluator rule '{rule.key}' is configured more than once."
            )
        seen_keys.add(key_value)

        if rule.enabled and not registry.contains(rule.key):
            raise ScoringConfigurationError(
                f"Enabled evaluator '{rule.key}' is not registered."
            )

        if rule.enabled and rule.category is EvaluatorCategory.QUALITY:
            enabled_quality_weight += rule.weight

    if enabled_quality_weight <= 0:
        raise ScoringConfigurationError(
            "Enabled quality evaluators must have a positive total weight."
        )


def _validate_rule(rule: EvaluatorRule) -> None:
    if not str(rule.key).strip():
        raise ScoringConfigurationError("Evaluator key cannot be empty.")

    if not math.isfinite(rule.weight) or rule.weight < 0:
        raise ScoringConfigurationError(
            f"Evaluator '{rule.key}' has an invalid weight: {rule.weight}."
        )

    if rule.category is EvaluatorCategory.CRITICAL:
        if rule.minimum_score is None:
            raise ScoringConfigurationError(
                f"Critical evaluator '{rule.key}' requires minimum_score."
            )
        _validate_score_value(rule.minimum_score, f"threshold for '{rule.key}'")

    if rule.category is EvaluatorCategory.QUALITY and rule.weight <= 0:
        raise ScoringConfigurationError(
            f"Quality evaluator '{rule.key}' requires a positive weight."
        )


def validate_evaluator_result(
    expected_key: str,
    result: EvaluatorResult,
    *,
    mode: ExecutionMode | None = None,
) -> None:
    if str(result.evaluator_key) != expected_key:
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' returned result for "
            f"'{result.evaluator_key}'."
        )

    if mode is ExecutionMode.PRODUCTION:
        if result.metrics:
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' returned DEBUG metrics in PRODUCTION."
            )
        if result.details is not None:
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' returned DEBUG details in PRODUCTION."
            )

    if result.status is EvaluationStatus.COMPLETED:
        if result.score is None:
            raise EvaluatorContractError(
                f"Evaluator '{expected_key}' completed without a score."
            )
        _validate_score_value(result.score, f"score from '{expected_key}'")
        return

    if result.score is not None:
        raise EvaluatorContractError(
            f"Evaluator '{expected_key}' returned a score while status was "
            f"'{result.status.value}'."
        )


def _validate_score_value(value: float, label: str) -> None:
    if not math.isfinite(value):
        raise EvaluatorContractError(f"The {label} must be finite.")
    if not MIN_EVALUATOR_SCORE <= value <= MAX_EVALUATOR_SCORE:
        raise EvaluatorContractError(
            f"The {label} must be between {MIN_EVALUATOR_SCORE} and "
            f"{MAX_EVALUATOR_SCORE}; received {value}."
        )
