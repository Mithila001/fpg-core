from __future__ import annotations

from dataclasses import replace

from .config import EvaluatorRule, ScoringConfig
from .context import ScoringContext, ScoringContextFactory
from .registry import EvaluatorRegistry
from .types import (
    CandidateScoringInput,
    EvaluationStatus,
    EvaluatorCategory,
    EvaluatorExecutionResult,
    FindingSeverity,
    ScoreFinding,
    ScoringResult,
)
from .validation import (
    validate_evaluator_result,
    validate_scoring_config,
    validate_scoring_input,
)


class CandidateScoreManager:
    """Runs configured evaluator stages and calculates the final score."""

    def __init__(
        self,
        registry: EvaluatorRegistry,
        config: ScoringConfig,
        context_factory: ScoringContextFactory | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        self._context_factory = context_factory or ScoringContextFactory()
        validate_scoring_config(config, registry)

    def score(self, scoring_input: CandidateScoringInput) -> ScoringResult:
        validate_scoring_input(scoring_input)
        context = self._context_factory.build(scoring_input)

        critical_rules = self._ordered_rules(EvaluatorCategory.CRITICAL)
        quality_rules = self._ordered_rules(EvaluatorCategory.QUALITY)
        execution_results: list[EvaluatorExecutionResult] = []
        manager_findings: list[ScoreFinding] = []

        critical_failure: EvaluatorExecutionResult | None = None
        for rule in critical_rules:
            execution = self._execute(rule, context)
            execution_results.append(execution)

            current_failure: EvaluatorExecutionResult | None = None
            if execution.status is EvaluationStatus.ERROR:
                current_failure = execution
            elif (
                execution.status is EvaluationStatus.COMPLETED
                and execution.passed_threshold is False
            ):
                current_failure = execution

            if current_failure is not None and critical_failure is None:
                critical_failure = current_failure

            if current_failure is not None and self._config.fail_fast_on_critical_failure:
                break

        if critical_failure is not None:
            reason = self._critical_stop_reason(critical_failure)
            manager_findings.append(
                ScoreFinding(
                    code="CRITICAL_EVALUATOR_FAILED",
                    message=reason,
                    severity=FindingSeverity.ERROR,
                )
            )
            execution_results.extend(
                self._skipped_result(rule, reason)
                for rule in self._remaining_rules(
                    critical_rules,
                    quality_rules,
                    execution_results,
                )
            )
            return ScoringResult(
                total_score=0.0,
                passed_critical_checks=False,
                stopped_early=True,
                stop_reason=reason,
                evaluator_results=tuple(execution_results),
                findings=tuple(manager_findings),
            )

        quality_executions = [self._execute(rule, context) for rule in quality_rules]
        weighted_quality = self._apply_quality_weights(quality_executions)
        execution_results.extend(weighted_quality)

        total_score = sum(item.contribution for item in weighted_quality)
        total_score = min(100.0, max(0.0, total_score))

        return ScoringResult(
            total_score=total_score,
            passed_critical_checks=True,
            stopped_early=False,
            stop_reason=None,
            evaluator_results=tuple(execution_results),
            findings=tuple(manager_findings),
        )

    def _execute(
        self,
        rule: EvaluatorRule,
        context: ScoringContext,
    ) -> EvaluatorExecutionResult:
        evaluator = self._registry.get(rule.key)

        try:
            result = evaluator.evaluate(context, rule.settings)
            validate_evaluator_result(str(rule.key), result)
        except Exception as exc:
            if self._config.raise_on_evaluator_error:
                raise

            finding = ScoreFinding(
                code="EVALUATOR_ERROR",
                message=f"Evaluator '{rule.key}' failed: {exc}",
                severity=FindingSeverity.ERROR,
            )
            return EvaluatorExecutionResult(
                evaluator_key=rule.key,
                category=rule.category,
                status=EvaluationStatus.ERROR,
                raw_score=None,
                configured_weight=rule.weight,
                normalized_weight=0.0,
                contribution=0.0,
                threshold=rule.minimum_score,
                passed_threshold=False if rule.category is EvaluatorCategory.CRITICAL else None,
                findings=(finding,),
            )

        passed_threshold: bool | None = None
        if rule.category is EvaluatorCategory.CRITICAL:
            passed_threshold = (
                result.status is EvaluationStatus.NOT_APPLICABLE
                or (
                    result.status is EvaluationStatus.COMPLETED
                    and result.score is not None
                    and rule.minimum_score is not None
                    and result.score >= rule.minimum_score
                )
            )

        return EvaluatorExecutionResult(
            evaluator_key=rule.key,
            category=rule.category,
            status=result.status,
            raw_score=result.score,
            configured_weight=rule.weight,
            normalized_weight=0.0,
            contribution=0.0,
            threshold=rule.minimum_score,
            passed_threshold=passed_threshold,
            findings=result.findings,
            metrics=result.metrics,
            visualization_payload=result.visualization_payload,
        )

    def _apply_quality_weights(
        self,
        executions: list[EvaluatorExecutionResult],
    ) -> list[EvaluatorExecutionResult]:
        eligible = [
            execution
            for execution in executions
            if execution.status is EvaluationStatus.COMPLETED
            or (
                self._config.not_applicable_quality_contributes
                and execution.status is EvaluationStatus.NOT_APPLICABLE
            )
        ]
        total_weight = sum(item.configured_weight for item in eligible)

        if total_weight <= 0:
            return executions

        weighted: list[EvaluatorExecutionResult] = []
        for execution in executions:
            if execution not in eligible:
                weighted.append(execution)
                continue

            normalized_weight = execution.configured_weight / total_weight
            raw_score = execution.raw_score or 0.0
            contribution = raw_score * normalized_weight
            weighted.append(
                replace(
                    execution,
                    normalized_weight=normalized_weight,
                    contribution=contribution,
                )
            )
        return weighted

    def _ordered_rules(self, category: EvaluatorCategory) -> list[EvaluatorRule]:
        return sorted(
            (
                rule
                for rule in self._config.evaluator_rules
                if rule.enabled and rule.category is category
            ),
            key=lambda rule: (rule.order, str(rule.key)),
        )

    @staticmethod
    def _critical_stop_reason(result: EvaluatorExecutionResult) -> str:
        if result.status is EvaluationStatus.ERROR:
            return f"Critical evaluator '{result.evaluator_key}' failed to execute."
        return (
            f"Critical evaluator '{result.evaluator_key}' scored "
            f"{result.raw_score} but requires at least {result.threshold}."
        )

    @staticmethod
    def _skipped_result(
        rule: EvaluatorRule,
        reason: str,
    ) -> EvaluatorExecutionResult:
        return EvaluatorExecutionResult(
            evaluator_key=rule.key,
            category=rule.category,
            status=EvaluationStatus.SKIPPED,
            raw_score=None,
            configured_weight=rule.weight,
            normalized_weight=0.0,
            contribution=0.0,
            threshold=rule.minimum_score,
            passed_threshold=None,
            findings=(
                ScoreFinding(
                    code="SKIPPED_AFTER_CRITICAL_FAILURE",
                    message=reason,
                    severity=FindingSeverity.INFO,
                ),
            ),
        )

    @staticmethod
    def _remaining_rules(
        critical_rules: list[EvaluatorRule],
        quality_rules: list[EvaluatorRule],
        completed: list[EvaluatorExecutionResult],
    ) -> list[EvaluatorRule]:
        completed_keys = {item.evaluator_key for item in completed}
        return [
            rule
            for rule in (*critical_rules, *quality_rules)
            if rule.key not in completed_keys
        ]
