from __future__ import annotations

import math
from fractions import Fraction

from ....domain import RoomType
from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types


class HallwayDimensionsConstraint:
    """Keep one hallway dimension within the configured corridor-width range."""

    key = "hallway_dimensions"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        hallway_types = require_room_types(
            settings.get("hallway_room_types", (RoomType.HALLWAY,)),
            "hallway_dimensions.hallway_room_types",
        )
        minimum_width = int(settings.get("minimum_width", 10))
        maximum_width = int(settings.get("maximum_width", 10))

        if minimum_width < 10:
            raise InvalidProfileError(
                "hallway_dimensions.minimum_width must be at least 10 project units"
            )
        if maximum_width < minimum_width:
            raise InvalidProfileError(
                "hallway_dimensions.maximum_width must be greater than or "
                "equal to minimum_width"
            )

        minimum_width = context.problem.scale.minimum_length(minimum_width)
        maximum_width = context.problem.scale.maximum_length(maximum_width)
        horizontal_ratio = _ratio(settings.get("horizontal_span_ratio", 0.5), "horizontal_span_ratio")
        vertical_ratio = _ratio(settings.get("vertical_span_ratio", 0.5), "vertical_span_ratio")
        for variables in context.room_variables.values():
            if variables.room.room_type not in hallway_types:
                continue

            horizontal = context.model.NewBoolVar(
                context.new_name(
                    "hallway_horizontal",
                    variables.room.id_key,
                )
            )
            vertical = context.model.NewBoolVar(
                context.new_name(
                    "hallway_vertical",
                    variables.room.id_key,
                )
            )

            # A present hallway chooses exactly one orientation. An absent
            # optional hallway chooses neither orientation.
            context.model.Add(horizontal + vertical == variables.present)

            # Horizontal hallway: length is the corridor width; room width may
            # extend as far as its prepared room-size bounds allow.
            context.model.Add(
                variables.length >= minimum_width
            ).OnlyEnforceIf(horizontal)
            context.model.Add(
                variables.length <= maximum_width
            ).OnlyEnforceIf(horizontal)
            horizontal_span = _room_span(context, hallway_types, horizontal=True)
            context.model.Add(
                variables.width * horizontal_ratio.denominator
                <= horizontal_span * horizontal_ratio.numerator
            ).OnlyEnforceIf(horizontal)

            # Vertical hallway: width is the corridor width; room length may
            # extend as far as its prepared room-size bounds allow.
            context.model.Add(
                variables.width >= minimum_width
            ).OnlyEnforceIf(vertical)
            context.model.Add(
                variables.width <= maximum_width
            ).OnlyEnforceIf(vertical)
            vertical_span = _room_span(context, hallway_types, horizontal=False)
            context.model.Add(
                variables.length * vertical_ratio.denominator
                <= vertical_span * vertical_ratio.numerator
            ).OnlyEnforceIf(vertical)


def _room_span(context, hallway_types, horizontal):
    rooms = [r for r in context.room_variables.values() if r.room.room_type not in hallway_types]
    if not rooms:
        return 0
    starts = [r.x if horizontal else r.y for r in rooms]
    ends = [r.x_end if horizontal else r.y_end for r in rooms]
    upper = context.problem.floor.width if horizontal else context.problem.floor.length
    lo = context.model.NewIntVar(0, upper, context.new_name("hallway_room_span_min"))
    hi = context.model.NewIntVar(0, upper, context.new_name("hallway_room_span_max"))
    span = context.model.NewIntVar(0, upper, context.new_name("hallway_room_span"))
    context.model.AddMinEquality(lo, starts)
    context.model.AddMaxEquality(hi, ends)
    context.model.Add(span == hi - lo)
    return span


def _ratio(value, name):
    try:
        ratio = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise InvalidProfileError(f"hallway_dimensions.{name} must be between 0 and 1") from exc
    if not math.isfinite(float(ratio)) or not 0 < ratio <= 1:
        raise InvalidProfileError(f"hallway_dimensions.{name} must be between 0 and 1")
    return ratio
