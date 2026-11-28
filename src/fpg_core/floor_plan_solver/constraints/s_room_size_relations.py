from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ...domain import RoomType
from ...domain.room_size_preferences import (
    DEFAULT_ROOM_SIZE_MAX_RATIO,
    DEFAULT_ROOM_SIZE_PAIRS,
    DEFAULT_ROOM_SIZE_SPREADS,
)
from ..exceptions import InvalidProfileError
from ..model import ModelContext
from .base import PENALTY_MAX, ConstraintSettings, average_penalties, ceil_ratio

DEFAULT_CROSS_TYPE_RULES = tuple(
    {
        "compared_type": compared,
        "reference_type": reference,
        "max_ratio": DEFAULT_ROOM_SIZE_MAX_RATIO,
        "penalty_multiplier": 1,
    }
    for compared, reference in DEFAULT_ROOM_SIZE_PAIRS
)
DEFAULT_SAME_TYPE_RULES = tuple(
    {"room_type": room_type, "maximum_spread_ratio": spread, "penalty_multiplier": 1}
    for room_type, spread in DEFAULT_ROOM_SIZE_SPREADS
)


class RoomSizeRelationsConstraint:
    """Penalize worst-case proportionality violations per applicable rule."""

    key = "room_size_relations"

    def build_penalty(self, context: ModelContext, settings: ConstraintSettings):
        if set(settings) - {"precision", "cross_type_rules", "same_type_rules"}:
            raise InvalidProfileError("room_size_relations has unsupported settings")
        precision = settings.get("precision", 1000)
        if type(precision) is not int or not 1 <= precision <= 1_000_000:
            raise InvalidProfileError(
                "room_size_relations.precision must be an integer in 1..1000000"
            )

        def ratio(value, label, *, zero=False):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or (not zero and value == 0)
                or value > 1_000_000
            ):
                raise InvalidProfileError(
                    f"room_size_relations.{label} has an invalid ratio"
                )
            scaled = round(value * precision)
            if value > 0 and scaled == 0:
                raise InvalidProfileError(
                    f"room_size_relations.{label} is below precision"
                )
            return scaled

        parsed = []
        for same, name, defaults in (
            (False, "cross_type_rules", DEFAULT_CROSS_TYPE_RULES),
            (True, "same_type_rules", DEFAULT_SAME_TYPE_RULES),
        ):
            rules = settings.get(name, defaults)
            if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
                raise InvalidProfileError(
                    f"room_size_relations.{name} must be a sequence"
                )
            seen = set()
            for rule in rules:
                allowed = (
                    {"room_type", "maximum_spread_ratio", "penalty_multiplier"}
                    if same
                    else {
                        "compared_type",
                        "reference_type",
                        "min_ratio",
                        "max_ratio",
                        "penalty_multiplier",
                    }
                )
                if not isinstance(rule, Mapping) or set(rule) - allowed:
                    raise InvalidProfileError(
                        f"room_size_relations.{name} has an invalid rule"
                    )
                compared = rule.get("room_type" if same else "compared_type")
                reference = compared if same else rule.get("reference_type")
                if (
                    not isinstance(compared, RoomType)
                    or not isinstance(reference, RoomType)
                    or (not same and compared is reference)
                ):
                    raise InvalidProfileError(
                        f"room_size_relations.{name} requires valid room types"
                    )
                identity = (compared, reference)
                if identity in seen:
                    raise InvalidProfileError(
                        f"room_size_relations.{name} contains a duplicate rule"
                    )
                seen.add(identity)
                multiplier = rule.get("penalty_multiplier", 1)
                if type(multiplier) is not int or not 1 <= multiplier <= 1_000_000:
                    raise InvalidProfileError(
                        "room_size_relations.penalty_multiplier must be an integer in 1..1000000"
                    )
                if same:
                    if "maximum_spread_ratio" not in rule:
                        raise InvalidProfileError(
                            "room_size_relations requires maximum_spread_ratio"
                        )
                    bounds = [
                        (
                            True,
                            precision
                            + ratio(
                                rule["maximum_spread_ratio"],
                                "maximum_spread_ratio",
                                zero=True,
                            ),
                        )
                    ]
                else:
                    minimum, maximum = rule.get("min_ratio"), rule.get("max_ratio")
                    if minimum is None and maximum is None:
                        raise InvalidProfileError(
                            "room_size_relations requires a ratio bound"
                        )
                    bounds = []
                    if minimum is not None:
                        bounds.append((False, ratio(minimum, "min_ratio")))
                    if maximum is not None:
                        bounds.append((True, ratio(maximum, "max_ratio")))
                    if (
                        minimum is not None
                        and maximum is not None
                        and minimum > maximum
                    ):
                        raise InvalidProfileError(
                            "room_size_relations requires an ordered ratio range"
                        )
                parsed.append((same, compared, reference, multiplier, bounds))

        extrema: dict[tuple[RoomType, bool], tuple[Any, int]] = {}
        rooms_by_type = {
            room_type: [
                v
                for v in context.room_variables.values()
                if v.room.room_type is room_type
            ]
            for room_type in RoomType
        }

        def extreme(room_type, maximum):
            cache_key = (room_type, maximum)
            if cache_key not in extrema:
                rooms = rooms_by_type[room_type]
                capacity = (max if maximum else min)(v.room.max_area for v in rooms)
                result = context.model.NewIntVar(
                    0, capacity, context.new_name("size_extreme")
                )
                add = (
                    context.model.AddMaxEquality
                    if maximum
                    else context.model.AddMinEquality
                )
                add(result, [v.area for v in rooms])
                extrema[cache_key] = result, capacity
            return extrema[cache_key]

        penalties = []
        for same, compared, reference, multiplier, bounds in parsed:
            if (
                not rooms_by_type[compared]
                or not rooms_by_type[reference]
                or (same and len(rooms_by_type[compared]) < 2)
            ):
                continue
            rule_penalties = []
            for upper, scaled in bounds:
                c_area, c_capacity = extreme(compared, upper)
                r_area, r_capacity = extreme(reference, not upper)
                denominator = precision * r_capacity
                limit = max(precision * c_capacity, scaled * r_capacity)
                if denominator <= 0 or (limit * PENALTY_MAX + denominator) > 2**50:
                    raise InvalidProfileError(
                        "room_size_relations area/ratio/precision product is too large"
                    )
                excess = context.model.NewIntVar(
                    0, limit, context.new_name("size_excess")
                )
                delta = precision * c_area - scaled * r_area
                context.model.AddMaxEquality(excess, [0, delta if upper else -delta])
                capped = context.model.NewIntVar(
                    0, denominator, context.new_name("size_capped")
                )
                context.model.AddMinEquality(capped, [excess, denominator])
                rule_penalties.append(
                    ceil_ratio(context, capped * PENALTY_MAX, denominator, PENALTY_MAX)
                )
            if len(rule_penalties) == 1:
                penalty = rule_penalties[0]
            else:
                penalty = context.model.NewIntVar(
                    0, PENALTY_MAX, context.new_name("size_rule_penalty")
                )
                context.model.AddMaxEquality(penalty, rule_penalties)
            penalties.append((penalty, multiplier))
        if sum(weight for _, weight in penalties) * (PENALTY_MAX + 1) > 2**50:
            raise InvalidProfileError(
                "room_size_relations aggregate weight is too large"
            )
        return average_penalties(context, penalties)
