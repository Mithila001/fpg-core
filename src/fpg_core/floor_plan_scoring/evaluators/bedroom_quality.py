from __future__ import annotations

from dataclasses import dataclass

from ...domain import RoomType
from ..context import ScoringContext
from ..exceptions import ScoringConfigurationError
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ScoreMetric,
)
from .base import FloorPlanEvaluator
from .common import clamp_score, require_non_negative, require_positive, typed_settings

BEDROOM_QUALITY_KEY = EvaluatorKey("bedroom_quality")


@dataclass(frozen=True, slots=True)
class BedroomQualitySettings:
    area_compliance_weight: float
    consistency_weight: float
    full_spread_penalty_ratio: float
    maximum_spread_penalty: float

    def __post_init__(self) -> None:
        require_non_negative(
            self.area_compliance_weight, "Bedroom area-compliance weight"
        )
        require_non_negative(self.consistency_weight, "Bedroom consistency weight")
        if self.area_compliance_weight + self.consistency_weight <= 0:
            raise ScoringConfigurationError(
                "Bedroom quality weights must have a positive total."
            )
        require_positive(
            self.full_spread_penalty_ratio, "Bedroom full-spread penalty ratio"
        )
        require_non_negative(
            self.maximum_spread_penalty, "Bedroom maximum spread penalty"
        )
        if self.maximum_spread_penalty > 100:
            raise ScoringConfigurationError(
                "Bedroom maximum spread penalty cannot exceed 100."
            )


class BedroomQualityEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return BEDROOM_QUALITY_KEY

    @property
    def settings_type(self) -> type[object]:
        return BedroomQualitySettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, BedroomQualitySettings, str(self.key))
        bedrooms = [
            room for room in context.rooms if room.room_type is RoomType.BEDROOM
        ]
        if not bedrooms:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)

        compliance_scores: list[float] = []
        findings: list[ScoreFinding] = []
        for room in bedrooms:
            size = context.specs_by_id[room.room_id].size
            if room.area < size.min_area:
                compliance = 100.0 * room.area / size.min_area
                findings.append(
                    ScoreFinding(
                        code="BEDROOM_BELOW_MINIMUM_AREA",
                        message=f"Bedroom '{room.name}' is below its specified minimum area.",
                        severity=FindingSeverity.WARNING,
                        subject_ids=(room.room_id,),
                        metrics=(ScoreMetric("area", room.area, "square_units"),),
                    )
                )
            elif room.area > size.max_area:
                compliance = 100.0 * size.max_area / room.area
                findings.append(
                    ScoreFinding(
                        code="BEDROOM_ABOVE_MAXIMUM_AREA",
                        message=f"Bedroom '{room.name}' exceeds its specified maximum area.",
                        severity=FindingSeverity.WARNING,
                        subject_ids=(room.room_id,),
                        metrics=(ScoreMetric("area", room.area, "square_units"),),
                    )
                )
            else:
                compliance = 100.0
            compliance_scores.append(clamp_score(compliance))

        area_score = sum(compliance_scores) / len(compliance_scores)
        areas = [room.area for room in bedrooms]
        relative_spread = 0.0
        if len(areas) > 1:
            mean_area = sum(areas) / len(areas)
            relative_spread = (max(areas) - min(areas)) / max(mean_area, 1e-12)
        spread_penalty = min(
            config.maximum_spread_penalty,
            relative_spread
            / config.full_spread_penalty_ratio
            * config.maximum_spread_penalty,
        )
        consistency_score = 100.0 - spread_penalty
        total_weight = config.area_compliance_weight + config.consistency_weight
        final_score = (
            area_score * config.area_compliance_weight
            + consistency_score * config.consistency_weight
        ) / total_weight
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            clamp_score(final_score),
            tuple(findings),
            (
                ScoreMetric("bedroom_count", len(bedrooms)),
                ScoreMetric("area_compliance_score", area_score),
                ScoreMetric("consistency_score", consistency_score),
                ScoreMetric("relative_area_spread", relative_spread),
            ),
        )
