from __future__ import annotations

from dataclasses import dataclass

from ..context import ScoringContext, shared_boundary_length
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ScoreMetric,
)
from .base import FloorPlanEvaluator
from .common import require_non_negative, typed_settings

REQUIRED_ADJACENCY_KEY = EvaluatorKey("required_adjacency")


@dataclass(frozen=True, slots=True)
class RequiredAdjacencySettings:
    minimum_shared_boundary: float
    tolerance: float

    def __post_init__(self) -> None:
        require_non_negative(self.minimum_shared_boundary, "Minimum shared boundary")
        require_non_negative(self.tolerance, "Adjacency tolerance")


class RequiredAdjacencyEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return REQUIRED_ADJACENCY_KEY

    @property
    def settings_type(self) -> type[object]:
        return RequiredAdjacencySettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, RequiredAdjacencySettings, str(self.key))
        relations = tuple(
            relation for relation in context.relations if relation.strength == "hard"
        )
        if not relations:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)

        findings: list[ScoreFinding] = []
        evaluated_relations = 0
        for relation in relations:
            source = context.rooms_by_id.get(relation.source_room_id)
            if source is None:
                continue
            evaluated_relations += 1
            checks = {
                target_id: (
                    target_id in context.rooms_by_id
                    and shared_boundary_length(context, source.room_id, target_id)
                    + config.tolerance
                    >= config.minimum_shared_boundary
                )
                for target_id in relation.target_room_ids
            }
            passed = (
                all(checks.values())
                if relation.match_policy == "and"
                else any(checks.values())
            )
            if not passed:
                target_names = ", ".join(relation.target_room_ids)
                findings.append(
                    ScoreFinding(
                        code="HARD_ADJACENCY_UNSATISFIED",
                        message=(
                            f"Room '{source.name}' does not satisfy its {relation.match_policy.upper()} "
                            f"adjacency relation with: {target_names}."
                        ),
                        severity=FindingSeverity.ERROR,
                        subject_ids=(source.room_id, *relation.target_room_ids),
                    )
                )

        if evaluated_relations == 0:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            0.0 if findings else 100.0,
            tuple(findings),
            (
                ScoreMetric("evaluated_relation_count", evaluated_relations),
                ScoreMetric("failed_relation_count", len(findings)),
            ),
        )
