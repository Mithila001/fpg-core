from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ..domain import (
    CirculationGrid,
    CirculationRouteRule,
    GridRoutingCostProfile,
    LandSide,
    RoomType,
)
from .types import EvaluatorCategory, EvaluatorKey

DEFAULT_VALID_ZONES: Mapping[RoomType, tuple[tuple[int, int], ...]] = MappingProxyType(
    {
        RoomType.VERANDA: ((1, 1), (2, 1), (3, 1)),
        RoomType.GARAGE: ((1, 1), (3, 1)),
        RoomType.KITCHEN: (
            (1, 1),
            (2, 1),
            (3, 1),
            (1, 2),
            (3, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        ),
        RoomType.HALLWAY: (
            (1, 2),
            (2, 2),
            (3, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        ),
        RoomType.LIVING_ROOM: (
            (1, 1),
            (2, 1),
            (3, 1),
            (1, 2),
            (2, 2),
            (3, 2),
        ),
        RoomType.BATHROOM: (
            (1, 1),
            (2, 1),
            (3, 1),
            (1, 2),
            (3, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        ),
    }
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ZoneSuitabilityConfig:
    """Typed caller configuration for zone-suitability scoring."""

    grid_size: int = 3
    falloff_multiplier: float = 1.5
    valid_zones: Mapping[RoomType, tuple[tuple[int, int], ...]] = field(
        default_factory=lambda: DEFAULT_VALID_ZONES
    )

    def __post_init__(self) -> None:
        if isinstance(self.grid_size, bool) or not isinstance(self.grid_size, int):
            raise TypeError("grid_size must be an integer.")
        if self.grid_size <= 0:
            raise ValueError("grid_size must be greater than zero.")

        if isinstance(self.falloff_multiplier, bool):
            raise TypeError("falloff_multiplier must be numeric, not boolean.")
        try:
            falloff_multiplier = float(self.falloff_multiplier)
        except (TypeError, ValueError) as exc:
            raise TypeError("falloff_multiplier must be numeric.") from exc
        if not math.isfinite(falloff_multiplier) or falloff_multiplier <= 0:
            raise ValueError("falloff_multiplier must be positive and finite.")

        if not isinstance(self.valid_zones, Mapping):
            raise TypeError("valid_zones must be a mapping.")

        normalized: dict[RoomType, tuple[tuple[int, int], ...]] = {}
        for room_type, raw_cells in self.valid_zones.items():
            if not isinstance(room_type, RoomType):
                raise TypeError("Every valid_zones key must be a RoomType member.")
            if isinstance(raw_cells, (str, bytes)) or not isinstance(
                raw_cells, Sequence
            ):
                raise TypeError(
                    f"Valid-zone cells for '{room_type.value}' must be a sequence."
                )

            cells: list[tuple[int, int]] = []
            for raw_cell in raw_cells:
                if isinstance(raw_cell, (str, bytes)) or not isinstance(
                    raw_cell, Sequence
                ):
                    raise TypeError(
                        f"Zone cell for '{room_type.value}' must be a coordinate pair."
                    )
                if len(raw_cell) != 2:
                    raise ValueError(
                        f"Zone cell for '{room_type.value}' must contain two coordinates."
                    )

                cell_x, cell_y = raw_cell
                if (
                    isinstance(cell_x, bool)
                    or not isinstance(cell_x, int)
                    or isinstance(cell_y, bool)
                    or not isinstance(cell_y, int)
                ):
                    raise TypeError(
                        f"Zone cell for '{room_type.value}' must use integer coordinates."
                    )
                if not 1 <= cell_x <= self.grid_size or not 1 <= cell_y <= self.grid_size:
                    raise ValueError(
                        f"Zone cell {(cell_x, cell_y)} for '{room_type.value}' "
                        f"is outside the 1..{self.grid_size} grid."
                    )
                cells.append((cell_x, cell_y))

            if len(cells) != len(set(cells)):
                raise ValueError(
                    f"Valid-zone cells for '{room_type.value}' must be unique."
                )
            normalized[room_type] = tuple(cells)

        object.__setattr__(self, "falloff_multiplier", falloff_multiplier)
        object.__setattr__(self, "valid_zones", MappingProxyType(normalized))


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
class RelationshipQualityConfig:
    """Typed single-pass routing configuration for relationship scoring."""

    grid: CirculationGrid
    costs: GridRoutingCostProfile
    route_rules: tuple[CirculationRouteRule, ...]
    always_traversable_room_types: tuple[RoomType, ...] = (RoomType.HALLWAY,)

    def __post_init__(self) -> None:
        if not isinstance(self.grid, CirculationGrid):
            raise TypeError("grid must be a CirculationGrid instance.")
        if not isinstance(self.costs, GridRoutingCostProfile):
            raise TypeError("costs must be a GridRoutingCostProfile instance.")

        route_rules = tuple(self.route_rules)
        if not route_rules:
            raise ValueError("At least one relationship route rule is required.")
        if any(not isinstance(rule, CirculationRouteRule) for rule in route_rules):
            raise TypeError("Every route rule must be a CirculationRouteRule.")
        rule_ids = [rule.id for rule in route_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Relationship route rule IDs must be unique.")

        always_traversable = tuple(self.always_traversable_room_types)
        if any(not isinstance(room_type, RoomType) for room_type in always_traversable):
            raise TypeError(
                "Every always_traversable_room_type must be a RoomType member."
            )
        if len(always_traversable) != len(set(always_traversable)):
            raise ValueError("always_traversable_room_types must be unique.")

        object.__setattr__(self, "route_rules", route_rules)
        object.__setattr__(
            self,
            "always_traversable_room_types",
            always_traversable,
        )


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
