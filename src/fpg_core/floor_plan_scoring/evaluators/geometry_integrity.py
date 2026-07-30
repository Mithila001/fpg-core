from __future__ import annotations

from dataclasses import dataclass

from shapely.errors import ShapelyError

from ..context import ScoringContext
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ScoreMetric,
)
from .base import FloorPlanEvaluator
from .common import is_rectilinear, require_non_negative, typed_settings

GEOMETRY_INTEGRITY_KEY = EvaluatorKey("geometry_integrity")


@dataclass(frozen=True, slots=True)
class GeometryIntegritySettings:
    tolerance: float

    def __post_init__(self) -> None:
        require_non_negative(self.tolerance, "Geometry tolerance")


class GeometryIntegrityEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return GEOMETRY_INTEGRITY_KEY

    @property
    def settings_type(self) -> type[object]:
        return GeometryIntegritySettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, GeometryIntegritySettings, str(self.key))
        findings: list[ScoreFinding] = []
        invalid_polygon_count = 0
        diagonal_polygon_count = 0
        containment_failure_count = 0
        overlap_count = 0

        if (
            not context.floor_polygon.is_valid
            or context.floor_polygon.area <= config.tolerance
        ):
            invalid_polygon_count += 1
            findings.append(
                ScoreFinding(
                    code="INVALID_FLOOR_BOUNDARY",
                    message="The floor boundary is topologically invalid or has no positive area.",
                    severity=FindingSeverity.ERROR,
                )
            )
        if not is_rectilinear(context.floor_points, config.tolerance):
            diagonal_polygon_count += 1
            findings.append(
                ScoreFinding(
                    code="NON_RECTILINEAR_FLOOR_BOUNDARY",
                    message="The floor boundary contains a diagonal edge.",
                    severity=FindingSeverity.ERROR,
                )
            )
        min_x, min_y, max_x, max_y = context.floor_polygon.bounds
        if (
            min_x < -config.tolerance
            or min_y < -config.tolerance
            or max_x > context.floor_width + config.tolerance
            or max_y > context.floor_length + config.tolerance
        ):
            containment_failure_count += 1
            findings.append(
                ScoreFinding(
                    code="FLOOR_BOUNDARY_OUTSIDE_SPECIFICATION",
                    message="The floor boundary extends outside the specified floor dimensions.",
                    severity=FindingSeverity.ERROR,
                )
            )

        for room in context.rooms:
            if not room.polygon.is_valid or room.area <= config.tolerance:
                invalid_polygon_count += 1
                findings.append(
                    ScoreFinding(
                        code="INVALID_ROOM_POLYGON",
                        message=f"Room '{room.name}' has invalid or zero-area geometry.",
                        severity=FindingSeverity.ERROR,
                        subject_ids=(room.room_id,),
                    )
                )
            if not is_rectilinear(room.points, config.tolerance):
                diagonal_polygon_count += 1
                findings.append(
                    ScoreFinding(
                        code="NON_RECTILINEAR_ROOM",
                        message=f"Room '{room.name}' contains a diagonal edge.",
                        severity=FindingSeverity.ERROR,
                        subject_ids=(room.room_id,),
                    )
                )
            try:
                if not context.floor_polygon.buffer(config.tolerance).covers(
                    room.polygon
                ):
                    containment_failure_count += 1
                    findings.append(
                        ScoreFinding(
                            code="ROOM_OUTSIDE_FLOOR_BOUNDARY",
                            message=f"Room '{room.name}' extends outside the floor boundary.",
                            severity=FindingSeverity.ERROR,
                            subject_ids=(room.room_id,),
                        )
                    )
            except ShapelyError:
                containment_failure_count += 1
                findings.append(
                    ScoreFinding(
                        code="ROOM_CONTAINMENT_UNAVAILABLE",
                        message=f"Containment could not be evaluated for room '{room.name}'.",
                        severity=FindingSeverity.ERROR,
                        subject_ids=(room.room_id,),
                    )
                )

        for index, room_a in enumerate(context.rooms):
            for room_b in context.rooms[index + 1 :]:
                try:
                    overlap_area = float(
                        room_a.polygon.intersection(room_b.polygon).area
                    )
                except ShapelyError:
                    overlap_area = None
                if overlap_area is None or overlap_area > config.tolerance:
                    overlap_count += 1
                    overlap_metrics = (
                        (ScoreMetric("overlap_area", overlap_area, "square_units"),)
                        if overlap_area is not None
                        else ()
                    )
                    findings.append(
                        ScoreFinding(
                            code="ROOM_OVERLAP",
                            message=f"Rooms '{room_a.name}' and '{room_b.name}' overlap.",
                            severity=FindingSeverity.ERROR,
                            subject_ids=(room_a.room_id, room_b.room_id),
                            metrics=overlap_metrics,
                        )
                    )

        summary_metrics = (
            ScoreMetric("invalid_polygon_count", invalid_polygon_count),
            ScoreMetric("diagonal_polygon_count", diagonal_polygon_count),
            ScoreMetric("containment_failure_count", containment_failure_count),
            ScoreMetric("overlap_count", overlap_count),
        )
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=0.0 if findings else 100.0,
            findings=tuple(findings),
            metrics=summary_metrics,
        )
