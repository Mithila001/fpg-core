from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from typing import Any

from ...domain import ExecutionMode
from ..config import DEFAULT_VALID_ZONES, ZoneSuitabilityConfig
from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ZoneSuitabilityDetails,
    ZoneSuitabilityPointDetails,
    ZoneSuitabilityRuleDetails,
)
from .base import CandidateEvaluator
from .common import build_evaluation_data, clamp_score

ZONE_SUITABILITY_KEY = EvaluatorKey("zone_suitability")


class ZoneSuitabilityEvaluator(CandidateEvaluator):
    """Scores whether selected room types occupy preferred floor regions."""

    @property
    def key(self) -> EvaluatorKey:
        return ZONE_SUITABILITY_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        data = build_evaluation_data(context)
        config = _read_config(settings)
        debug_enabled = context.mode is ExecutionMode.DEBUG

        scores: list[float] = []
        findings: list[ScoreFinding] = []
        metrics: dict[str, float] = {}
        point_details: list[ZoneSuitabilityPointDetails] = []

        for point in data.points:
            cells = config.valid_zones.get(point.room_type)
            if not cells:
                continue

            nx = point.x / data.floor_width
            ny = point.y / data.floor_length
            distance_to_zone = _minimum_distance_to_cells(
                nx,
                ny,
                cells,
                config.zone_count_per_axis,
            )
            score = clamp_score(
                100.0 * (1.0 - distance_to_zone * config.falloff_multiplier)
            )
            scores.append(score)

            if debug_enabled:
                point_details.append(
                    ZoneSuitabilityPointDetails(
                        point_id=point.room_id,
                        source_room_id=point.source_room_id,
                        room_name=point.name,
                        room_type=point.room_type,
                        hint_index=point.hint_index,
                        x=point.x,
                        y=point.y,
                        preferred_cells=tuple(cells),
                        distance_to_zone=distance_to_zone,
                        score=score,
                        inside_preferred_zone=distance_to_zone <= 1e-12,
                    )
                )
                metrics[f"room.{point.room_id}.score"] = score
                metrics[f"room.{point.room_id}.distance_to_zone"] = (
                    distance_to_zone
                )

            if score < 100.0:
                findings.append(
                    ScoreFinding(
                        code="ROOM_OUTSIDE_PREFERRED_ZONE",
                        message=(
                            f"Room '{point.name}' is outside its preferred zone "
                            f"by {distance_to_zone:.3f} normalized units."
                        ),
                        severity=FindingSeverity.WARNING,
                        subject_ids=(point.source_room_id,),
                    )
                )

        if debug_enabled:
            metrics["scored_room_count"] = float(len(scores))
            details: ZoneSuitabilityDetails | None = ZoneSuitabilityDetails(
                floor_width=data.floor_width,
                floor_length=data.floor_length,
                zone_count_per_axis=config.zone_count_per_axis,
                falloff_multiplier=config.falloff_multiplier,
                rules=tuple(
                    ZoneSuitabilityRuleDetails(
                        room_type=room_type,
                        preferred_cells=tuple(cells),
                    )
                    for room_type, cells in config.valid_zones.items()
                ),
                points=tuple(point_details),
            )
        else:
            details = None

        if not scores:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_ZONE_SCORABLE_ROOMS",
                        message="No candidate rooms use configured zone rules.",
                    ),
                ),
                metrics=metrics,
                details=details,
            )

        final_score = clamp_score(sum(scores) / len(scores))
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=final_score,
            findings=tuple(findings),
            metrics=metrics,
            details=details,
        )


def _read_config(settings: Mapping[str, Any]) -> ZoneSuitabilityConfig:
    configured = settings.get("zone_config")
    if configured is not None:
        if not isinstance(configured, ZoneSuitabilityConfig):
            raise TypeError(
                "Zone suitability setting 'zone_config' must be a "
                "ZoneSuitabilityConfig instance."
            )
        return configured

    # Preserve existing caller settings while providing a typed public config.
    return ZoneSuitabilityConfig(
        zone_count_per_axis=int(
            settings.get("zone_count_per_axis", settings.get("grid_size", 3))
        ),
        falloff_multiplier=float(settings.get("falloff_multiplier", 1.5)),
        valid_zones=settings.get("valid_zones", DEFAULT_VALID_ZONES),
    )


def _minimum_distance_to_cells(
    nx: float,
    ny: float,
    cells: Collection[tuple[int, int]],
    grid_size: int,
) -> float:
    minimum = math.inf
    for cell_x, cell_y in cells:
        xmin = (cell_x - 1) / grid_size
        xmax = cell_x / grid_size
        ymin = (cell_y - 1) / grid_size
        ymax = cell_y / grid_size
        dx = max(0.0, xmin - nx, nx - xmax)
        dy = max(0.0, ymin - ny, ny - ymax)
        minimum = min(minimum, math.hypot(dx, dy))
    return minimum
