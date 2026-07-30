from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import MultiPolygon, Polygon

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

ENCLOSED_VOIDS_KEY = EvaluatorKey("enclosed_voids")


@dataclass(frozen=True, slots=True)
class EnclosedVoidVisualization:
    points: tuple[tuple[float, float], ...]
    area: float
    affects_score: bool


@dataclass(frozen=True, slots=True)
class EnclosedVoidsVisualizationData:
    area_tolerance: float
    voids: tuple[EnclosedVoidVisualization, ...]


@dataclass(frozen=True, slots=True)
class EnclosedVoidsSettings:
    area_tolerance: float

    def __post_init__(self) -> None:
        require_non_negative(self.area_tolerance, "Enclosed-void area tolerance")


class EnclosedVoidsEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return ENCLOSED_VOIDS_KEY

    @property
    def settings_type(self) -> type[object]:
        return EnclosedVoidsSettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, EnclosedVoidsSettings, str(self.key))
        if context.room_union is None:
            return EvaluatorResult(
                self.key,
                EvaluationStatus.COMPLETED,
                0.0,
                (
                    ScoreFinding(
                        code="ROOM_UNION_UNAVAILABLE",
                        message="Room geometry could not be combined for enclosed-void analysis.",
                        severity=FindingSeverity.ERROR,
                    ),
                ),
                visualization_payload=EnclosedVoidsVisualizationData(
                    area_tolerance=config.area_tolerance,
                    voids=(),
                ),
            )

        polygons: tuple[Polygon, ...]
        if isinstance(context.room_union, Polygon):
            polygons = (context.room_union,)
        elif isinstance(context.room_union, MultiPolygon):
            polygons = tuple(context.room_union.geoms)
        else:
            polygons = tuple(
                geometry
                for geometry in getattr(context.room_union, "geoms", ())
                if isinstance(geometry, Polygon)
            )
        void_polygons = [
            Polygon(interior)
            for polygon in polygons
            for interior in polygon.interiors
        ]
        void_areas = [float(void.area) for void in void_polygons]
        significant = [area for area in void_areas if area > config.area_tolerance]
        total_area = sum(significant)
        findings = ()
        if significant:
            findings = (
                ScoreFinding(
                    code="ENCLOSED_VOID_DETECTED",
                    message=f"Detected {len(significant)} enclosed void(s) in the room layout.",
                    severity=FindingSeverity.ERROR,
                    metrics=(
                        ScoreMetric("enclosed_void_area", total_area, "square_units"),
                    ),
                ),
            )
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            0.0 if significant else 100.0,
            findings,
            (
                ScoreMetric("enclosed_void_count", len(significant)),
                ScoreMetric("enclosed_void_area", total_area, "square_units"),
            ),
            visualization_payload=EnclosedVoidsVisualizationData(
                area_tolerance=config.area_tolerance,
                voids=tuple(
                    EnclosedVoidVisualization(
                        points=tuple(
                            (float(x), float(y))
                            for x, y in void.exterior.coords
                        ),
                        area=float(void.area),
                        affects_score=float(void.area) > config.area_tolerance,
                    )
                    for void in void_polygons
                ),
            ),
        )
