from __future__ import annotations


from ....domain import RoomType
from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm, require_room_types
from .h_hallway_shared_wall import _interval_overlap


class HallwayEfficiencyConstraint:
    """Prefer a compact hallway system without making compactness mandatory.

    The objective evaluates all configured hallway rooms together. It can:

    - penalize total hallway area; and
    - penalize hallway wall length that is not shared with another room.

    The constraint never removes hallway rooms and does not decide whether a
    hallway is semantically necessary. Existing hard constraints remain
    responsible for feasibility and connectivity.
    """

    key = "hallway_efficiency"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        hallway_types = require_room_types(
            settings.get("hallway_room_types", (RoomType.HALLWAY,)),
            "hallway_efficiency.hallway_room_types",
        )
        area_penalty_multiplier = self._non_negative_int(
            settings.get("area_penalty_multiplier", 1),
            "hallway_efficiency.area_penalty_multiplier",
        )
        hallways = tuple(
            variables
            for variables in context.room_variables.values()
            if variables.room.room_type in hallway_types
        )
        if not hallways:
            return ()

        penalties: list[PenaltyTerm] = []

        if area_penalty_multiplier > 0:
            penalties.append(
                PenaltyTerm(
                    name="hallway_efficiency:total_area",
                    expression=sum(hallway.area for hallway in hallways),
                    multiplier=area_penalty_multiplier,
                )
            )

        for hallway in hallways:
            perimeter = 2 * (hallway.width + hallway.length)
            shared = []
            for other in context.room_variables.values():
                if other is hallway:
                    continue
                x_overlap = _interval_overlap(context, hallway.x, hallway.x_end, other.x, other.x_end, context.problem.floor.width, "wall_x_overlap", hallway, other)
                y_overlap = _interval_overlap(context, hallway.y, hallway.y_end, other.y, other.y_end, context.problem.floor.length, "wall_y_overlap", hallway, other)
                for first_face, second_face, overlap in ((hallway.x, other.x_end, y_overlap), (hallway.x_end, other.x, y_overlap), (hallway.y, other.y_end, x_overlap), (hallway.y_end, other.y, x_overlap)):
                    touching = context.model.NewBoolVar(context.new_name("hallway_wall_touch"))
                    context.model.Add(first_face == second_face).OnlyEnforceIf(touching)
                    context.model.Add(first_face != second_face).OnlyEnforceIf(touching.Not())
                    amount = context.model.NewIntVar(0, max(context.problem.floor.width, context.problem.floor.length), context.new_name("shared_wall_length"))
                    context.model.Add(amount == overlap).OnlyEnforceIf(touching)
                    context.model.Add(amount == 0).OnlyEnforceIf(touching.Not())
                    shared.append(amount)
            exposed = context.model.NewIntVar(0, 2 * (context.problem.floor.width + context.problem.floor.length), context.new_name("hallway_exposed_wall"))
            context.model.Add(exposed == perimeter - sum(shared))
            penalties.append(PenaltyTerm(name=f"hallway_efficiency:exposed_wall:{hallway.room.id_key}", expression=exposed))

        return tuple(penalties)

    @staticmethod
    def _non_negative_int(value: object, label: str) -> int:
        if isinstance(value, bool):
            raise InvalidProfileError(f"{label} must be a non-negative integer")
        if not isinstance(value, (int, float, str, bytes, bytearray)):
            raise InvalidProfileError(f"{label} must be a non-negative integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidProfileError(
                f"{label} must be a non-negative integer"
            ) from exc
        if parsed != value or parsed < 0:
            raise InvalidProfileError(f"{label} must be a non-negative integer")
        return parsed
