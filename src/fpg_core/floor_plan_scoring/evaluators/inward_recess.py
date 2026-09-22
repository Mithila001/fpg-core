from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, MultiPolygon, Polygon

from ...domain import ExecutionMode
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
from .common import require_non_negative, typed_settings

INWARD_RECESS_KEY = EvaluatorKey("inward_recess")


@dataclass(frozen=True, slots=True)
class InwardPocketVisualization:
    pocket_index: int
    points: tuple[tuple[float, float], ...]
    measured_length: float
    violates_maximum: bool


@dataclass(frozen=True, slots=True)
class InwardRecessVisualizationData:
    maximum_length: float
    tolerance: float
    pockets: tuple[InwardPocketVisualization, ...]


@dataclass(frozen=True, slots=True)
class InwardRecessSettings:
    maximum_length: float
    tolerance: float

    def __post_init__(self) -> None:
        require_non_negative(self.maximum_length, "Maximum inward-recess length")
        require_non_negative(self.tolerance, "Inward-recess tolerance")


class InwardRecessEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return INWARD_RECESS_KEY

    @property
    def settings_type(self) -> type[object]:
        return InwardRecessSettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, InwardRecessSettings, str(self.key))
        union = context.room_union
        if union is None or union.is_empty:
            return EvaluatorResult(
                self.key,
                EvaluationStatus.COMPLETED,
                0.0,
                (
                    ScoreFinding(
                        code="ROOM_UNION_UNAVAILABLE",
                        message="Room geometry could not be combined for inward-recess analysis.",
                        severity=FindingSeverity.ERROR,
                    ),
                ),
                visualization_payload=(
                    InwardRecessVisualizationData(
                        maximum_length=config.maximum_length,
                        tolerance=config.tolerance,
                        pockets=(),
                    )
                    if context.mode is ExecutionMode.DEBUG
                    else None
                ),
            )

        hull = union.convex_hull
        pockets = _pocket_polygons(hull.difference(union))
        violating: list[tuple[int, float]] = []
        maximum_observed = 0.0
        visualized_pockets: list[InwardPocketVisualization] = []
        plan_boundary = union.boundary
        hull_boundary = hull.boundary

        for pocket_index, pocket in enumerate(pockets):
            segments = _segments(pocket, config.tolerance)
            outer = [
                segment
                for segment in segments
                if segment[2].intersection(plan_boundary).length > config.tolerance
            ]
            convex = [
                segment
                for segment in segments
                if segment[2].intersection(hull_boundary).length > config.tolerance
            ]
            if not convex or len(outer) == 2:
                continue

            horizontal_hull = sum(
                segment.length
                for first, second, segment in convex
                if _orientation(first, second, config.tolerance) == "horizontal"
            )
            vertical_hull = sum(
                segment.length
                for first, second, segment in convex
                if _orientation(first, second, config.tolerance) == "vertical"
            )
            opposing = "vertical" if horizontal_hull >= vertical_hull else "horizontal"
            lengths = [
                float(segment.length)
                for first, second, segment in outer
                if _orientation(first, second, config.tolerance) == opposing
            ]
            pocket_maximum = max(lengths, default=0.0)
            maximum_observed = max(maximum_observed, pocket_maximum)
            violates = pocket_maximum > config.maximum_length + config.tolerance
            if context.mode is ExecutionMode.DEBUG:
                visualized_pockets.append(
                    InwardPocketVisualization(
                        pocket_index=pocket_index,
                        points=tuple(
                            (float(x), float(y)) for x, y in pocket.exterior.coords
                        ),
                        measured_length=pocket_maximum,
                        violates_maximum=violates,
                    )
                )
            if violates:
                violating.append((pocket_index, pocket_maximum))

        findings = tuple(
            ScoreFinding(
                code="INWARD_RECESS_TOO_LONG",
                message=(
                    f"Inward recess {index} has length {length:.4f}, exceeding "
                    f"the configured maximum {config.maximum_length:.4f}."
                ),
                severity=FindingSeverity.ERROR,
                metrics=(ScoreMetric("recess_length", length, "units"),),
            )
            for index, length in violating
        )
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            0.0 if violating else 100.0,
            findings,
            (
                ScoreMetric("pocket_count", len(pockets)),
                ScoreMetric("violating_recess_count", len(violating)),
                ScoreMetric("maximum_recess_length", maximum_observed, "units"),
            ),
            visualization_payload=(
                InwardRecessVisualizationData(
                    maximum_length=config.maximum_length,
                    tolerance=config.tolerance,
                    pockets=tuple(visualized_pockets),
                )
                if context.mode is ExecutionMode.DEBUG
                else None
            ),
        )


def _pocket_polygons(geometry: object) -> tuple[Polygon, ...]:
    if getattr(geometry, "is_empty", True):
        return ()
    if isinstance(geometry, Polygon):
        return (geometry,)
    if isinstance(geometry, MultiPolygon):
        return tuple(geometry.geoms)
    return tuple(
        item for item in getattr(geometry, "geoms", ()) if isinstance(item, Polygon)
    )


def _segments(
    polygon: Polygon,
    tolerance: float,
) -> list[tuple[tuple[float, float], tuple[float, float], LineString]]:
    coordinates = [(float(x), float(y)) for x, y in polygon.exterior.coords]
    if coordinates and coordinates[0] == coordinates[-1]:
        coordinates.pop()
    result: list[tuple[tuple[float, float], tuple[float, float], LineString]] = []
    for index, first in enumerate(coordinates):
        second = coordinates[(index + 1) % len(coordinates)]
        segment = LineString((first, second))
        if segment.length > tolerance:
            result.append((first, second, segment))
    return result


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    tolerance: float,
) -> str:
    dx = abs(second[0] - first[0])
    dy = abs(second[1] - first[1])
    if dx <= tolerance < dy:
        return "vertical"
    if dy <= tolerance < dx:
        return "horizontal"
    return "other"
