from __future__ import annotations

from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm, require_room_types
from ..geometry import active_linear_penalty


class BathroomDepthConstraint:
    """Prefer bathrooms farther from the front boundary (y = 0)."""

    key = "bathroom_depth"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        target_types = require_room_types(
            settings.get(
                "room_types",
                (RoomType.BATHROOM, RoomType.ATTACHED_BATHROOM),
            ),
            "bathroom_depth.room_types",
        )
        floor = context.problem.floor
        penalties: list[PenaltyTerm] = []

        for variables in context.room_variables.values():
            if variables.room.room_type not in target_types:
                continue
            expression = 2 * floor.length - (2 * variables.y + variables.length)
            penalty = active_linear_penalty(
                context,
                expression,
                2 * floor.length,
                variables.present,
                f"bathroom_depth_penalty_{variables.room.id_key}",
            )
            penalties.append(
                PenaltyTerm(
                    name=f"bathroom_depth:{variables.room.id_key}",
                    expression=penalty,
                )
            )

        return tuple(penalties)
