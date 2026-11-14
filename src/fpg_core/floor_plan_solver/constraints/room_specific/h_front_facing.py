from __future__ import annotations

from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings


def clear_front(context, room):
    for other in context.room_variables.values():
        if other is room:
            continue
        left = context.model.NewBoolVar(context.new_name("front_clear_left"))
        right = context.model.NewBoolVar(context.new_name("front_clear_right"))
        behind = context.model.NewBoolVar(context.new_name("front_clear_behind"))
        context.model.Add(other.x_end <= room.x).OnlyEnforceIf(left)
        context.model.Add(other.x >= room.x_end).OnlyEnforceIf(right)
        context.model.Add(other.y >= room.y).OnlyEnforceIf(behind)
        context.model.AddBoolOr([left, right, behind, room.present.Not(), other.present.Not()])


class VerandaFrontConstraint:
    key = "veranda_front"

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        for room in context.room_variables.values():
            if room.room.room_type == RoomType.VERANDA:
                clear_front(context, room)


class LivingRoomFrontConstraint:
    key = "living_room_front"

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        rooms = context.room_variables.values()
        if any(room.room.room_type == RoomType.VERANDA for room in rooms):
            return
        for room in context.room_variables.values():
            if room.room.room_type == RoomType.LIVING_ROOM:
                clear_front(context, room)
