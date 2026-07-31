# fpg_core\types\floor_plan.py
from dataclasses import dataclass, field
from enum import Enum
from typing import NewType

from .floor_plan_spec import RoomId, RoomType
from .geometry import Point, Polygon

OpeningId = NewType("OpeningId", str)


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"


class OpeningPurpose(str, Enum):
    ROOM_CONNECTION = "room_connection"
    MAIN_ENTRANCE = "main_entrance"
    SECONDARY_ENTRANCE = "secondary_entrance"
    DAYLIGHT = "daylight"


class RoomRole(str, Enum):
    STANDARD = "standard"
    SOLVER_PLACEHOLDER = "solver_placeholder"


@dataclass(frozen=True)
class RoomMetadata:
    """Typed post-solver provenance retained with a room."""

    source_room_ids: tuple[RoomId, ...] = ()
    applied_transformations: tuple[str, ...] = ()


@dataclass
class FloorPlanRoom:
    id: RoomId
    room_type: RoomType
    name: str
    boundary: Polygon
    role: RoomRole = RoomRole.STANDARD
    parent_room_id: RoomId | None = None
    metadata: RoomMetadata = field(default_factory=RoomMetadata)

    def __post_init__(self) -> None:
        if not isinstance(self.room_type, RoomType):
            raise TypeError("room_type must be a RoomType enum member")


@dataclass
class FloorPlanOpening:
    id: OpeningId
    opening_type: OpeningType
    purpose: OpeningPurpose
    start: Point
    end: Point
    connected_room_ids: tuple[RoomId, ...] = ()


@dataclass
class FloorPlan:
    boundary: Polygon
    rooms: list[FloorPlanRoom]
    openings: list[FloorPlanOpening] = field(default_factory=list)
    identity_redirects: dict[RoomId, RoomId] = field(default_factory=dict)
    applied_transformations: set[str] = field(default_factory=set)
