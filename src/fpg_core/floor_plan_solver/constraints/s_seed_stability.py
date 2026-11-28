from __future__ import annotations

from fractions import Fraction
from math import isfinite

from ..exceptions import InvalidProfileError
from ..model import ModelContext
from .base import PENALTY_MAX, ConstraintSettings, average_penalties, ceil_ratio


class SeedStabilityConstraint:
    """Penalize movement and resizing away from the prepared seed layout."""

    key = "seed_stability"

    def build_penalty(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ):
        seed = context.problem.seed
        if seed is None:
            return 0

        multipliers = []
        for name in ("position_multiplier", "size_multiplier"):
            value = settings.get(name, 1)
            if (
                type(value) not in (int, float)
                or value < 0
                or (isinstance(value, float) and not isfinite(value))
            ):
                raise InvalidProfileError(
                    f"{self.key}.{name} must be finite and non-negative"
                )
            multipliers.append(Fraction(str(value)))

        position_share, size_share = multipliers
        if position_share and size_share:
            # CP-SAT needs integer coefficients. Preserve the relative balance.
            ratio = position_share / size_share
            position_multiplier, size_multiplier = ratio.numerator, ratio.denominator
            if position_multiplier + size_multiplier > 2**40:
                raise InvalidProfileError(
                    f"{self.key} multiplier ratio is too precise for the solver"
                )
        else:
            position_multiplier, size_multiplier = (
                int(bool(position_share)),
                int(bool(size_share)),
            )

        if position_multiplier == 0 and size_multiplier == 0:
            return 0

        floor = context.problem.floor
        penalties = []
        for room_id_key, room_seed in seed.rooms.items():
            variables = context.room_variables.get(room_id_key)
            if variables is None:
                continue

            centered = room_seed.center_x is not None and room_seed.center_y is not None
            factor = 2 if centered else 1
            x_delta = context.model.NewIntVar(
                0, factor * floor.width, context.new_name("seed_x_delta", room_id_key)
            )
            y_delta = context.model.NewIntVar(
                0, factor * floor.length, context.new_name("seed_y_delta", room_id_key)
            )
            context.model.AddAbsEquality(
                x_delta,
                2 * variables.x + variables.width - 2 * room_seed.center_x
                if centered
                else variables.x - room_seed.x,
            )
            context.model.AddAbsEquality(
                y_delta,
                2 * variables.y + variables.length - 2 * room_seed.center_y
                if centered
                else variables.y - room_seed.y,
            )

            components = []
            if position_multiplier:
                position = ceil_ratio(
                    context,
                    PENALTY_MAX * (x_delta * floor.length + y_delta * floor.width),
                    factor * 2 * floor.width * floor.length,
                    PENALTY_MAX,
                )
                components.append((position, position_multiplier))
            if size_multiplier:
                sizes = []
                for value, seed_value, span in (
                    (variables.width, room_seed.width, floor.width),
                    (variables.length, room_seed.length, floor.length),
                ):
                    if seed_value is not None:
                        delta = context.model.NewIntVar(
                            0, span, context.new_name("seed_size_delta")
                        )
                        context.model.AddAbsEquality(delta, value - seed_value)
                        sizes.append(
                            (
                                ceil_ratio(
                                    context, PENALTY_MAX * delta, span, PENALTY_MAX
                                ),
                                1,
                            )
                        )
                if sizes:
                    components.append(
                        (average_penalties(context, sizes), size_multiplier)
                    )
            if components:
                penalties.append((average_penalties(context, components), 1))
        return average_penalties(context, penalties)
