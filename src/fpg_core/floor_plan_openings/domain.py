from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from ..types import (
    FloorPlanRoom,
    OpeningPurpose,
    OpeningType,
    RoomId,
)


class WallOrientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class WallKind(str, Enum):
    EXTERIOR = "exterior"
    SHARED = "shared"


class WallSide(str, Enum):
    SOUTH = "south"
    EAST = "east"
    NORTH = "north"
    WEST = "west"


@dataclass(frozen=True, slots=True)
class AnalyzedWall:
    id: str
    orientation: WallOrientation
    fixed_coordinate: int
    start: int
    end: int
    kind: WallKind
    room_ids: tuple[RoomId, ...]
    exterior_side: WallSide | None = None

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class PreparedFloorPlan:
    walls: tuple[AnalyzedWall, ...]
    rooms_by_id: Mapping[RoomId, FloorPlanRoom]
    scale: int

    def wall_by_id(self) -> dict[str, AnalyzedWall]:
        return {wall.id: wall for wall in self.walls}


@dataclass(frozen=True, slots=True)
class PlacementOption:
    id: str
    wall_id: str
    width: int
    preference_rank: int = 0
    undersized: bool = False


@dataclass(frozen=True, slots=True)
class OpeningDemand:
    id: str
    feature_id: str
    opening_type: OpeningType
    purpose: OpeningPurpose
    room_ids: tuple[RoomId, ...]
    options: tuple[PlacementOption, ...]
    objective_tier: str
    category: str
