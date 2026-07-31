# fpg_core\types\floor_plan_spec.py
from dataclasses import dataclass
from enum import Enum
from typing import NewType

# Canonical shared types used throughout the generation pipeline.

RoomId = NewType("RoomId", str)


class RoomType(str, Enum):
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    ATTACHED_BATHROOM = "attached_bathroom"
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    DINING_ROOM = "dining_room"
    HALLWAY = "hallway"
    VERANDA = "veranda"
    GARAGE = "garage"


class RoomWidthAxis(str, Enum):
    """Axis to which the room's width range applies."""

    ANY = "any"
    X = "x"
    Y = "y"


@dataclass(frozen=True)
class RoomSizeSpec:
    min_width: float
    max_width: float
    min_area: float
    max_area: float
    width_axis: RoomWidthAxis = RoomWidthAxis.ANY


@dataclass(frozen=True)
class RoomSpec:
    id: RoomId
    room_type: RoomType
    name: str
    size: RoomSizeSpec

    def __post_init__(self) -> None:
        if not isinstance(self.room_type, RoomType):
            raise TypeError("room_type must be a RoomType enum member")


@dataclass(frozen=True)
class FloorSpec:
    width: float
    length: float


class MatchPolicy(str, Enum):
    AND = "and"
    OR = "or"


class ConstraintStrength(str, Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class RoomRelationSpec:
    source_room_id: RoomId
    target_room_ids: tuple[RoomId, ...]
    match_policy: MatchPolicy
    strength: ConstraintStrength


# Main Type for floor plan generation specification
@dataclass(frozen=True)
class FloorPlanGenerationSpec:
    floor: FloorSpec
    rooms: tuple[RoomSpec, ...]
    room_relations: tuple[RoomRelationSpec, ...]
