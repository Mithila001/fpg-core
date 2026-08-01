from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain import RoomType


class DestinationSelection(StrEnum):
    """Determines which matching destination hints a route rule selects."""

    ALL_MATCHING = "all_matching"
    LOWEST_COST_MATCH = "lowest_cost_match"


class TrafficClass(StrEnum):
    """Architectural traffic carried by a configured route."""

    PUBLIC = "public"
    PRIVATE = "private"


class HallwayTrafficClass(StrEnum):
    """Traffic role inferred for one hallway hint point."""

    PUBLIC = "public"
    PRIVATE = "private"
    MIXED = "mixed"
    UNCLASSIFIED = "unclassified"
    UNUSED = "unused"


@dataclass(frozen=True, slots=True)
class GridNode:
    """One grid crossing used by an orthogonal circulation path."""

    x_index: int
    y_index: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class RouteCostBreakdown:
    """Cost components accumulated by one resolved route."""

    movement_cost: float
    perimeter_bias_cost: float
    turn_cost: float
    traffic_conflict_cost: float
    total_cost: float


@dataclass(frozen=True, slots=True)
class CirculationPathDetails:
    """DEBUG data for one expanded and resolved route."""

    rule_id: int
    rule_name: str
    traffic_class: TrafficClass
    destination_selection: DestinationSelection
    allowed_transit_room_types: tuple[RoomType, ...]
    importance_weight: float
    source_point_key: str
    source_room_id: str
    source_room_type: RoomType
    destination_point_key: str
    destination_room_id: str
    destination_room_type: RoomType
    nodes: tuple[GridNode, ...]
    step_count: int
    manhattan_step_count: int
    detour_step_count: int
    turn_count: int
    manhattan_reference_cost: float
    costs: RouteCostBreakdown
    diagnostic_score: float


@dataclass(frozen=True, slots=True)
class HallwayTrafficDetails:
    """Traffic totals and final role for one hallway hint point."""

    point_key: str
    room_id: str
    hint_index: int
    x: float
    y: float
    public_route_count: int
    private_route_count: int
    public_importance_weight: float
    private_importance_weight: float
    traffic_class: HallwayTrafficClass
    removed: bool


@dataclass(frozen=True, slots=True)
class RoutingPassDetails:
    """DEBUG snapshot of one routing and hallway-classification pass."""

    pass_number: int
    classifications_changed_from_previous: bool
    paths: tuple[CirculationPathDetails, ...]
    hallway_traffic: tuple[HallwayTrafficDetails, ...]


@dataclass(frozen=True, slots=True)
class RemovedHallwayPointDetails:
    """Identity and position of one hallway hint removed from the candidate."""

    point_key: str
    room_id: str
    hint_index: int
    x: float
    y: float
