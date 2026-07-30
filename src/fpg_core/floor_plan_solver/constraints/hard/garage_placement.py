from __future__ import annotations

from ...domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types


class GaragePlacementConstraint:
    """Place every present garage at the front-left or front-right corner.

    Project coordinate convention:

    - Front: minimum Y boundary
    - Left: minimum X boundary
    - Right: maximum X boundary

    Garage dimensions are not defined here. The prepared RoomSpec.size
    values are already enforced as hard constraints when room variables
    are created.
    """

    key = "garage_placement"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        garage_types = require_room_types(
            settings.get("garage_room_types", (RoomType.GARAGE,)),
            "garage_placement.garage_room_types",
        )

        for variables in context.room_variables.values():
            if variables.room.room_type not in garage_types:
                continue

            room_id = variables.room.id_key

            touches_left = context.model.NewBoolVar(
                context.new_name(
                    "garage_touches_left",
                    room_id,
                )
            )
            touches_right = context.model.NewBoolVar(
                context.new_name(
                    "garage_touches_right",
                    room_id,
                )
            )

            # A present garage must touch the front boundary.
            context.model.Add(variables.y == 0).OnlyEnforceIf(variables.present)

            # A present garage must select either the left or right edge.
            # An absent optional garage selects neither.
            context.model.Add(touches_left + touches_right == variables.present)

            # Front-left garage.
            context.model.Add(variables.x == 0).OnlyEnforceIf(touches_left)

            # Front-right garage.
            context.model.Add(
                variables.x_end == context.problem.floor.width
            ).OnlyEnforceIf(touches_right)
