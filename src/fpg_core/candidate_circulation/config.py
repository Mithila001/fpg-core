from __future__ import annotations

import math
from dataclasses import dataclass

from ..domain import CirculationRouteRule, GridRoutingCostProfile, RoomType

_MAX_ROUTING_PASSES = 10


@dataclass(frozen=True, slots=True)
class RoutingCostProfile(GridRoutingCostProfile):
    """Routing costs including the multi-pass hallway conflict penalty."""

    traffic_conflict_cost: float

    def __post_init__(self) -> None:
        GridRoutingCostProfile.__post_init__(self)
        if isinstance(self.traffic_conflict_cost, bool):
            raise TypeError("traffic_conflict_cost must be numeric, not boolean.")
        try:
            traffic_conflict_cost = float(self.traffic_conflict_cost)
        except (TypeError, ValueError) as exc:
            raise TypeError("traffic_conflict_cost must be numeric.") from exc
        if not math.isfinite(traffic_conflict_cost):
            raise ValueError("traffic_conflict_cost must be finite.")
        if traffic_conflict_cost <= 0:
            raise ValueError("traffic_conflict_cost must be greater than zero.")
        if traffic_conflict_cost > 1_000_000_000_000.0:
            raise ValueError(
                "traffic_conflict_cost exceeds the numerical safety limit."
            )
        object.__setattr__(self, "traffic_conflict_cost", traffic_conflict_cost)


@dataclass(frozen=True, slots=True)
class CandidateCirculationConfig:
    """Reusable routing policy; request-specific grid comes from CandidateMap."""

    costs: RoutingCostProfile
    route_rules: tuple[CirculationRouteRule, ...]
    always_traversable_room_types: tuple[RoomType, ...]
    max_routing_passes: int = 3

    def __post_init__(self) -> None:
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
            self.max_routing_passes, int
        ):
            raise TypeError("max_routing_passes must be an integer.")
        if self.max_routing_passes < 2:
            raise ValueError("max_routing_passes must be at least 2.")
        if self.max_routing_passes > _MAX_ROUTING_PASSES:
            raise ValueError(
                f"max_routing_passes cannot exceed {_MAX_ROUTING_PASSES}."
            )

        object.__setattr__(self, "route_rules", route_rules)
        object.__setattr__(
            self,
            "always_traversable_room_types",
            always_traversable,
        )


__all__ = [
    "CandidateCirculationConfig",
    "CirculationRouteRule",
    "RoutingCostProfile",
]
