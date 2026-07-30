from __future__ import annotations

from ...domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types


class HallwayDimensionsConstraint:
    """Keep one hallway dimension within the configured corridor-width range."""

    key = "hallway_dimensions"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        hallway_types = require_room_types(
            settings.get("hallway_room_types", (RoomType.HALLWAY,)),
            "hallway_dimensions.hallway_room_types",
        )
        minimum_width = int(settings.get("minimum_width", 8))
        maximum_width = int(settings.get("maximum_width", 10))

        if minimum_width <= 0:
            raise InvalidProfileError(
                "hallway_dimensions.minimum_width must be positive"
            )
        if maximum_width < minimum_width:
            raise InvalidProfileError(
                "hallway_dimensions.maximum_width must be greater than or "
                "equal to minimum_width"
            )

        for variables in context.room_variables.values():
            if variables.room.room_type not in hallway_types:
                continue

            horizontal = context.model.NewBoolVar(
                context.new_name(
                    "hallway_horizontal",
                    variables.room.id_key,
                )
            )
            vertical = context.model.NewBoolVar(
                context.new_name(
                    "hallway_vertical",
                    variables.room.id_key,
                )
            )

            # A present hallway chooses exactly one orientation. An absent
            # optional hallway chooses neither orientation.
            context.model.Add(horizontal + vertical == variables.present)

            # Horizontal hallway: length is the corridor width; room width may
            # extend as far as its prepared room-size bounds allow.
            context.model.Add(
                variables.length >= minimum_width
            ).OnlyEnforceIf(horizontal)
            context.model.Add(
                variables.length <= maximum_width
            ).OnlyEnforceIf(horizontal)

            # Vertical hallway: width is the corridor width; room length may
            # extend as far as its prepared room-size bounds allow.
            context.model.Add(
                variables.width >= minimum_width
            ).OnlyEnforceIf(vertical)
            context.model.Add(
                variables.width <= maximum_width
            ).OnlyEnforceIf(vertical)
