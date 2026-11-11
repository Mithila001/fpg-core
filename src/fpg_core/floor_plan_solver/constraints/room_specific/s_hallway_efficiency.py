from __future__ import annotations

import math

from ....domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm, require_room_types


class HallwayEfficiencyConstraint:
    """Prefer a compact hallway system without making compactness mandatory.

    The objective evaluates all configured hallway rooms together. It can:

    - penalize total hallway area; and
    - add an extra penalty when a hallway's longest side exceeds a preferred
      maximum length.

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
        excess_length_penalty_multiplier = self._non_negative_int(
            settings.get("excess_length_penalty_multiplier", 5),
            "hallway_efficiency.excess_length_penalty_multiplier",
        )

        raw_preferred_max_length = settings.get("preferred_max_length", 40.0)
        preferred_max_length: int | None
        if raw_preferred_max_length is None:
            preferred_max_length = None
        else:
            try:
                preferred_max_length_value = float(raw_preferred_max_length)
            except (TypeError, ValueError) as exc:
                raise InvalidProfileError(
                    "hallway_efficiency.preferred_max_length must be numeric or None"
                ) from exc
            if (
                not math.isfinite(preferred_max_length_value)
                or preferred_max_length_value <= 0
            ):
                raise InvalidProfileError(
                    "hallway_efficiency.preferred_max_length must be positive and finite"
                )
            preferred_max_length = context.problem.scale.minimum_length(
                preferred_max_length_value
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

        if excess_length_penalty_multiplier > 0 and preferred_max_length is not None:
            floor = context.problem.floor
            max_longest_side = max(floor.width, floor.length)
            excess_lengths = []

            for hallway in hallways:
                longest_side = context.model.NewIntVar(
                    0,
                    max_longest_side,
                    context.new_name(
                        "hallway_longest_side",
                        hallway.room.id_key,
                    ),
                )
                context.model.AddMaxEquality(
                    longest_side,
                    [hallway.width, hallway.length],
                )

                excess_length = context.model.NewIntVar(
                    0,
                    max_longest_side,
                    context.new_name(
                        "hallway_excess_length",
                        hallway.room.id_key,
                    ),
                )
                context.model.AddMaxEquality(
                    excess_length,
                    [longest_side - preferred_max_length, 0],
                )
                excess_lengths.append(excess_length)

            penalties.append(
                PenaltyTerm(
                    name="hallway_efficiency:excess_length",
                    expression=sum(excess_lengths),
                    multiplier=excess_length_penalty_multiplier,
                )
            )

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
