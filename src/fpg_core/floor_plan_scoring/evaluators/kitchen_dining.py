from __future__ import annotations

import math
from dataclasses import dataclass

from ..domain import RoomType
from ..context import ScoringContext, shared_boundary_length
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult, ScoreMetric
from .base import FloorPlanEvaluator
from .common import clamp_score, require_non_negative, require_positive, typed_settings

KITCHEN_DINING_KEY = EvaluatorKey("kitchen_dining_proximity")


@dataclass(frozen=True, slots=True)
class KitchenDiningSettings:
    minimum_shared_boundary: float
    maximum_distance: float
    tolerance: float

    def __post_init__(self) -> None:
        require_non_negative(
            self.minimum_shared_boundary, "Kitchen-dining shared boundary"
        )
        require_positive(self.maximum_distance, "Kitchen-dining maximum distance")
        require_non_negative(self.tolerance, "Kitchen-dining tolerance")


class KitchenDiningEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return KITCHEN_DINING_KEY

    @property
    def settings_type(self) -> type[object]:
        return KitchenDiningSettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, KitchenDiningSettings, str(self.key))
        kitchens = [
            room for room in context.rooms if room.room_type is RoomType.KITCHEN
        ]
        dining_rooms = [
            room
            for room in context.rooms
            if room.room_type is RoomType.DINING_ROOM
        ]
        if not kitchens or not dining_rooms:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)

        best_shared = 0.0
        best_distance = float("inf")
        for kitchen in kitchens:
            for dining in dining_rooms:
                best_shared = max(
                    best_shared,
                    shared_boundary_length(context, kitchen.room_id, dining.room_id),
                )
                best_distance = min(
                    best_distance,
                    math.dist(kitchen.centroid, dining.centroid),
                )
        if best_shared + config.tolerance >= config.minimum_shared_boundary:
            score = 100.0
        else:
            score = clamp_score(100.0 * (1.0 - best_distance / config.maximum_distance))
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            score,
            metrics=(
                ScoreMetric("maximum_shared_boundary", best_shared, "units"),
                ScoreMetric("minimum_centroid_distance", best_distance, "units"),
            ),
        )
