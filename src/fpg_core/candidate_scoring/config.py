from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ..domain import LandSide, RoomType
from .types import EvaluatorCategory, EvaluatorKey


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ExteriorClearanceRule:
    """One global-direction clearance requirement for selected room types.

    A source room qualifies when at least one of its hint points has no other
    room hint point inside the configured corridor. Multiple hallway hints are
    therefore still counted as one room.
    """

    room_types: tuple[RoomType, ...]
    required_clear_room_count: int
    clearance_width: float
    direction: LandSide

    def __post_init__(self) -> None:
        room_types = tuple(self.room_types)
        if not room_types:
            raise ValueError("Exterior clearance room_types cannot be empty.")
        if any(not isinstance(room_type, RoomType) for room_type in room_types):
            raise TypeError(
                "Every exterior clearance room type must be a RoomType member."
            )
        if len(room_types) != len(set(room_types)):
            raise ValueError("Exterior clearance room_types must be unique.")

        if isinstance(self.required_clear_room_count, bool) or not isinstance(
            self.required_clear_room_count,
            int,
        ):
            raise TypeError("required_clear_room_count must be an integer.")
        if self.required_clear_room_count <= 0:
            raise ValueError("required_clear_room_count must be greater than zero.")

        if isinstance(self.clearance_width, bool):
            raise TypeError("clearance_width must be numeric, not boolean.")
        try:
            clearance_width = float(self.clearance_width)
        except (TypeError, ValueError) as exc:
            raise TypeError("clearance_width must be numeric.") from exc
        if not math.isfinite(clearance_width) or clearance_width <= 0:
            raise ValueError("clearance_width must be positive and finite.")

        if not isinstance(self.direction, LandSide):
            raise TypeError("direction must be a LandSide member.")

        object.__setattr__(self, "room_types", room_types)
        object.__setattr__(self, "clearance_width", clearance_width)


@dataclass(frozen=True, slots=True)
class EvaluatorRule:
    """Manager-owned configuration for one registered evaluator."""

    key: EvaluatorKey
    category: EvaluatorCategory
    enabled: bool = True
    order: int = 0
    weight: float = 1.0
    minimum_score: float | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Configuration for the complete evaluator pipeline."""

    evaluator_rules: tuple[EvaluatorRule, ...]
    fail_fast_on_critical_failure: bool = True
    not_applicable_quality_contributes: bool = False
    raise_on_evaluator_error: bool = False
