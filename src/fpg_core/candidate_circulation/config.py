from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..domain import RoomType
from .domain import DestinationSelection, TrafficClass

_MAX_NUMERIC_COST = 1_000_000_000_000.0
_MAX_ROUTING_PASSES = 10


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


@dataclass(frozen=True, slots=True)
class CirculationGrid:
    """Axis-aligned usable-floor grid expressed in project units."""

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
class RoutingCostProfile:
    """Required routing costs. No tuning values are silently defaulted."""

    empty_node_cost: float
    traversable_hint_node_cost: float
    turn_cost: float
    perimeter_bias_max_cost: float
    traffic_conflict_cost: float

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
        object.__setattr__(
            self,
            "traffic_conflict_cost",
            _positive_cost(
                "traffic_conflict_cost",
                self.traffic_conflict_cost,
            ),
        )


@dataclass(frozen=True, slots=True)
class CirculationRouteRule:
    """Expands a room-type relationship into one or more routed paths."""

    id: int
    name: str
    source_room_type: RoomType
    destination_room_type: RoomType
    destination_selection: DestinationSelection
    traffic_class: TrafficClass
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
        if not isinstance(self.traffic_class, TrafficClass):
            raise TypeError("traffic_class must be a TrafficClass member.")

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
class CandidateCirculationConfig:
    """Complete routing and hallway-refinement configuration."""

    grid: CirculationGrid
    costs: RoutingCostProfile
    route_rules: tuple[CirculationRouteRule, ...]
    always_traversable_room_types: tuple[RoomType, ...]
    max_routing_passes: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.grid, CirculationGrid):
            raise TypeError("grid must be a CirculationGrid instance.")
        if not isinstance(self.costs, RoutingCostProfile):
            raise TypeError("costs must be a RoutingCostProfile instance.")

        route_rules = tuple(self.route_rules)
        if not route_rules:
            raise ValueError("At least one circulation route rule is required.")
        if any(not isinstance(rule, CirculationRouteRule) for rule in route_rules):
            raise TypeError("Every route rule must be a CirculationRouteRule.")
        rule_ids = [rule.id for rule in route_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Circulation route rule IDs must be unique.")

        always_traversable = tuple(self.always_traversable_room_types)
        if any(not isinstance(room_type, RoomType) for room_type in always_traversable):
            raise TypeError(
                "Every always_traversable_room_type must be a RoomType member."
            )
        if len(always_traversable) != len(set(always_traversable)):
            raise ValueError("always_traversable_room_types must be unique.")

        if isinstance(self.max_routing_passes, bool) or not isinstance(
            self.max_routing_passes,
            int,
        ):
            raise TypeError("max_routing_passes must be an integer.")
        if self.max_routing_passes < 2:
            raise ValueError("max_routing_passes must be at least 2.")
        if self.max_routing_passes > _MAX_ROUTING_PASSES:
            raise ValueError(f"max_routing_passes cannot exceed {_MAX_ROUTING_PASSES}.")

        object.__setattr__(self, "route_rules", route_rules)
        object.__setattr__(
            self,
            "always_traversable_room_types",
            always_traversable,
        )
