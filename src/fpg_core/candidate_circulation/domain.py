from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain import (
    CirculationGridNode,
    CirculationTrafficClass,
    DestinationSelection,
    HallwayTrafficClass,
    RoomType,
    RouteCostBreakdown,
)

# Compatibility names retained at the feature boundary.
TrafficClass = CirculationTrafficClass
GridNode = CirculationGridNode


class HallwayRemovalReason(StrEnum):
    """Why a hallway hint was removed from the production candidate."""

    UNUSED = "unused"
    CONSOLIDATED = "consolidated"


class HallwayConsolidationDecision(StrEnum):
    """DEBUG result of testing one nearby hallway for safe removal."""

    REMOVED = "removed"
    KEPT_ROUTE_UNAVAILABLE = "kept_route_unavailable"
    KEPT_ROUTE_COVERAGE_CHANGED = "kept_route_coverage_changed"
    KEPT_ROUTE_COST_INCREASE = "kept_route_cost_increase"


@dataclass(frozen=True, slots=True)
class CirculationPathDetails:
    """DEBUG data for one expanded and resolved route."""

    rule_id: int
    rule_name: str
    traffic_class: CirculationTrafficClass
    destination_selection: DestinationSelection
    allowed_transit_room_types: tuple[RoomType, ...]
    required_transit_room_types: tuple[RoomType, ...]
    required_transit_point_keys: tuple[str, ...]
    importance_weight: float
    source_point_key: str
    source_room_id: str
    source_room_type: RoomType
    destination_point_key: str
    destination_room_id: str
    destination_room_type: RoomType
    nodes: tuple[CirculationGridNode, ...]
    step_count: int
    manhattan_step_count: int
    detour_step_count: int
    turn_count: int
    manhattan_reference_cost: float
    costs: RouteCostBreakdown
    path_efficiency_score: float


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
    removal_reason: HallwayRemovalReason | None


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
    reason: HallwayRemovalReason


@dataclass(frozen=True, slots=True)
class HallwayConsolidationAttemptDetails:
    """DEBUG record of one route-verified hallway consolidation attempt."""

    point_key: str
    nearby_point_keys: tuple[str, ...]
    decision: HallwayConsolidationDecision
    max_route_cost_increase_ratio: float | None
