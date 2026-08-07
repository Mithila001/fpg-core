from __future__ import annotations

from dataclasses import dataclass

from ...domain import RoomType
from ..context import ScoringContext
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult, ScoreMetric
from .base import FloorPlanEvaluator
from .common import clamp_score, require_positive, typed_settings

LIVING_ROOM_BALANCE_KEY = EvaluatorKey("living_room_balance")


@dataclass(frozen=True, slots=True)
class LivingRoomBalanceSettings:
    maximum_excess_ratio: float

    def __post_init__(self) -> None:
        require_positive(self.maximum_excess_ratio, "Living-room maximum excess ratio")


class LivingRoomBalanceEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return LIVING_ROOM_BALANCE_KEY

    @property
    def settings_type(self) -> type[object]:
        return LivingRoomBalanceSettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(settings, LivingRoomBalanceSettings, str(self.key))
        living_rooms = [
            room
            for room in context.rooms
            if room.room_type is RoomType.LIVING_ROOM
        ]
        if not living_rooms:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        living_area = sum(room.area for room in living_rooms)
        other_area = sum(
            room.area
            for room in context.rooms
            if room.room_type is not RoomType.LIVING_ROOM
        )
        if other_area <= 0 or living_area <= other_area:
            score = 100.0
            ratio = living_area / other_area if other_area > 0 else 0.0
        else:
            ratio = living_area / other_area
            score = clamp_score(
                100.0 * (1.0 - (ratio - 1.0) / config.maximum_excess_ratio)
            )
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            score,
            metrics=(
                ScoreMetric("living_area", living_area, "square_units"),
                ScoreMetric("other_room_area", other_area, "square_units"),
                ScoreMetric("living_to_other_ratio", ratio),
            ),
        )
