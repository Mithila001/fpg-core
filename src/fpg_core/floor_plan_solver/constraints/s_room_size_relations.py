from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ...domain import RoomType
from ...domain.room_size_preferences import DEFAULT_ROOM_SIZE_MAX_RATIO, DEFAULT_ROOM_SIZE_PAIRS
from ..exceptions import InvalidProfileError
from ..model import ModelContext
from .base import ConstraintSettings, PenaltyTerm

DEFAULT_RULES = tuple(
    {"compared_type": compared, "reference_type": reference,
     "max_ratio": DEFAULT_ROOM_SIZE_MAX_RATIO, "penalty_multiplier": 20}
    for compared, reference in DEFAULT_ROOM_SIZE_PAIRS
)


class RoomSizeRelationsConstraint:
    """Worst-case area shortfall/excess, normalized by reference area capacity."""

    key = "room_size_relations"

    def build_penalties(
        self, context: ModelContext, settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        precision = settings.get("precision", 1000)
        if type(precision) is not int or not 1 <= precision <= 1_000_000:
            raise InvalidProfileError("room_size_relations.precision must be an integer in 1..1000000")
        rules = settings.get("rules", DEFAULT_RULES)
        if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
            raise InvalidProfileError("room_size_relations.rules must be a sequence")
        parsed = []
        for rule in rules:
            if not isinstance(rule, Mapping) or set(rule) - {
                "compared_type", "reference_type", "min_ratio", "max_ratio", "penalty_multiplier",
            }:
                raise InvalidProfileError("room_size_relations rule must be a mapping with supported keys")
            compared, reference = rule.get("compared_type"), rule.get("reference_type")
            if not isinstance(compared, RoomType) or not isinstance(reference, RoomType) or compared is reference:
                raise InvalidProfileError("room_size_relations requires two distinct RoomType members")
            multiplier = rule.get("penalty_multiplier", 1)
            if type(multiplier) is not int or not 1 <= multiplier <= 1_000_000:
                raise InvalidProfileError("room_size_relations.penalty_multiplier must be an integer in 1..1000000")
            bounds = []
            for key in ("min_ratio", "max_ratio"):
                value = rule.get(key)
                if value is not None:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise InvalidProfileError(f"room_size_relations.{key} must be positive and finite")
                    scaled = round(value * precision) if value <= 1_000_000 else 0
                    if scaled < 1:
                        raise InvalidProfileError(f"room_size_relations.{key} is outside supported precision/range")
                    bounds.append((key, scaled))
            if not bounds or (rule.get("min_ratio") is not None and rule.get("max_ratio") is not None and rule["min_ratio"] > rule["max_ratio"]):
                raise InvalidProfileError("room_size_relations requires an ordered nonempty ratio range")
            parsed.append((compared, reference, multiplier, bounds))

        extrema: dict[tuple[RoomType, bool], tuple[Any, int]] = {}

        def extreme(room_type: RoomType, maximum: bool) -> tuple[Any, int] | None:
            cache_key = (room_type, maximum)
            if cache_key in extrema:
                return extrema[cache_key]
            rooms = [v for v in context.room_variables.values() if v.room.room_type is room_type]
            if not rooms:
                return None
            capacity = (max if maximum else min)(v.room.max_area for v in rooms)
            result = context.model.NewIntVar(0, capacity, context.new_name("size_extreme"))
            add = context.model.AddMaxEquality if maximum else context.model.AddMinEquality
            add(result, [v.area for v in rooms])
            extrema[cache_key] = result, capacity
            return result, capacity

        penalties = []
        for index, (compared, reference, multiplier, bounds) in enumerate(parsed):
            for key, ratio in bounds:
                upper = key == "max_ratio"
                c = extreme(compared, upper)
                r = extreme(reference, not upper)
                if c is None or r is None:
                    continue
                c_area, c_capacity = c
                r_area, r_capacity = r
                denominator = precision * r_capacity
                limit = max(precision * c_capacity, ratio * r_capacity)
                numerator_limit = limit * precision + denominator - 1
                # Leave ample int64 headroom for CP-SAT's expression validation.
                if numerator_limit * multiplier > 2**50:
                    raise InvalidProfileError("room_size_relations area/ratio/precision product is too large")
                excess = context.model.NewIntVar(0, limit, context.new_name("size_excess"))
                delta = precision * c_area - ratio * r_area
                context.model.AddMaxEquality(excess, [0, delta if upper else -delta])
                numerator = context.model.NewIntVar(0, numerator_limit, context.new_name("size_numerator"))
                context.model.Add(numerator == excess * precision + denominator - 1)
                penalty = context.model.NewIntVar(0, numerator_limit // denominator, context.new_name("size_penalty"))
                context.model.AddDivisionEquality(penalty, numerator, denominator)
                penalties.append(PenaltyTerm(f"room_size_relations:{index}:{key}", penalty, multiplier))
        return tuple(penalties)
