"""Shared default size ordering policy; consumers own evaluation and weights."""

from .floor_plan_spec import RoomType

DEFAULT_ROOM_SIZE_PAIRS = tuple(
    (compared, reference)
    for compared in (RoomType.BATHROOM, RoomType.ATTACHED_BATHROOM)
    for reference in (
        RoomType.BEDROOM, RoomType.LIVING_ROOM, RoomType.DINING_ROOM,
        RoomType.KITCHEN, RoomType.GARAGE,
    )
) + (
    (RoomType.BEDROOM, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.LIVING_ROOM),
)

DEFAULT_ROOM_SIZE_MAX_RATIO = 1.0
