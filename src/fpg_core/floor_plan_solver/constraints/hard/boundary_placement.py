from __future__ import annotations

from collections.abc import Mapping, Sequence

from ...exceptions import InvalidProfileError
from ...model import ModelContext
from ..base import ConstraintSettings, require_room_types


class BoundaryPlacementConstraint:
    """Apply profile-defined room-type placement rules to floor boundaries."""

    key = "boundary_placement"

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        raw_rules = settings.get("rules", ())
        if not isinstance(raw_rules, Sequence):
            raise InvalidProfileError("boundary_placement.rules must be a sequence")

        for index, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, Mapping):
                raise InvalidProfileError(
                    f"boundary_placement rule {index} must be a mapping"
                )
            room_types = require_room_types(
                raw_rule.get("room_types", ()),
                f"boundary_placement.rules[{index}].room_types",
            )
            side = str(raw_rule.get("side", "")).strip().lower()
            offset_value = float(raw_rule.get("offset", 0.0))
            if not room_types:
                raise InvalidProfileError(
                    f"boundary_placement rule {index} has no room types"
                )
            if side not in {"front", "back", "left", "right"}:
                raise InvalidProfileError(
                    f"boundary_placement rule {index} has invalid side '{side}'"
                )
            if offset_value < 0:
                raise InvalidProfileError(
                    f"boundary_placement rule {index} has a negative offset"
                )

            offset = context.problem.scale.nearest_length(offset_value)
            if side in {"left", "right"} and offset > context.problem.floor.width:
                raise InvalidProfileError(
                    f"boundary_placement rule {index} offset exceeds floor width"
                )
            if side in {"front", "back"} and offset > context.problem.floor.length:
                raise InvalidProfileError(
                    f"boundary_placement rule {index} offset exceeds floor length"
                )

            for variables in context.room_variables.values():
                if variables.room.room_type not in room_types:
                    continue
                if side == "front":
                    constraint = context.model.Add(variables.y == offset)
                elif side == "back":
                    constraint = context.model.Add(
                        variables.y_end == context.problem.floor.length - offset
                    )
                elif side == "left":
                    constraint = context.model.Add(variables.x == offset)
                else:
                    constraint = context.model.Add(
                        variables.x_end == context.problem.floor.width - offset
                    )
                constraint.OnlyEnforceIf(variables.present)
