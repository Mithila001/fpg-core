from __future__ import annotations

from ...domain import RoomType
from ...model import ModelContext, RoomVariables
from ..base import ConstraintSettings, require_room_types


class FrontAnchorConstraint:
    """Ensure only configured room types can occupy the front-most edge."""

    key = "front_anchor"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        allowed_types = require_room_types(
            settings.get(
                "anchor_room_types",
                (
                    RoomType.VERANDA,
                    RoomType.LIVING_ROOM,
                    RoomType.BEDROOM,
                    RoomType.GARAGE,
                ),
            ),
            "front_anchor.anchor_room_types",
        )
        all_rooms = tuple(context.room_variables.values())
        allowed_rooms: tuple[RoomVariables, ...] = tuple(
            room for room in all_rooms if room.room.room_type in allowed_types
        )

        # An empty BoolOr deliberately makes a specification with no eligible
        # front room infeasible.
        context.model.AddBoolOr([room.present for room in allowed_rooms])

        floor_length = context.problem.floor.length
        eligible_y_values = []
        for room in allowed_rooms:
            effective_y = context.model.NewIntVar(
                0,
                floor_length,
                context.new_name("front_effective_y", room.room.id_key),
            )
            context.model.Add(effective_y == room.y).OnlyEnforceIf(room.present)
            context.model.Add(effective_y == floor_length).OnlyEnforceIf(
                room.present.Not()
            )
            eligible_y_values.append(effective_y)

        front_y = context.model.NewIntVar(
            0,
            floor_length,
            context.new_name("front_y"),
        )
        if eligible_y_values:
            context.model.AddMinEquality(front_y, eligible_y_values)

        for room in all_rooms:
            if room.room.room_type in allowed_types:
                continue
            context.model.Add(room.y >= front_y + 1).OnlyEnforceIf(room.present)
