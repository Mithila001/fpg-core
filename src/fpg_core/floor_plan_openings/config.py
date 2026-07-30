from __future__ import annotations

from dataclasses import dataclass

from ..types import RoomType
from .exceptions import OpeningConfigurationError


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    coordinate_scale: int = 10
    tolerance: float = 1e-6
    corner_clearance: float = 0.0
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
    door_width: float = 8.0
    window_width: float = 16.0
    minimum_shared_wall: float = 10.0

    def __post_init__(self) -> None:
        if min(self.door_width, self.window_width, self.minimum_shared_wall) <= 0:
            raise OpeningConfigurationError("opening dimensions must be positive")


@dataclass(frozen=True, slots=True)
class FeaturePolicy:
    allowed_room_pairs: tuple[tuple[RoomType, RoomType], ...] = (
        (RoomType.BEDROOM, RoomType.LIVING_ROOM),
        (RoomType.KITCHEN, RoomType.LIVING_ROOM),
        (RoomType.BATHROOM, RoomType.LIVING_ROOM),
        (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
        (RoomType.VERANDA, RoomType.LIVING_ROOM),
        (RoomType.GARAGE, RoomType.LIVING_ROOM),
        (RoomType.GARAGE, RoomType.HALLWAY),
        (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
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
    )
    main_side_priority: tuple[str, ...] = ("south", "east", "north", "west")
    secondary_side_priority: tuple[str, ...] = (
        "north",
        "west",
        "east",
        "south",
    )
    window_side_priority: tuple[str, ...] = ("east", "north", "south", "west")

    def __post_init__(self) -> None:
        if any(cap < 1 for _, cap in self.room_door_caps):
            raise OpeningConfigurationError("room door caps must be positive")
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
        "window",
        "secondary_entrance",
        "other_interior",
        "preferred_hallway",
        "bathroom_hallway",
        "attached_bathroom",
        "main_entrance",
    )

    def __post_init__(self) -> None:
        if len(self.tier_order) != len(set(self.tier_order)):
            raise OpeningConfigurationError("objective tiers must be unique")
