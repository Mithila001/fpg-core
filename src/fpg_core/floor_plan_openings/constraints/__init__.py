from .shared import (
    RequiredRoomAccessConstraint,
    RoomDoorLimitConstraint,
    SharedPlacementConstraint,
)

OPENING_CONSTRAINT_TYPES = (
    SharedPlacementConstraint,
    RoomDoorLimitConstraint,
    RequiredRoomAccessConstraint,
)

OPENING_CONSTRAINT_IDS = frozenset(
    constraint_type.constraint_id for constraint_type in OPENING_CONSTRAINT_TYPES
)

STRUCTURAL_OPENING_CONSTRAINT_IDS = frozenset(
    {
        SharedPlacementConstraint.constraint_id,
        RequiredRoomAccessConstraint.constraint_id,
    }
)

__all__ = [
    "OPENING_CONSTRAINT_IDS",
    "OPENING_CONSTRAINT_TYPES",
    "STRUCTURAL_OPENING_CONSTRAINT_IDS",
    "RequiredRoomAccessConstraint",
    "RoomDoorLimitConstraint",
    "SharedPlacementConstraint",
]
