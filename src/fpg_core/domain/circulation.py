from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .floor_plan_spec import RoomId, RoomType

_MAX_NUMERIC_COST = 1_000_000_000_000.0


def _finite_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not boolean.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _positive_cost(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    if number > _MAX_NUMERIC_COST:
        raise ValueError(f"{field_name} exceeds the numerical safety limit.")
    return number


def _non_negative_cost(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    if number > _MAX_NUMERIC_COST:
        raise ValueError(f"{field_name} exceeds the numerical safety limit.")
    return number


class DestinationSelection(StrEnum):
    """Determines which matching destinations a route rule selects."""

    ALL_MATCHING = "all_matching"
    LOWEST_COST_MATCH = "lowest_cost_match"


class CirculationTrafficClass(StrEnum):
    """Architectural traffic carried by a configured route."""

    PUBLIC = "public"
    PRIVATE = "private"


class HallwayTrafficClass(StrEnum):
    """Traffic role assigned to one hallway hint point."""

    PUBLIC = "public"
    PRIVATE = "private"
    MIXED = "mixed"
    UNCLASSIFIED = "unclassified"
    UNUSED = "unused"


@dataclass(frozen=True, slots=True)
class CirculationGrid:
    """Axis-aligned routing grid expressed in project units."""

    width: float
    length: float
    scale: float
    origin_x: float = 0.0
    origin_y: float = 0.0

    def __post_init__(self) -> None:
        width = _finite_number("width", self.width)
        length = _finite_number("length", self.length)
        scale = _finite_number("scale", self.scale)
        origin_x = _finite_number("origin_x", self.origin_x)
        origin_y = _finite_number("origin_y", self.origin_y)

        if width <= 0:
            raise ValueError("width must be greater than zero.")
        if length <= 0:
            raise ValueError("length must be greater than zero.")
        if scale <= 0:
            raise ValueError("scale must be greater than zero.")

        object.__setattr__(self, "width", width)
        object.__setattr__(self, "length", length)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "origin_x", origin_x)
        object.__setattr__(self, "origin_y", origin_y)


@dataclass(frozen=True, slots=True)
class GridRoutingCostProfile:
    """Costs shared by orthogonal grid-routing features."""

    empty_node_cost: float
    traversable_hint_node_cost: float
    turn_cost: float
    perimeter_bias_max_cost: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "empty_node_cost",
            _positive_cost("empty_node_cost", self.empty_node_cost),
        )
        object.__setattr__(
            self,
            "traversable_hint_node_cost",
            _positive_cost(
                "traversable_hint_node_cost",
                self.traversable_hint_node_cost,
            ),
        )
        object.__setattr__(
            self,
            "turn_cost",
            _non_negative_cost("turn_cost", self.turn_cost),
        )
        object.__setattr__(
            self,
            "perimeter_bias_max_cost",
            _non_negative_cost(
                "perimeter_bias_max_cost",
                self.perimeter_bias_max_cost,
            ),
        )


@dataclass(frozen=True, slots=True)
class CirculationRouteRule:
    """Shared typed request for room-type circulation routing."""

    id: int
    name: str
    source_room_type: RoomType
    destination_room_type: RoomType
    destination_selection: DestinationSelection
    traffic_class: CirculationTrafficClass
    allowed_transit_room_types: tuple[RoomType, ...]
    importance_weight: float

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int):
            raise TypeError("Route rule id must be an integer.")
        if self.id < 0:
            raise ValueError("Route rule id cannot be negative.")

        if not isinstance(self.name, str):
            raise TypeError("Route rule name must be a string.")
        name = self.name.strip()
        if not name:
            raise ValueError("Route rule name cannot be empty.")

        if not isinstance(self.source_room_type, RoomType):
            raise TypeError("source_room_type must be a RoomType member.")
        if not isinstance(self.destination_room_type, RoomType):
            raise TypeError("destination_room_type must be a RoomType member.")
        if self.source_room_type is self.destination_room_type:
            raise ValueError(
                "source_room_type and destination_room_type must be different."
            )
        if not isinstance(self.destination_selection, DestinationSelection):
            raise TypeError(
                "destination_selection must be a DestinationSelection member."
            )
        if not isinstance(self.traffic_class, CirculationTrafficClass):
            raise TypeError(
                "traffic_class must be a CirculationTrafficClass member."
            )

        allowed_types = tuple(self.allowed_transit_room_types)
        if any(not isinstance(room_type, RoomType) for room_type in allowed_types):
            raise TypeError(
                "Every allowed_transit_room_type must be a RoomType member."
            )
        if len(allowed_types) != len(set(allowed_types)):
            raise ValueError("allowed_transit_room_types must be unique.")

        importance_weight = _positive_cost(
            "importance_weight",
            self.importance_weight,
        )

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "allowed_transit_room_types", allowed_types)
        object.__setattr__(self, "importance_weight", importance_weight)


@dataclass(frozen=True, slots=True)
class HallwayClassification:
    """Production-safe traffic classification for one hallway hint point."""

    room_id: RoomId
    hint_index: int
    traffic_class: HallwayTrafficClass

    def __post_init__(self) -> None:
        if not isinstance(self.room_id, str):
            raise TypeError("Hallway classification room_id must be string based.")
        room_id = self.room_id.strip()
        if not room_id:
            raise ValueError("Hallway classification room_id cannot be empty.")
        if isinstance(self.hint_index, bool) or not isinstance(self.hint_index, int):
            raise TypeError("Hallway classification hint_index must be an integer.")
        if self.hint_index <= 0:
            raise ValueError(
                "Hallway classification hint_index must be greater than zero."
            )
        if not isinstance(self.traffic_class, HallwayTrafficClass):
            raise TypeError(
                "traffic_class must be a HallwayTrafficClass member."
            )
        object.__setattr__(self, "room_id", RoomId(room_id))

    @property
    def point_key(self) -> str:
        return f"{self.room_id}[{self.hint_index}]"


@dataclass(frozen=True, slots=True)
class CirculationGridNode:
    """One grid node used by an orthogonal circulation path."""

    x_index: int
    y_index: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class RouteCostBreakdown:
    """Cost components accumulated by one resolved circulation route."""

    movement_cost: float
    perimeter_bias_cost: float
    turn_cost: float
    traffic_conflict_cost: float
    total_cost: float
