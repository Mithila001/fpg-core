from collections.abc import Mapping
from typing import Any

from shapely.ops import unary_union

from ...domain import ExecutionMode
from ..context import ScoringContext
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult
from .base import CandidateEvaluator

SPATIAL_OCCUPANCY_KEY = EvaluatorKey("spatial_occupancy")


class SpatialOccupancyEvaluator(CandidateEvaluator):
    """Score footprint overlap and floor-boundary overflow continuously."""

    @property
    def key(self):
        return SPATIAL_OCCUPANCY_KEY

    def evaluate(self, context: ScoringContext, settings: Mapping[str, Any]):
        footprints = context.derived["footprints"]
        if not footprints:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        floor = context.derived["floor_geometry"]
        circles = context.derived["circles"]
        details = []
        for key, footprint in footprints.items():
            circle = circles[key]
            inside = circle.intersection(floor)
            others = [
                other
                for other_key, other in circles.items()
                if other_key != key and circle.intersects(other)
            ]
            overlap = inside.intersection(unary_union(others)).area if others else 0.0
            overflow = circle.area - inside.area
            overlap_ratio, overflow_ratio = (
                overlap / circle.area,
                overflow / circle.area,
            )
            score = 100 * max(0.0, min(1.0, 1 - overlap_ratio - overflow_ratio))
            point = footprint.point
            details.append(
                {
                    "point_id": key,
                    "room_id": point.source_room_id,
                    "room_type": point.room_type.value,
                    "hint_index": point.hint_index,
                    "x": point.x,
                    "y": point.y,
                    "radius": footprint.radius,
                    "allocated_area": footprint.allocated_area,
                    "overlap_ratio": overlap_ratio,
                    "overflow_ratio": overflow_ratio,
                    "score": score,
                }
            )
        score = sum(item["score"] for item in details) / len(details)
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            score,
            metrics={"room_count": float(len(details)), "score": score}
            if context.mode is ExecutionMode.DEBUG
            else {},
            details={"rooms": details, "score": score}
            if context.mode is ExecutionMode.DEBUG
            else None,
        )
