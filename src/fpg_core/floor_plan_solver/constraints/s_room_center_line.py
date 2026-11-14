from __future__ import annotations

from ..model import ModelContext
from .base import ConstraintSettings, PenaltyTerm
from .geometry import active_linear_penalty


class RoomCenterLineConstraint:
    """Prefer each room's center close to the floor's vertical center line."""

    key = "room_center_line"

    def build_penalties(self, context: ModelContext, settings: ConstraintSettings) -> tuple[PenaltyTerm, ...]:
        width = context.problem.floor.width
        penalties = []
        for room in context.room_variables.values():
            distance = context.model.NewIntVar(0, width, context.new_name("room_center_line_distance", room.room.id_key))
            context.model.AddAbsEquality(distance, 2 * room.x + room.width - width)
            penalty = active_linear_penalty(context, distance, width, room.present, "room_center_line_penalty")
            penalties.append(PenaltyTerm(name=f"room_center_line:{room.room.id_key}", expression=penalty))
        return tuple(penalties)
