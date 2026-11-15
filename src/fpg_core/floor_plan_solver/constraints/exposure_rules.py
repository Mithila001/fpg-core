from __future__ import annotations

from ..exceptions import InvalidProfileError
from .base import PenaltyTerm
from .exposure import _and, _or, exposure_literal


def apply_rules(context, settings, key, *, soft=False):
    rules = settings["rules"]
    penalties = []
    for rule in rules:
        ident = rule["id"]
        types = rule["room_types"]
        policy = rule["match"]["policy"]
        count = rule["match"].get("count")

        def validate_span(node, ident=ident):
            if "all" in node or "any" in node:
                for child in node.get("all", node.get("any", ())):
                    validate_span(child)
            elif node["coverage"] == "minimum_continuous_length":
                span = (
                    context.problem.floor.width
                    if node["side"] in ("front", "back")
                    else context.problem.floor.length
                )
                if context.problem.scale.minimum_length(node["minimum_length"]) > span:
                    raise InvalidProfileError(
                        f"{key}.{ident}: minimum_length exceeds floor span"
                    )

        validate_span(rule["requirement"])

        def requirement(node, room):
            if "all" in node or "any" in node:
                op = "all" if "all" in node else "any"
                values = [requirement(child, room) for child in node[op]]
                return _and(context, values) if op == "all" else _or(context, values)
            minimum = (
                context.problem.scale.minimum_length(node["minimum_length"])
                if node["coverage"] == "minimum_continuous_length"
                else None
            )
            return exposure_literal(context, room, node["side"], minimum)

        rooms = [
            room
            for room in context.room_variables.values()
            if room.room.room_type in types
        ]
        if not rooms:
            if soft or policy == "all":
                continue
            context.model.AddBoolOr([])
            continue
        qualified = [requirement(rule["requirement"], room) for room in rooms]
        if policy == "all":
            qualified = [
                _or(context, [room.present.Not(), value])
                for room, value in zip(rooms, qualified, strict=True)
            ]
            satisfied = _and(context, qualified)
        else:
            satisfied = context.model.NewBoolVar(context.new_name("exposure_count"))
            context.model.Add(sum(qualified) >= count).OnlyEnforceIf(satisfied)
            context.model.Add(sum(qualified) < count).OnlyEnforceIf(satisfied.Not())
        if soft:
            present = _or(context, [room.present for room in rooms])
            violation = _and(context, [present, satisfied.Not()])
            penalties.append(PenaltyTerm(name=f"{key}:{ident}", expression=violation))
        else:
            context.model.Add(satisfied == 1)
    return tuple(penalties)


class HardExteriorWallExposure:
    key = "exterior_wall_exposure"

    def apply(self, context, settings):
        apply_rules(context, settings, self.key)


class SoftExteriorWallExposure:
    key = "exterior_wall_exposure"

    def build_penalties(self, context, settings):
        return apply_rules(context, settings, self.key, soft=True)
