from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ..domain import RoomType
from .exceptions import InvalidProfileError

FRONT_WALL_SETBACK_KEY = "front_wall_setback"


def validate_front_wall_setback_settings(settings: Mapping[str, Any]) -> None:
    key = FRONT_WALL_SETBACK_KEY
    if not isinstance(settings, Mapping) or set(settings) != {"rules"}:
        raise InvalidProfileError(f"{key}.settings must contain only rules")
    rules = settings["rules"]
    if not isinstance(rules, (list, tuple)) or not rules:
        raise InvalidProfileError(f"{key}.rules must be a nonempty sequence")

    required = {"room_types", "maximum_setback"}
    for index, rule in enumerate(rules):
        path = f"{key}.rules[{index}]"
        if not isinstance(rule, Mapping) or not required <= set(rule) <= required | {
            "when"
        }:
            raise InvalidProfileError(f"{path} has invalid fields")
        room_types = rule["room_types"]
        if (
            not isinstance(room_types, (list, tuple))
            or not room_types
            or any(not isinstance(room_type, RoomType) for room_type in room_types)
        ):
            raise InvalidProfileError(
                f"{path}.room_types must be a nonempty sequence of RoomType members"
            )
        maximum = rule["maximum_setback"]
        if (
            type(maximum) not in (int, float)
            or maximum < 0
            or (type(maximum) is float and not math.isfinite(maximum))
        ):
            raise InvalidProfileError(
                f"{path}.maximum_setback must be finite and non-negative"
            )
        if "when" in rule:
            when = rule["when"]
            if not isinstance(when, Mapping) or set(when) != {"room_type", "exists"}:
                raise InvalidProfileError(
                    f"{path}.when must contain only room_type and exists"
                )
            if not isinstance(when["room_type"], RoomType):
                raise InvalidProfileError(
                    f"{path}.when.room_type must be a RoomType member"
                )
            if type(when["exists"]) is not bool:
                raise InvalidProfileError(f"{path}.when.exists must be Boolean")
