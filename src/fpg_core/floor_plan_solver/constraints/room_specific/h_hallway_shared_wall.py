from __future__ import annotations

import math
from typing import Any

from ....domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext, RoomVariables
from ..base import ConstraintSettings, require_room_types


class HallwaySharedWallConstraint:
    """Limit the wall length shared by any two configured hallway rooms."""

    key = "hallway_shared_wall"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        hallway_types = set(
            require_room_types(
                settings.get("hallway_room_types", (RoomType.HALLWAY,)),
                "hallway_shared_wall.hallway_room_types",
            )
        )

        raw_maximum = settings.get("maximum_shared_wall", 12.0)
        try:
            maximum_shared_wall = float(raw_maximum)
        except (TypeError, ValueError) as exc:
            raise InvalidProfileError(
                "hallway_shared_wall.maximum_shared_wall must be numeric"
            ) from exc
        if not math.isfinite(maximum_shared_wall) or maximum_shared_wall < 0:
            raise InvalidProfileError(
                "hallway_shared_wall.maximum_shared_wall must be finite and "
                "non-negative"
            )

        maximum_overlap = context.problem.scale.maximum_length(maximum_shared_wall)
        hallways = [
            variables
            for variables in context.room_variables.values()
            if variables.room.room_type in hallway_types
        ]

        for index, first in enumerate(hallways):
            for second in hallways[index + 1 :]:
                x_overlap = _interval_overlap(
                    context,
                    first.x,
                    first.x_end,
                    second.x,
                    second.x_end,
                    context.problem.floor.width,
                    "hallway_x_overlap",
                    first,
                    second,
                )
                y_overlap = _interval_overlap(
                    context,
                    first.y,
                    first.y_end,
                    second.y,
                    second.y_end,
                    context.problem.floor.length,
                    "hallway_y_overlap",
                    first,
                    second,
                )

                _limit_overlap_if_equal(
                    context,
                    first.x_end,
                    second.x,
                    y_overlap,
                    maximum_overlap,
                    "hallway_touch_right",
                    first,
                    second,
                )
                _limit_overlap_if_equal(
                    context,
                    first.x,
                    second.x_end,
                    y_overlap,
                    maximum_overlap,
                    "hallway_touch_left",
                    first,
                    second,
                )
                _limit_overlap_if_equal(
                    context,
                    first.y_end,
                    second.y,
                    x_overlap,
                    maximum_overlap,
                    "hallway_touch_back",
                    first,
                    second,
                )
                _limit_overlap_if_equal(
                    context,
                    first.y,
                    second.y_end,
                    x_overlap,
                    maximum_overlap,
                    "hallway_touch_front",
                    first,
                    second,
                )


def _interval_overlap(
    context: ModelContext,
    first_start: Any,
    first_end: Any,
    second_start: Any,
    second_end: Any,
    axis_limit: int,
    name: str,
    first: RoomVariables,
    second: RoomVariables,
) -> Any:
    """Return max(0, min(end) - max(start)) for two integer intervals."""

    pair = (first.room.id_key, second.room.id_key)
    minimum_end = context.model.NewIntVar(
        0,
        axis_limit,
        context.new_name(f"{name}_min_end", *pair),
    )
    maximum_start = context.model.NewIntVar(
        0,
        axis_limit,
        context.new_name(f"{name}_max_start", *pair),
    )
    signed_overlap = context.model.NewIntVar(
        -axis_limit,
        axis_limit,
        context.new_name(f"{name}_signed", *pair),
    )
    overlap = context.model.NewIntVar(
        0,
        axis_limit,
        context.new_name(name, *pair),
    )

    context.model.AddMinEquality(minimum_end, [first_end, second_end])
    context.model.AddMaxEquality(maximum_start, [first_start, second_start])
    context.model.Add(signed_overlap == minimum_end - maximum_start)
    context.model.AddMaxEquality(overlap, [signed_overlap, 0])
    return overlap


def _limit_overlap_if_equal(
    context: ModelContext,
    first_face: Any,
    second_face: Any,
    projected_overlap: Any,
    maximum_overlap: int,
    name: str,
    first: RoomVariables,
    second: RoomVariables,
) -> None:
    """Apply the overlap cap exactly when two candidate wall faces coincide."""

    touching = context.model.NewBoolVar(
        context.new_name(name, first.room.id_key, second.room.id_key)
    )
    context.model.Add(first_face == second_face).OnlyEnforceIf(touching)
    context.model.Add(first_face != second_face).OnlyEnforceIf(touching.Not())
    context.model.Add(projected_overlap <= maximum_overlap).OnlyEnforceIf(touching)
