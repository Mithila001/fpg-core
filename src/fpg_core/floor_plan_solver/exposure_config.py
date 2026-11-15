from __future__ import annotations

import math
from collections.abc import Mapping

from ..domain import RoomType
from .exceptions import InvalidProfileError

EXPOSURE_KEYS = frozenset({"exterior_wall_exposure", "living_room_front"})


def validate_exposure_settings(key, settings):
    if key not in EXPOSURE_KEYS:
        return settings
    if not isinstance(settings, Mapping) or set(settings) != {"rules"}:
        raise InvalidProfileError(f"{key}.settings must contain only rules")
    rules = settings["rules"]
    if not isinstance(rules, (list, tuple)) or not rules:
        raise InvalidProfileError(f"{key}.rules must be a nonempty sequence")

    def validate_requirement(node, path):
        if not isinstance(node, Mapping):
            raise InvalidProfileError(f"{path} must be a mapping")
        if set(node) in ({"all"}, {"any"}):
            op = next(iter(node))
            children = node[op]
            if not isinstance(children, (tuple, list)) or not children:
                raise InvalidProfileError(f"{path}.{op} must be a nonempty sequence")
            for index, child in enumerate(children):
                validate_requirement(child, f"{path}.{op}[{index}]")
            return
        if node.get("side") not in ("front", "back", "left", "right"):
            raise InvalidProfileError(f"{path}.side is invalid")
        coverage = node.get("coverage")
        if coverage == "full_wall" and set(node) == {"side", "coverage"}:
            return
        if coverage == "minimum_continuous_length" and set(node) == {
            "side",
            "coverage",
            "minimum_length",
        }:
            length = node["minimum_length"]
            if (
                not isinstance(length, bool)
                and isinstance(length, (int, float))
                and math.isfinite(length)
                and length > 0
            ):
                return
        raise InvalidProfileError(f"{path} has invalid coverage or minimum_length")

    ids = set()
    for index, rule in enumerate(rules):
        path = f"{key}.rules[{index}]"
        if not isinstance(rule, Mapping) or set(rule) != {
            "id",
            "room_types",
            "match",
            "requirement",
        }:
            raise InvalidProfileError(f"{path} has invalid fields")
        ident = rule["id"]
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise InvalidProfileError(f"{path}.id must be nonempty and unique")
        ids.add(ident)
        path = f"{key}.{ident}"
        types = rule["room_types"]
        if (
            not isinstance(types, (tuple, list))
            or not types
            or any(not isinstance(t, RoomType) for t in types)
        ):
            raise InvalidProfileError(
                f"{path}.room_types must contain RoomType members"
            )
        match = rule["match"]
        if not isinstance(match, Mapping):
            raise InvalidProfileError(f"{path}.match must be a mapping")
        policy = match.get("policy")
        count = match.get("count")
        if not (
            policy == "all"
            and set(match) == {"policy"}
            or policy == "at_least"
            and set(match) == {"policy", "count"}
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count > 0
        ):
            raise InvalidProfileError(f"{path}.match has invalid policy or count")
        validate_requirement(rule["requirement"], f"{path}.requirement")
    return settings
