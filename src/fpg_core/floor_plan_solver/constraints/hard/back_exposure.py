from __future__ import annotations

import math

from ....domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types


class BackExposureConstraint:
    """Require a sufficiently wide eligible room wall on the back boundary."""

    key = "back_exposure"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        room_types = require_room_types(
            settings.get(
                "room_types",
                (RoomType.HALLWAY, RoomType.KITCHEN),
            ),
            "back_exposure.room_types",
        )
        raw_minimum = float(settings.get("minimum_exposure", 10.0))
        if not math.isfinite(raw_minimum) or raw_minimum <= 0:
            raise InvalidProfileError(
                "back_exposure.minimum_exposure must be positive and finite"
            )
        minimum = context.problem.scale.minimum_length(raw_minimum)
        if minimum > context.problem.floor.width:
            raise InvalidProfileError(
                "back_exposure.minimum_exposure exceeds the floor width"
            )

        qualifying = []
        for room in context.room_variables.values():
            if room.room.room_type not in room_types:
                continue
            exposed = context.model.NewBoolVar(
                context.new_name("back_exposed", room.room.id_key)
            )
            context.model.AddImplication(exposed, room.present)
            context.model.Add(
                room.y_end == context.problem.floor.length
            ).OnlyEnforceIf(exposed)
            context.model.Add(room.width >= minimum).OnlyEnforceIf(exposed)
            qualifying.append(exposed)

        # This is intentionally infeasible when no eligible room can qualify.
        context.model.AddBoolOr(qualifying)
