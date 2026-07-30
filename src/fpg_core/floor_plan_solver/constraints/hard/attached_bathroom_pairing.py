from __future__ import annotations

import math
from typing import Any

from ...domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext, RoomVariables
from ..base import ConstraintSettings, require_room_types


def _exact_equality_literal(
    context: ModelContext,
    left: Any,
    right: Any,
    name: str,
) -> Any:
    """Return a Boolean literal equivalent to ``left == right``."""

    left_le_right = _exact_less_equal_literal(
        context,
        left,
        right,
        f"{name}_left_le_right",
    )
    right_le_left = _exact_less_equal_literal(
        context,
        right,
        left,
        f"{name}_right_le_left",
    )
    return _exact_and_literal(
        context,
        (left_le_right, right_le_left),
        name,
    )


def _exact_less_equal_literal(
    context: ModelContext,
    left: Any,
    right: Any,
    name: str,
) -> Any:
    """Return a Boolean literal equivalent to ``left <= right``."""

    literal = context.model.NewBoolVar(context.new_name(name))
    context.model.Add(left <= right).OnlyEnforceIf(literal)
    context.model.Add(left >= right + 1).OnlyEnforceIf(literal.Not())
    return literal


def _exact_and_literal(
    context: ModelContext,
    conditions: tuple[Any, ...],
    name: str,
) -> Any:
    """Return a Boolean literal equivalent to the AND of all conditions."""

    result = context.model.NewBoolVar(context.new_name(name))
    for condition in conditions:
        context.model.AddImplication(result, condition)

    # If every condition is true, result must also be true.
    context.model.AddBoolOr(
        [condition.Not() for condition in conditions] + [result]
    )
    return result


def _exact_shared_wall_literal(
    context: ModelContext,
    first: RoomVariables,
    second: RoomVariables,
    minimum_overlap: int,
) -> Any:
    """Return a literal equivalent to a qualifying shared wall.

    Unlike the solver's normal adjacency helper, this relation is fully
    reified. Therefore a false literal also means the two rooms cannot share a
    wall segment of ``minimum_overlap`` or more. That exact behavior is needed
    to make the geometric bathroom/bedroom pairing genuinely one-to-one.
    """

    pair_name = f"{first.room.id_key}_{second.room.id_key}"

    first_right = _exact_and_literal(
        context,
        (
            _exact_equality_literal(
                context,
                first.x_end,
                second.x,
                f"pair_right_edge_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                first.y + minimum_overlap,
                second.y_end,
                f"pair_right_overlap_a_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                second.y + minimum_overlap,
                first.y_end,
                f"pair_right_overlap_b_{pair_name}",
            ),
        ),
        f"pair_touches_right_{pair_name}",
    )

    first_left = _exact_and_literal(
        context,
        (
            _exact_equality_literal(
                context,
                first.x,
                second.x_end,
                f"pair_left_edge_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                first.y + minimum_overlap,
                second.y_end,
                f"pair_left_overlap_a_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                second.y + minimum_overlap,
                first.y_end,
                f"pair_left_overlap_b_{pair_name}",
            ),
        ),
        f"pair_touches_left_{pair_name}",
    )

    first_back = _exact_and_literal(
        context,
        (
            _exact_equality_literal(
                context,
                first.y_end,
                second.y,
                f"pair_back_edge_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                first.x + minimum_overlap,
                second.x_end,
                f"pair_back_overlap_a_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                second.x + minimum_overlap,
                first.x_end,
                f"pair_back_overlap_b_{pair_name}",
            ),
        ),
        f"pair_touches_back_{pair_name}",
    )

    first_front = _exact_and_literal(
        context,
        (
            _exact_equality_literal(
                context,
                first.y,
                second.y_end,
                f"pair_front_edge_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                first.x + minimum_overlap,
                second.x_end,
                f"pair_front_overlap_a_{pair_name}",
            ),
            _exact_less_equal_literal(
                context,
                second.x + minimum_overlap,
                first.x_end,
                f"pair_front_overlap_b_{pair_name}",
            ),
        ),
        f"pair_touches_front_{pair_name}",
    )

    side_literals = (
        first_right,
        first_left,
        first_back,
        first_front,
    )
    adjacent = context.model.NewBoolVar(
        context.new_name("attached_bathroom_pair", pair_name)
    )

    context.model.AddImplication(adjacent, first.present)
    context.model.AddImplication(adjacent, second.present)
    context.model.AddBoolOr(list(side_literals)).OnlyEnforceIf(adjacent)
    for side in side_literals:
        context.model.AddImplication(side, adjacent)

    return adjacent


class AttachedBathroomPairingConstraint:
    """Enforce one-to-one attached-bathroom and bedroom wall connections."""

    key = "attached_bathroom_pairing"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        attached_bathroom_types = set(
            require_room_types(
                settings.get(
                    "attached_bathroom_room_types",
                    (RoomType.ATTACHED_BATHROOM,),
                ),
                "attached_bathroom_pairing.attached_bathroom_room_types",
            )
        )
        bedroom_types = set(
            require_room_types(
                settings.get("bedroom_room_types", (RoomType.BEDROOM,)),
                "attached_bathroom_pairing.bedroom_room_types",
            )
        )

        try:
            minimum_shared_wall_value = float(
                settings.get("minimum_shared_wall", 10.0)
            )
        except (TypeError, ValueError) as exc:
            raise InvalidProfileError(
                "attached_bathroom_pairing.minimum_shared_wall must be numeric"
            ) from exc

        if (
            not math.isfinite(minimum_shared_wall_value)
            or minimum_shared_wall_value <= 0
        ):
            raise InvalidProfileError(
                "attached_bathroom_pairing.minimum_shared_wall must be "
                "finite and greater than zero"
            )

        minimum_shared_wall = max(
            1,
            context.problem.scale.minimum_length(minimum_shared_wall_value),
        )

        all_rooms = tuple(context.room_variables.values())
        attached_bathrooms = tuple(
            room
            for room in all_rooms
            if room.room.room_type in attached_bathroom_types
        )
        bedrooms = tuple(
            room for room in all_rooms if room.room.room_type in bedroom_types
        )

        pairings_by_bedroom: dict[str, list[Any]] = {
            bedroom.room.id_key: [] for bedroom in bedrooms
        }

        for attached_bathroom in attached_bathrooms:
            bathroom_pairings: list[Any] = []

            for bedroom in bedrooms:
                pairing = _exact_shared_wall_literal(
                    context,
                    attached_bathroom,
                    bedroom,
                    minimum_shared_wall,
                )
                bathroom_pairings.append(pairing)
                pairings_by_bedroom[bedroom.room.id_key].append(pairing)

            if not bathroom_pairings:
                # Required attached bathrooms make the model infeasible;
                # optional attached bathrooms are forced absent.
                context.model.Add(attached_bathroom.present == 0)
                continue

            # Every present attached bathroom must share a qualifying wall with
            # exactly one bedroom. An absent optional bathroom has no pairing.
            context.model.Add(
                sum(bathroom_pairings) == attached_bathroom.present
            )

        for bedroom in bedrooms:
            bedroom_pairings = pairings_by_bedroom[bedroom.room.id_key]
            if not bedroom_pairings:
                continue

            # A present bedroom may serve no more than one attached bathroom.
            # An absent optional bedroom cannot serve any bathroom.
            context.model.Add(
                sum(bedroom_pairings) <= bedroom.present
            )
