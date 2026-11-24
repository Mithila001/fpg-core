from __future__ import annotations

from ..model import ModelContext
from .base import ConstraintSettings, PENALTY_MAX, ceil_ratio
from .geometry import active_linear_penalty


class RoomCenterLineConstraint:
    """Prefer each room's center close to the floor's vertical center line."""

    key = "room_center_line"

    def build_penalty(self, context: ModelContext, settings: ConstraintSettings):
        width = context.problem.floor.width
        penalties = []
        for room in context.room_variables.values():
            distance = context.model.NewIntVar(0, width, context.new_name("room_center_line_distance", room.room.id_key))
            context.model.AddAbsEquality(distance, 2 * room.x + room.width - width)
            penalty = active_linear_penalty(context, distance, width, room.present, "room_center_line_penalty")
            penalties.append(penalty)
        return ceil_ratio(context, PENALTY_MAX * sum(penalties), width * len(penalties), PENALTY_MAX) if penalties else 0
