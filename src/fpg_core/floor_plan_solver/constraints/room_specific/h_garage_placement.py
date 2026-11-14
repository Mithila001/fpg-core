from __future__ import annotations

from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types
from .h_front_facing import clear_front


class GaragePlacementConstraint:
    """Keep the garage front and one side clear of other rooms."""

    key = "garage_placement"

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        types = require_room_types(settings.get("garage_room_types", (RoomType.GARAGE,)), "garage_placement.garage_room_types")
        for garage in context.room_variables.values():
            if garage.room.room_type not in types:
                continue
            clear_front(context, garage)
            left = context.model.NewBoolVar(context.new_name("garage_clear_left"))
            for other in context.room_variables.values():
                if other is garage:
                    continue
                right_of = context.model.NewBoolVar(context.new_name("garage_other_right"))
                left_of = context.model.NewBoolVar(context.new_name("garage_other_left"))
                behind = context.model.NewBoolVar(context.new_name("garage_other_behind"))
                context.model.Add(other.x >= garage.x_end).OnlyEnforceIf(right_of)
                context.model.Add(other.x_end <= garage.x).OnlyEnforceIf(left_of)
                context.model.Add(other.y >= garage.y_end).OnlyEnforceIf(behind)
                context.model.AddBoolOr([right_of, behind, left.Not(), garage.present.Not(), other.present.Not()])
                context.model.AddBoolOr([left_of, behind, left, garage.present.Not(), other.present.Not()])
