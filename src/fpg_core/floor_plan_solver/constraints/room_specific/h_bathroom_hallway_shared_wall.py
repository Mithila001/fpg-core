from __future__ import annotations

import math
from itertools import combinations
from typing import Any

from ....domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext, RoomVariables
from ..base import ConstraintSettings

_BATHROOM_TYPE = RoomType.BATHROOM
_HALLWAY_TYPE = RoomType.HALLWAY
_SIDES = ("right", "left", "back", "front")


class BathroomHallwaySharedWallConstraint:
    """Limit bathroom sides shared with hallways and total extra shared length."""

    key = "bathroom_hallway_shared_wall"

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        side_count = settings.get("maximum_shared_sides", 1)
        if type(side_count) is not int or not 0 <= side_count <= 4:
            raise InvalidProfileError("maximum_shared_sides must be an integer from 0 to 4")
        try:
            extra_length = float(settings.get("additional_shared_length", 10.0))
        except (TypeError, ValueError) as exc:
            raise InvalidProfileError("additional_shared_length must be numeric") from exc
        if not math.isfinite(extra_length) or extra_length < 0:
            raise InvalidProfileError("additional_shared_length must be finite and non-negative")
        allowance = context.problem.scale.maximum_length(extra_length)
        hallways = tuple(
            room
            for room in context.room_variables.values()
            if room.room.room_type is _HALLWAY_TYPE
        )
        bathrooms = tuple(
            room
            for room in context.room_variables.values()
            if room.room.room_type is _BATHROOM_TYPE
        )

        for bathroom in bathrooms:
            side_overlaps = {side: [] for side in _SIDES}
            for hallway in hallways:
                for side, overlap in _shared_side_overlaps(
                    context, bathroom, hallway
                ).items():
                    side_overlaps[side].append(overlap)

            side_totals = []
            for side, overlaps in side_overlaps.items():
                side_limit = (
                    context.problem.floor.length
                    if side in ("right", "left")
                    else context.problem.floor.width
                )
                side_total = context.model.NewIntVar(
                    0,
                    side_limit,
                    context.new_name(
                        "bathroom_hallway_side_length",
                        bathroom.room.id_key,
                        side,
                    ),
                )
                context.model.Add(side_total == sum(overlaps))
                side_totals.append(side_total)

            largest_side = context.model.NewIntVar(
                0,
                2 * (context.problem.floor.width + context.problem.floor.length),
                context.new_name("bathroom_hallway_largest_side", bathroom.room.id_key),
            )
            context.model.AddMaxEquality(
                largest_side,
                [sum(group) for group in combinations(side_totals, side_count)],
            )
            context.model.Add(sum(side_totals) - largest_side <= allowance)


def _shared_side_overlaps(
    context: ModelContext,
    first: RoomVariables,
    second: RoomVariables,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    directions = (
        ("right", first.x_end, second.x, first.y, first.y_end, second.y, second.y_end),
        ("left", first.x, second.x_end, first.y, first.y_end, second.y, second.y_end),
        ("back", first.y_end, second.y, first.x, first.x_end, second.x, second.x_end),
        ("front", first.y, second.y_end, first.x, first.x_end, second.x, second.x_end),
    )
    for side, face_a, face_b, start_a, end_a, start_b, end_b in directions:
        limit = (
            context.problem.floor.length
            if side in ("right", "left")
            else context.problem.floor.width
        )
        pair = (first.room.id_key, second.room.id_key, side)
        minimum_end = context.model.NewIntVar(
            0, limit, context.new_name("bathroom_hallway_min_end", *pair)
        )
        maximum_start = context.model.NewIntVar(
            0, limit, context.new_name("bathroom_hallway_max_start", *pair)
        )
        signed = context.model.NewIntVar(
            -limit, limit, context.new_name("bathroom_hallway_signed_overlap", *pair)
        )
        projected_overlap = context.model.NewIntVar(
            0, limit, context.new_name("bathroom_hallway_overlap", *pair)
        )
        context.model.AddMinEquality(minimum_end, [end_a, end_b])
        context.model.AddMaxEquality(maximum_start, [start_a, start_b])
        context.model.Add(signed == minimum_end - maximum_start)
        context.model.AddMaxEquality(projected_overlap, [signed, 0])

        touching = context.model.NewBoolVar(
            context.new_name("bathroom_hallway_touching", *pair)
        )
        context.model.Add(face_a == face_b).OnlyEnforceIf(touching)
        context.model.Add(face_a != face_b).OnlyEnforceIf(touching.Not())
        shared_overlap = context.model.NewIntVar(
            0, limit, context.new_name("bathroom_hallway_shared_overlap", *pair)
        )
        context.model.Add(shared_overlap == projected_overlap).OnlyEnforceIf(touching)
        context.model.Add(shared_overlap == 0).OnlyEnforceIf(touching.Not())
        result[side] = shared_overlap
    return result
