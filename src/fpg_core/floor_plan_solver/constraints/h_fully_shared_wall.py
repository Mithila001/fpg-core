from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from typing import Any

from ..model import ModelContext, RoomVariables
from ..shared_wall_config import FULLY_SHARED_WALL_KEY
from .base import ConstraintSettings


class FullySharedWallConstraint:
    """Require positive contact and near-complete coverage on selected walls."""

    key = FULLY_SHARED_WALL_KEY

    def apply(self, context: ModelContext, settings: ConstraintSettings) -> None:
        rooms = tuple(context.room_variables.values())
        room_types = {room.room.room_type for room in rooms}
        rules_by_room = {}
        for room in rooms:
            rules = [
                rule for rule in settings["rules"]
                if rule["minimum_shared_sides"] > 0
                and room.room.room_type in rule["room_types"]
                and (
                    "when" not in rule
                    or (rule["when"]["room_type"] in room_types) == rule["when"]["exists"]
                )
            ]
            if rules:
                rules_by_room[room.room.id_key] = rules
        if not rules_by_room:
            return

        # Sides run clockwise: front, right, back, left.
        overlaps: dict[str, tuple[list[Any], ...]] = {
            key: ([], [], [], []) for key in rules_by_room
        }
        floor = context.problem.floor
        limits = (floor.width, floor.length, floor.width, floor.length)
        for first, second in combinations(rooms, 2):
            first_sides = overlaps.get(first.room.id_key)
            second_sides = overlaps.get(second.room.id_key)
            if first_sides is None and second_sides is None:
                continue
            faces_a = (first.y, first.x_end, first.y_end, first.x)
            faces_b = (second.y, second.x_end, second.y_end, second.x)
            projections = (
                _projected_overlap(context, first.x, first.x_end, second.x, second.x_end, floor.width),
                _projected_overlap(context, first.y, first.y_end, second.y, second.y_end, floor.length),
            )
            for side, face in enumerate(faces_a):
                opposite = (side + 2) % 4
                shared = _touching_overlap(
                    context, face, faces_b[opposite], projections[side % 2], limits[side]
                )
                if first_sides is not None:
                    first_sides[side].append(shared)
                if second_sides is not None:
                    second_sides[opposite].append(shared)

        for key, rules in rules_by_room.items():
            room = context.room_variables[key]
            shared_sides = tuple(sum(segments) for segments in overlaps[key])
            for rule in rules:
                _require_wall_group(context, room, shared_sides, rule)


def _projected_overlap(
    context: ModelContext, start_a: Any, end_a: Any, start_b: Any, end_b: Any, limit: int
) -> Any:
    model = context.model
    start = model.NewIntVar(0, limit, context.new_name("shared_wall_start"))
    end = model.NewIntVar(0, limit, context.new_name("shared_wall_end"))
    span = model.NewIntVar(-limit, limit, context.new_name("shared_wall_span"))
    overlap = model.NewIntVar(0, limit, context.new_name("shared_wall_projection"))
    model.AddMaxEquality(start, [start_a, start_b])
    model.AddMinEquality(end, [end_a, end_b])
    model.Add(span == end - start)
    model.AddMaxEquality(overlap, [0, span])
    return overlap


def _touching_overlap(
    context: ModelContext, face_a: Any, face_b: Any, projection: Any, limit: int
) -> Any:
    model = context.model
    touches = model.NewBoolVar(context.new_name("shared_wall_touches"))
    shared = model.NewIntVar(0, limit, context.new_name("shared_wall_contact"))
    model.Add(face_a == face_b).OnlyEnforceIf(touches)
    model.Add(face_a != face_b).OnlyEnforceIf(touches.Not())
    model.Add(shared == projection).OnlyEnforceIf(touches)
    model.Add(shared == 0).OnlyEnforceIf(touches.Not())
    return shared


def _require_wall_group(
    context: ModelContext, room: RoomVariables, shared: tuple[Any, ...], rule: ConstraintSettings
) -> None:
    count = rule["minimum_shared_sides"]
    groups = tuple(combinations(range(4), count))
    if count == 2 and rule["arrangement"] == "adjacent":
        groups = tuple(group for group in groups if group[1] - group[0] != 2)

    floor = context.problem.floor
    tolerance = rule.get("uncovered_length_tolerance", 0)
    # Use the coordinate scale with an exact floor, including near grid boundaries.
    length = Fraction(str(tolerance)) if type(tolerance) is float else Fraction(tolerance)
    allowance = min(
        length * context.problem.scale.factor // 1, 2 * (floor.width + floor.length)
    )
    lengths = (room.width, room.length, room.width, room.length)
    # Non-overlap makes the positive segments on a wall disjoint.
    uncovered = tuple(length - contact for length, contact in zip(lengths, shared, strict=True))
    model = context.model
    choices = []
    for group in groups:
        enforced_by = []
        if len(groups) > 1:
            choice = model.NewBoolVar(context.new_name("shared_wall_group", room.room.id_key))
            choices.append(choice)
            enforced_by.append(choice)
        for side in group:
            model.Add(shared[side] > 0).OnlyEnforceIf(enforced_by)
        model.Add(sum(uncovered[side] for side in group) <= allowance).OnlyEnforceIf(enforced_by)
    if choices:
        model.AddBoolOr(choices)
