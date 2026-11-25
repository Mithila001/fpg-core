from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ..domain import RoomType
from .exceptions import InvalidProfileError

FULLY_SHARED_WALL_KEY = "fully_shared_wall"


def validate_fully_shared_wall_settings(settings: Mapping[str, Any]) -> None:
    key = FULLY_SHARED_WALL_KEY
    if not isinstance(settings, Mapping) or set(settings) != {"rules"}:
        raise InvalidProfileError(f"{key}.settings must contain only rules")
    rules = settings["rules"]
    if not isinstance(rules, (list, tuple)) or not rules:
        raise InvalidProfileError(f"{key}.rules must be a nonempty sequence")

    required = {"room_types", "minimum_shared_sides", "arrangement"}
    allowed = required | {"uncovered_length_tolerance", "when"}
    for index, rule in enumerate(rules):
        path = f"{key}.rules[{index}]"
        if not isinstance(rule, Mapping) or not required <= set(rule) <= allowed:
            raise InvalidProfileError(f"{path} has invalid fields")
        room_types = rule["room_types"]
        if (
            not isinstance(room_types, (list, tuple))
            or not room_types
            or any(not isinstance(room_type, RoomType) for room_type in room_types)
        ):
            raise InvalidProfileError(f"{path}.room_types must be a nonempty sequence of RoomType members")
        count = rule["minimum_shared_sides"]
        if type(count) is not int or not 0 <= count <= 4:
            raise InvalidProfileError(f"{path}.minimum_shared_sides must be an integer from 0 to 4")
        if rule["arrangement"] not in ("adjacent", "any"):
            raise InvalidProfileError(f"{path}.arrangement must be adjacent or any")
        tolerance = rule.get("uncovered_length_tolerance", 0)
        if (
            type(tolerance) not in (int, float)
            or tolerance < 0
            or (type(tolerance) is float and not math.isfinite(tolerance))
        ):
            raise InvalidProfileError(f"{path}.uncovered_length_tolerance must be finite and non-negative")
        if "when" in rule:
            when = rule["when"]
            if not isinstance(when, Mapping) or set(when) != {"room_type", "exists"}:
                raise InvalidProfileError(f"{path}.when must contain only room_type and exists")
            if not isinstance(when["room_type"], RoomType):
                raise InvalidProfileError(f"{path}.when.room_type must be a RoomType member")
            if type(when["exists"]) is not bool:
                raise InvalidProfileError(f"{path}.when.exists must be Boolean")
