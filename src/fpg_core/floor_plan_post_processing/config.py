from __future__ import annotations

from dataclasses import dataclass

from ..types import RoomType


@dataclass(frozen=True)
class VerandaAdjustmentConfig:
    transformation_version: str = "veranda_adjustment:v1"


@dataclass(frozen=True)
class WallExtensionRule:
    room_type: RoomType
    min_wall_length: float
    max_wall_length: float
    max_rooms: int
    max_selections: int
    expansion_percentage: float
    max_distance: float


@dataclass(frozen=True)
class WallExtensionConfig:
    rules: tuple[WallExtensionRule, ...] = (
        WallExtensionRule(RoomType.VERANDA, 10, 50, 3, 1, 0.80, 40),
        WallExtensionRule(RoomType.LIVING_ROOM, 10, 40, 1, 2, 0.80, 20),
        WallExtensionRule(RoomType.KITCHEN, 10, 40, 1, 1, 0.80, 10),
        WallExtensionRule(RoomType.HALLWAY, 5, 50, 3, 3, 0.80, 2),
        WallExtensionRule(RoomType.BEDROOM, 10, 40, 3, 1, 0.80, 10),
    )
    transformation_version: str = "wall_extension:v1"


@dataclass(frozen=True)
class PlaceholderRemovalConfig:
    pass


@dataclass(frozen=True)
class HallwayMergeConfig:
    minimum_shared_wall: float = 10.0


@dataclass(frozen=True)
class GridSnapConfig:
    grid_size: float | None = None


@dataclass(frozen=True)
class RectilinearSimplificationConfig:
    pass
