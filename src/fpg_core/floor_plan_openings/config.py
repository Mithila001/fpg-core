from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Literal

from ..domain import RoomType
from .constraints import (
    OPENING_CONSTRAINT_IDS,
    STRUCTURAL_OPENING_CONSTRAINT_IDS,
)
from .exceptions import OpeningConfigurationError


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    coordinate_scale: int = 10
    tolerance: float = 1e-6
    corner_clearance: float = 5.0
    window_spacing: float = 5.0

    def __post_init__(self) -> None:
        if self.coordinate_scale < 1:
            raise OpeningConfigurationError("coordinate_scale must be at least 1")
        if self.tolerance <= 0:
            raise OpeningConfigurationError("tolerance must be positive")
        if self.corner_clearance < 0 or self.window_spacing < 0:
            raise OpeningConfigurationError("clearances cannot be negative")


@dataclass(frozen=True, slots=True)
class DimensionConfig:
    door_width: float = 10.0
    window_width: float = 16.0
    minimum_shared_wall: float = 10.0

    def __post_init__(self) -> None:
        if min(self.door_width, self.window_width, self.minimum_shared_wall) <= 0:
            raise OpeningConfigurationError("opening dimensions must be positive")


_DEFAULT_ALLOWED_ROOM_PAIRS: tuple[tuple[RoomType, RoomType], ...] = (
    (RoomType.BEDROOM, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.DINING_ROOM),
    (RoomType.BATHROOM, RoomType.LIVING_ROOM),
    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
    (RoomType.VERANDA, RoomType.LIVING_ROOM),
    (RoomType.GARAGE, RoomType.LIVING_ROOM),
    (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
    # These explicit hallway pairs preserve the previous behavior where hallway
    # connections were implicitly allowed by the implementation.
    (RoomType.BEDROOM, RoomType.HALLWAY),
    (RoomType.BATHROOM, RoomType.HALLWAY),
    (RoomType.LIVING_ROOM, RoomType.HALLWAY),
    (RoomType.KITCHEN, RoomType.HALLWAY),
    (RoomType.DINING_ROOM, RoomType.HALLWAY),
    (RoomType.VERANDA, RoomType.HALLWAY),
    (RoomType.GARAGE, RoomType.HALLWAY),
    (RoomType.HALLWAY, RoomType.HALLWAY),
)


@dataclass(frozen=True, slots=True)
class InteriorDoorPolicy:
    door_width: float = 10.0
    preferred_clearance: float = 5.0
    minimum_clearance: float = 0.0
    minimum_shared_wall: float = 10.0
    placement_preference: Literal["wall_end", "center"] = "wall_end"

    def __post_init__(self) -> None:
        values = (
            self.door_width,
            self.preferred_clearance,
            self.minimum_clearance,
            self.minimum_shared_wall,
        )
        if (
            not all(isfinite(value) for value in values)
            or self.door_width <= 0
            or self.minimum_shared_wall <= 0
        ):
            raise OpeningConfigurationError(
                "interior door dimensions must be finite and positive"
            )
        if (
            self.minimum_clearance < 0
            or self.preferred_clearance < self.minimum_clearance
        ):
            raise OpeningConfigurationError(
                "preferred clearance must be at least the non-negative minimum"
            )
        if self.placement_preference not in {"wall_end", "center"}:
            raise OpeningConfigurationError(
                "unknown interior door placement preference"
            )


@dataclass(frozen=True, slots=True)
class InteriorDoorConfig:
    default: InteriorDoorPolicy = field(default_factory=InteriorDoorPolicy)
    overrides: tuple[tuple[RoomType, InteriorDoorPolicy], ...] = field(
        default_factory=lambda: (
            (RoomType.BATHROOM, InteriorDoorPolicy(8.0, 2.0, 0.0, 8.0, "center")),
            (
                RoomType.ATTACHED_BATHROOM,
                InteriorDoorPolicy(8.0, 2.0, 0.0, 8.0, "center"),
            ),
        )
    )

    def __post_init__(self) -> None:
        types = [room_type for room_type, _ in self.overrides]
        if any(not isinstance(room_type, RoomType) for room_type in types) or len(
            types
        ) != len(set(types)):
            raise OpeningConfigurationError(
                "interior door overrides must have unique room types"
            )

    def resolve(self, room_types: tuple[RoomType, ...]) -> InteriorDoorPolicy:
        # The first configured override wins, independent of wall direction.
        return next(
            (policy for room_type, policy in self.overrides if room_type in room_types),
            self.default,
        )


@dataclass(frozen=True, slots=True)
class WindowPolicy:
    width: float = 16.0
    target_count: int = 1
    preferred_clearance: float = 5.0
    minimum_clearance: float = 0.0

    def __post_init__(self) -> None:
        if (
            not all(
                isfinite(v)
                for v in (self.width, self.preferred_clearance, self.minimum_clearance)
            )
            or self.width <= 0
        ):
            raise OpeningConfigurationError(
                "window dimensions must be finite and width positive"
            )
        if (
            type(self.target_count) is not int
            or self.target_count < 1
            or self.minimum_clearance < 0
            or self.preferred_clearance < self.minimum_clearance
        ):
            raise OpeningConfigurationError("invalid window count or clearances")


@dataclass(frozen=True, slots=True)
class FeaturePolicy:
    """Consumer-owned architectural policy for opening generation.

    `allowed_room_pairs` is authoritative: no room-type connection is silently
    added by the feature. `door_placement_priority` uses larger values for rooms
    whose usable wall corner should dominate door positioning.
    """

    allowed_room_pairs: tuple[tuple[RoomType, RoomType], ...] = (
        _DEFAULT_ALLOWED_ROOM_PAIRS
    )
    room_door_caps: tuple[tuple[RoomType, int], ...] = (
        (RoomType.BEDROOM, 2),
        (RoomType.BATHROOM, 1),
        (RoomType.LIVING_ROOM, 10),
        (RoomType.HALLWAY, 10),
        (RoomType.KITCHEN, 1),
        (RoomType.ATTACHED_BATHROOM, 1),
        (RoomType.VERANDA, 1),
        (RoomType.GARAGE, 1),
        (RoomType.DINING_ROOM, 2),
    )
    secondary_room_priority: tuple[RoomType, ...] = (
        RoomType.KITCHEN,
        RoomType.HALLWAY,
    )
    window_room_types: tuple[RoomType, ...] = (
        RoomType.BEDROOM,
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.BATHROOM,
        RoomType.ATTACHED_BATHROOM,
    )
    window_policies: tuple[tuple[RoomType, WindowPolicy], ...] = field(
        default_factory=lambda: (
            (RoomType.BEDROOM, WindowPolicy()),
            (RoomType.LIVING_ROOM, WindowPolicy()),
            (RoomType.KITCHEN, WindowPolicy()),
            (RoomType.DINING_ROOM, WindowPolicy()),
            (RoomType.BATHROOM, WindowPolicy(5.0, 1, 2.0, 0.0)),
            (RoomType.ATTACHED_BATHROOM, WindowPolicy(5.0, 1, 2.0, 0.0)),
        )
    )
    normal_connection_caps: tuple[tuple[RoomType, int], ...] = (
        (RoomType.BEDROOM, 1),
        (RoomType.KITCHEN, 1),
        (RoomType.BATHROOM, 1),
        (RoomType.ATTACHED_BATHROOM, 1),
    )
    prevent_duplicate_connections: bool = True
    main_side_priority: tuple[str, ...] = ("south", "east", "north", "west")
    secondary_side_priority: tuple[str, ...] = (
        "north",
        "west",
        "east",
        "south",
    )
    window_side_priority: tuple[str, ...] = ("east", "north", "south", "west")
    required_access_room_types: tuple[RoomType, ...] = (
        RoomType.BEDROOM,
        RoomType.BATHROOM,
        RoomType.ATTACHED_BATHROOM,
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.HALLWAY,
        RoomType.VERANDA,
        RoomType.GARAGE,
    )
    door_placement_priority: tuple[tuple[RoomType, int], ...] = (
        (RoomType.BEDROOM, 100),
        (RoomType.BATHROOM, 100),
        (RoomType.ATTACHED_BATHROOM, 100),
        (RoomType.KITCHEN, 80),
        (RoomType.DINING_ROOM, 60),
        (RoomType.GARAGE, 60),
        (RoomType.VERANDA, 40),
        (RoomType.LIVING_ROOM, 20),
        (RoomType.HALLWAY, 10),
    )

    def __post_init__(self) -> None:
        for name, entries in (
            ("window policies", self.window_policies),
            ("normal connection caps", self.normal_connection_caps),
        ):
            types = [room_type for room_type, _ in entries]
            if any(not isinstance(room_type, RoomType) for room_type in types) or len(
                types
            ) != len(set(types)):
                raise OpeningConfigurationError(f"{name} must have unique room types")
        if any(cap < 1 for _, cap in self.normal_connection_caps):
            raise OpeningConfigurationError("normal connection caps must be positive")
        if any(
            not isinstance(policy, WindowPolicy) for _, policy in self.window_policies
        ):
            raise OpeningConfigurationError(
                "window policies must be WindowPolicy values"
            )
        normalized_pairs = [frozenset(pair) for pair in self.allowed_room_pairs]
        if len(normalized_pairs) != len(set(normalized_pairs)):
            raise OpeningConfigurationError("allowed room pairs must be unique")

        cap_types = [room_type for room_type, _ in self.room_door_caps]
        if len(cap_types) != len(set(cap_types)):
            raise OpeningConfigurationError(
                "room door caps must define each room type once"
            )
        if any(cap < 1 for _, cap in self.room_door_caps):
            raise OpeningConfigurationError("room door caps must be positive")

        if len(self.required_access_room_types) != len(
            set(self.required_access_room_types)
        ):
            raise OpeningConfigurationError("required access room types must be unique")

        priority_types = [room_type for room_type, _ in self.door_placement_priority]
        if len(priority_types) != len(set(priority_types)):
            raise OpeningConfigurationError(
                "door placement priorities must define each room type once"
            )
        if any(priority < 0 for _, priority in self.door_placement_priority):
            raise OpeningConfigurationError(
                "door placement priorities cannot be negative"
            )

        valid_sides = {"south", "east", "north", "west"}
        for priority in (
            self.main_side_priority,
            self.secondary_side_priority,
            self.window_side_priority,
        ):
            if set(priority) != valid_sides or len(priority) != 4:
                raise OpeningConfigurationError(
                    "side priorities must contain each cardinal side exactly once"
                )

    @property
    def cap_by_room_type(self) -> dict[RoomType, int]:
        return dict(self.room_door_caps)

    @property
    def door_priority_by_room_type(self) -> dict[RoomType, int]:
        return dict(self.door_placement_priority)


@dataclass(frozen=True, slots=True)
class SolverConfig:
    max_time_seconds: float = 10.0
    num_search_workers: int = 1
    random_seed: int = 0
    cp_model_presolve: bool = True
    log_search_progress: bool = False

    def __post_init__(self) -> None:
        if self.max_time_seconds <= 0:
            raise OpeningConfigurationError("max_time_seconds must be positive")
        if self.num_search_workers < 1:
            raise OpeningConfigurationError("num_search_workers must be positive")
        if self.random_seed < 0:
            raise OpeningConfigurationError("random_seed cannot be negative")


@dataclass(frozen=True, slots=True)
class ObjectiveConfig:
    tier_order: tuple[str, ...] = (
        "other_interior",
        "preferred_hallway",
        "bathroom_hallway",
        "attached_bathroom",
        "window",
        "secondary_entrance",
        "main_entrance",
    )

    def __post_init__(self) -> None:
        if len(self.tier_order) != len(set(self.tier_order)):
            raise OpeningConfigurationError("objective tiers must be unique")


@dataclass(frozen=True, slots=True)
class FloorPlanOpeningsConfig:
    """Reusable configuration controlling opening generation behavior."""

    name: str
    enabled_features: tuple[str, ...] = (
        "interior_doors",
        "exterior_doors",
        "windows",
    )
    enabled_constraints: tuple[str, ...] = (
        "shared_placement",
        "room_door_limits",
        "required_room_access",
    )
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    dimensions: DimensionConfig = field(default_factory=DimensionConfig)
    policy: FeaturePolicy = field(default_factory=FeaturePolicy)
    objective: ObjectiveConfig = field(default_factory=ObjectiveConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    interior_doors: InteriorDoorConfig = field(default_factory=InteriorDoorConfig)

    def window_policy(self, room_type: RoomType) -> WindowPolicy:
        return dict(self.policy.window_policies).get(
            room_type,
            WindowPolicy(
                self.dimensions.window_width, 1, self.geometry.corner_clearance, 0.0
            ),
        )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise OpeningConfigurationError("configuration name cannot be empty")
        if len(self.enabled_features) != len(set(self.enabled_features)):
            raise OpeningConfigurationError("enabled feature IDs must be unique")
        if len(self.enabled_constraints) != len(set(self.enabled_constraints)):
            raise OpeningConfigurationError("enabled constraint IDs must be unique")
        unknown_constraints = set(self.enabled_constraints).difference(
            OPENING_CONSTRAINT_IDS
        )
        if unknown_constraints:
            raise OpeningConfigurationError(
                "unknown opening constraint IDs: "
                + ", ".join(sorted(unknown_constraints))
            )
        missing = STRUCTURAL_OPENING_CONSTRAINT_IDS.difference(self.enabled_constraints)
        if missing:
            raise OpeningConfigurationError(
                "structural opening-model constraints cannot be disabled: "
                + ", ".join(sorted(missing))
            )
