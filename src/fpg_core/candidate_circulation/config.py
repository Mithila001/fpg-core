from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..domain import CirculationRouteRule, GridRoutingCostProfile, RoomType

_MAX_ROUTING_PASSES = 10


@dataclass(frozen=True, slots=True)
class HallwayConsolidationConfig:
    """Controls conservative removal of redundant nearby hallway hints."""

    enabled: bool = True
    minimum_separation_grid_steps: float = 2.0
    max_route_cost_increase_ratio: float = 0.15

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean.")

        if isinstance(self.minimum_separation_grid_steps, bool):
            raise TypeError(
                "minimum_separation_grid_steps must be numeric, not boolean."
            )
        try:
            separation = float(self.minimum_separation_grid_steps)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "minimum_separation_grid_steps must be numeric."
            ) from exc
        if not math.isfinite(separation):
            raise ValueError("minimum_separation_grid_steps must be finite.")
        if separation <= 0:
            raise ValueError(
                "minimum_separation_grid_steps must be greater than zero."
            )
        if separation > 10.0:
            raise ValueError(
                "minimum_separation_grid_steps cannot exceed 10 grid steps."
            )

        if isinstance(self.max_route_cost_increase_ratio, bool):
            raise TypeError(
                "max_route_cost_increase_ratio must be numeric, not boolean."
            )
        try:
            cost_ratio = float(self.max_route_cost_increase_ratio)
        except (TypeError, ValueError) as exc:
            raise TypeError("max_route_cost_increase_ratio must be numeric.") from exc
        if not math.isfinite(cost_ratio):
            raise ValueError("max_route_cost_increase_ratio must be finite.")
        if not 0.0 <= cost_ratio <= 1.0:
            raise ValueError(
                "max_route_cost_increase_ratio must be between 0.0 and 1.0."
            )

        object.__setattr__(self, "minimum_separation_grid_steps", separation)
        object.__setattr__(self, "max_route_cost_increase_ratio", cost_ratio)


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
    hallway_consolidation: HallwayConsolidationConfig = field(
        default_factory=HallwayConsolidationConfig
    )

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

        if not isinstance(self.hallway_consolidation, HallwayConsolidationConfig):
            raise TypeError(
                "hallway_consolidation must be a HallwayConsolidationConfig instance."
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
    "HallwayConsolidationConfig",
    "RoutingCostProfile",
]
