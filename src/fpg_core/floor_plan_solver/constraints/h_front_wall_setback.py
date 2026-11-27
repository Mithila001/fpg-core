from __future__ import annotations

from fractions import Fraction

from ..front_wall_setback_config import FRONT_WALL_SETBACK_KEY
from ..model import ModelContext
from .base import ConstraintSettings
from .geometry import frontmost_wall_y


class FrontWallSetbackConstraint:
    """Limit selected room front edges relative to the entire room arrangement."""

    key = FRONT_WALL_SETBACK_KEY

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        rooms = tuple(context.room_variables.values())
        room_types = {room.room.room_type for room in rooms}
        active_rules = [
            rule
            for rule in settings["rules"]
            if any(room_type in room_types for room_type in rule["room_types"])
            and (
                "when" not in rule
                or (rule["when"]["room_type"] in room_types) == rule["when"]["exists"]
            )
        ]
        if not active_rules:
            return

        front_y = frontmost_wall_y(context)
        for rule in active_rules:
            # A maximum must round down, never expand the allowed setback.
            allowance = min(
                Fraction(str(rule["maximum_setback"])) * context.problem.scale.factor // 1,
                context.problem.floor.length,
            )
            for room in rooms:
                if room.room.room_type in rule["room_types"]:
                    context.model.Add(room.y - front_y <= allowance)
