from __future__ import annotations

import math

from ...domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm, require_room_types
from ..geometry import exact_or_literal, violation_when_present


class KitchenBackExposureConstraint:
    """Prefer a qualifying kitchen back wall without removing hallway fallback."""

    key = "kitchen_back_exposure"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        room_types = require_room_types(
            settings.get("room_types", (RoomType.KITCHEN,)),
            "kitchen_back_exposure.room_types",
        )
        raw_minimum = float(settings.get("minimum_exposure", 10.0))
        if not math.isfinite(raw_minimum) or raw_minimum <= 0:
            raise InvalidProfileError(
                "kitchen_back_exposure.minimum_exposure must be positive and finite"
            )
        minimum = context.problem.scale.minimum_length(raw_minimum)
        if minimum > context.problem.floor.width:
            raise InvalidProfileError(
                "kitchen_back_exposure.minimum_exposure exceeds the floor width"
            )

        candidates = tuple(
            room
            for room in context.room_variables.values()
            if room.room.room_type in room_types
        )
        if not candidates:
            return ()

        qualifying = []
        for room in candidates:
            exposed = context.model.NewBoolVar(
                context.new_name("preferred_back_exposed", room.room.id_key)
            )
            context.model.AddImplication(exposed, room.present)
            context.model.Add(
                room.y_end == context.problem.floor.length
            ).OnlyEnforceIf(exposed)
            context.model.Add(room.width >= minimum).OnlyEnforceIf(exposed)
            qualifying.append(exposed)

        any_present = exact_or_literal(
            context,
            (room.present for room in candidates),
            "preferred_back_room_present",
        )
        any_qualifying = exact_or_literal(
            context,
            qualifying,
            "preferred_back_room_qualifies",
        )
        penalty = violation_when_present(
            context,
            any_qualifying,
            any_present,
            "kitchen_back_exposure_penalty",
        )
        return (
            PenaltyTerm(
                name="kitchen_back_exposure",
                expression=penalty,
            ),
        )
