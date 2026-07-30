from __future__ import annotations

from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, PenaltyTerm
from ..geometry import active_linear_penalty


class SeedStabilityConstraint:
    """Penalize movement and resizing away from the prepared seed layout."""

    key = "seed_stability"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        seed = context.problem.seed
        if seed is None:
            return ()

        position_multiplier = int(settings.get("position_multiplier", 1))
        size_multiplier = int(settings.get("size_multiplier", 1))
        if position_multiplier < 0 or size_multiplier < 0:
            raise InvalidProfileError(
                "seed_stability multipliers cannot be negative"
            )
        if position_multiplier == 0 and size_multiplier == 0:
            return ()

        floor = context.problem.floor
        penalties: list[PenaltyTerm] = []
        for room_id_key, room_seed in seed.rooms.items():
            variables = context.room_variables.get(room_id_key)
            if variables is None:
                continue

            x_delta = context.model.NewIntVar(
                0, floor.width, context.new_name("seed_x_delta", room_id_key)
            )
            y_delta = context.model.NewIntVar(
                0, floor.length, context.new_name("seed_y_delta", room_id_key)
            )
            context.model.AddAbsEquality(x_delta, variables.x - room_seed.x)
            context.model.AddAbsEquality(y_delta, variables.y - room_seed.y)

            expression = position_multiplier * (x_delta + y_delta)
            upper_bound = position_multiplier * (floor.width + floor.length)

            if room_seed.width is not None:
                width_delta = context.model.NewIntVar(
                    0,
                    floor.width,
                    context.new_name("seed_width_delta", room_id_key),
                )
                context.model.AddAbsEquality(
                    width_delta, variables.width - room_seed.width
                )
                expression += size_multiplier * width_delta
                upper_bound += size_multiplier * floor.width

            if room_seed.length is not None:
                length_delta = context.model.NewIntVar(
                    0,
                    floor.length,
                    context.new_name("seed_length_delta", room_id_key),
                )
                context.model.AddAbsEquality(
                    length_delta, variables.length - room_seed.length
                )
                expression += size_multiplier * length_delta
                upper_bound += size_multiplier * floor.length

            penalty = active_linear_penalty(
                context,
                expression,
                upper_bound,
                variables.present,
                f"seed_stability_penalty_{room_id_key}",
            )
            penalties.append(
                PenaltyTerm(
                    name=f"seed_stability:{room_id_key}",
                    expression=penalty,
                )
            )

        return tuple(penalties)
