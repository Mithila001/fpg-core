from __future__ import annotations

from dataclasses import replace

from ..domain import ExecutionMode, FloorPlan, FloorPlanGenerationSpec
from .config import EvaluatorRule, FloorPlanScoringConfig, ScoringGroupRule
from .context import ScoringContext, ScoringContextFactory
from .contracts import FloorPlanScoringDetails
from .exceptions import (
    EvaluatorContractError,
    EvaluatorExecutionError,
    FloorPlanScoringError,
)
from .registry import EvaluatorRegistry
from .types import (
    CRITICAL_GROUP,
    EvaluationStatus,
    EvaluatorExecutionResult,
    FindingSeverity,
    FloorPlanScoringResult,
    GroupStatus,
    ScoreFinding,
    ScoreMetric,
    ScoringGroupResult,
)
from .validation import validate_config, validate_evaluator_result


class FloorPlanScoreManager:
    def __init__(
        self,
        registry: EvaluatorRegistry,
        config: FloorPlanScoringConfig,
        context_factory: ScoringContextFactory | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        self._context_factory = context_factory or ScoringContextFactory()
        validate_config(config, registry)

    def score(
        self,
        floor_plan: FloorPlan,
        specification: FloorPlanGenerationSpec,
        *,
        mode: ExecutionMode,
    ) -> tuple[FloorPlanScoringResult, FloorPlanScoringDetails | None]:
        context = self._context_factory.build(
            floor_plan,
            specification,
            mode=mode,
        )
        groups = self._ordered_groups()
        rules_by_group = {
            str(group.key): self._ordered_rules(group) for group in groups
        }
        configured_allocations = self._group_allocations(groups)
        executions_by_group: dict[str, list[EvaluatorExecutionResult]] = {}

        critical_group = next(group for group in groups if group.key == CRITICAL_GROUP)
        critical_rules = rules_by_group[str(CRITICAL_GROUP)]
        critical_executions = [self._execute(rule, context) for rule in critical_rules]
        executions_by_group[str(CRITICAL_GROUP)] = critical_executions
        if not any(
            execution.status is EvaluationStatus.COMPLETED
            for execution in critical_executions
        ):
            raise EvaluatorExecutionError(
                "The critical scoring group produced no applicable evaluator results."
            )
        critical_failed = any(
            execution.status is EvaluationStatus.COMPLETED
            and execution.passed_threshold is False
            for execution in critical_executions
        )

        if critical_failed:
            weighted_critical, critical_result = self._score_group(
                critical_group,
                critical_executions,
                configured_allocations[str(CRITICAL_GROUP)],
                failed=True,
            )
            critical_evaluator_results = list(weighted_critical)
            critical_group_results = [critical_result]
            for group in groups:
                if group.key == CRITICAL_GROUP:
                    continue
                reason = "Skipped because the critical scoring group failed."
                skipped = [
                    self._skipped(rule, reason)
                    for rule in rules_by_group[str(group.key)]
                ]
                critical_evaluator_results.extend(skipped)
                critical_group_results.append(
                    ScoringGroupResult(
                        group_key=group.key,
                        status=GroupStatus.SKIPPED,
                        normalized_maximum=configured_allocations[str(group.key)],
                        raw_score=None,
                        contribution=0.0,
                    )
                )
            failure_metrics = (
                ScoreMetric(
                    "critical_group_score", critical_result.raw_score or 0.0
                ),
                ScoreMetric(
                    "earned_critical_contribution", critical_result.contribution
                ),
            )
            failure = ScoreFinding(
                code="CRITICAL_SCORING_FAILED",
                message="One or more critical floor-plan evaluators failed.",
                severity=FindingSeverity.ERROR,
            )
            result = FloorPlanScoringResult(
                total_score=_clamp_total(critical_result.contribution),
                passed_critical=False,
                critical_failure=failure,
            )
            details = (
                FloorPlanScoringDetails(
                    group_results=tuple(critical_group_results),
                    evaluator_results=tuple(critical_evaluator_results),
                    findings=(replace(failure, metrics=failure_metrics),),
                )
                if mode is ExecutionMode.DEBUG
                else None
            )
            return result, details

        for group in groups:
            if group.key == CRITICAL_GROUP:
                continue
            executions_by_group[str(group.key)] = [
                self._execute(rule, context) for rule in rules_by_group[str(group.key)]
            ]

        applicable_groups = [
            group
            for group in groups
            if any(
                execution.status is EvaluationStatus.COMPLETED
                for execution in executions_by_group[str(group.key)]
            )
        ]
        final_allocations = self._group_allocations(applicable_groups)
        evaluator_results: list[EvaluatorExecutionResult] = []
        group_results: list[ScoringGroupResult] = []
        for group in groups:
            executions = executions_by_group[str(group.key)]
            allocation = final_allocations.get(str(group.key), 0.0)
            weighted, group_result = self._score_group(
                group,
                executions,
                allocation,
                failed=False,
            )
            evaluator_results.extend(weighted)
            group_results.append(group_result)

        total_score = _clamp_total(sum(group.contribution for group in group_results))
        result = FloorPlanScoringResult(
            total_score=total_score,
            passed_critical=True,
            critical_failure=None,
        )
        details = (
            FloorPlanScoringDetails(
                group_results=tuple(group_results),
                evaluator_results=tuple(evaluator_results),
            )
            if mode is ExecutionMode.DEBUG
            else None
        )
        return result, details

    def _execute(
        self,
        rule: EvaluatorRule,
        context: ScoringContext,
    ) -> EvaluatorExecutionResult:
        evaluator = self._registry.get(rule.key)
        try:
            raw_result = evaluator.evaluate(context, rule.settings)
        except FloorPlanScoringError:
            raise
        except Exception as exc:
            raise EvaluatorExecutionError(
                f"Evaluator '{rule.key}' failed unexpectedly: {exc}"
            ) from exc
        try:
            result = validate_evaluator_result(str(rule.key), raw_result)
        except EvaluatorContractError:
            raise

        passed_threshold: bool | None = None
        if (
            rule.group_key == CRITICAL_GROUP
            and result.status is EvaluationStatus.COMPLETED
        ):
            assert result.score is not None
            assert rule.minimum_score is not None
            passed_threshold = result.score >= rule.minimum_score
        debug_enabled = context.mode is ExecutionMode.DEBUG
        findings = (
            result.findings
            if debug_enabled
            else tuple(replace(finding, metrics=()) for finding in result.findings)
        )
        return EvaluatorExecutionResult(
            evaluator_key=rule.key,
            group_key=rule.group_key,
            status=result.status,
            raw_score=result.score,
            configured_weight=rule.weight,
            threshold=rule.minimum_score,
            passed_threshold=passed_threshold,
            findings=findings,
            metrics=result.metrics if debug_enabled else (),
            visualization_payload=(
                result.visualization_payload if debug_enabled else None
            ),
        )

    @staticmethod
    def _score_group(
        group: ScoringGroupRule,
        executions: list[EvaluatorExecutionResult],
        allocation: float,
        *,
        failed: bool,
    ) -> tuple[list[EvaluatorExecutionResult], ScoringGroupResult]:
        applicable = [
            execution
            for execution in executions
            if execution.status is EvaluationStatus.COMPLETED
        ]
        if not applicable:
            return executions, ScoringGroupResult(
                group_key=group.key,
                status=GroupStatus.NOT_APPLICABLE,
                normalized_maximum=0.0,
                raw_score=None,
                contribution=0.0,
            )

        total_weight = sum(execution.configured_weight for execution in applicable)
        weighted: list[EvaluatorExecutionResult] = []
        raw_group_score = 0.0
        contribution = 0.0
        for execution in executions:
            if execution.status is not EvaluationStatus.COMPLETED:
                weighted.append(execution)
                continue
            normalized_weight = execution.configured_weight / total_weight
            raw_score = execution.raw_score or 0.0
            evaluator_contribution = allocation * normalized_weight * raw_score / 100.0
            raw_group_score += normalized_weight * raw_score
            contribution += evaluator_contribution
            weighted.append(
                replace(
                    execution,
                    normalized_weight=normalized_weight,
                    contribution=evaluator_contribution,
                )
            )
        return weighted, ScoringGroupResult(
            group_key=group.key,
            status=GroupStatus.FAILED if failed else GroupStatus.COMPLETED,
            normalized_maximum=allocation,
            raw_score=raw_group_score,
            contribution=contribution,
        )

    @staticmethod
    def _skipped(rule: EvaluatorRule, reason: str) -> EvaluatorExecutionResult:
        return EvaluatorExecutionResult(
            evaluator_key=rule.key,
            group_key=rule.group_key,
            status=EvaluationStatus.SKIPPED,
            raw_score=None,
            configured_weight=rule.weight,
            threshold=rule.minimum_score,
            findings=(
                ScoreFinding(
                    code="SKIPPED_AFTER_CRITICAL_FAILURE",
                    message=reason,
                    severity=FindingSeverity.WARNING,
                ),
            ),
        )

    def _ordered_groups(self) -> list[ScoringGroupRule]:
        return sorted(
            (group for group in self._config.groups if group.enabled),
            key=lambda group: (group.order, str(group.key)),
        )

    def _ordered_rules(self, group: ScoringGroupRule) -> list[EvaluatorRule]:
        return sorted(
            (
                rule
                for rule in self._config.evaluators
                if rule.enabled and rule.group_key == group.key
            ),
            key=lambda rule: (rule.order, str(rule.key)),
        )

    @staticmethod
    def _group_allocations(groups: list[ScoringGroupRule]) -> dict[str, float]:
        total_weight = sum(group.weight for group in groups)
        if total_weight <= 0:
            return {}
        return {str(group.key): 100.0 * group.weight / total_weight for group in groups}


def _clamp_total(value: float) -> float:
    numeric = float(value)
    if abs(numeric) <= 1e-12:
        return 0.0
    if abs(numeric - 100.0) <= 1e-12:
        return 100.0
    return min(100.0, max(0.0, numeric))
