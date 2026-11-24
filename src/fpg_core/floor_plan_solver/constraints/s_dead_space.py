from __future__ import annotations

from ..model import ModelContext
from .base import ConstraintSettings, PENALTY_MAX, ceil_ratio


class DeadSpaceConstraint:
    """Penalize empty area inside the rooms' overall bounding rectangle."""

    key = "dead_space"

    def build_penalty(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ):
        del settings
        floor = context.problem.floor
        rooms = tuple(context.room_variables.values())
        if not rooms:
            return 0

        left_candidates = []
        right_candidates = []
        front_candidates = []
        back_candidates = []

        for variables in rooms:
            left = context.model.NewIntVar(
                0, floor.width, context.new_name("bbox_left_candidate")
            )
            right = context.model.NewIntVar(
                0, floor.width, context.new_name("bbox_right_candidate")
            )
            front = context.model.NewIntVar(
                0, floor.length, context.new_name("bbox_front_candidate")
            )
            back = context.model.NewIntVar(
                0, floor.length, context.new_name("bbox_back_candidate")
            )

            context.model.Add(left == variables.x).OnlyEnforceIf(variables.present)
            context.model.Add(left == floor.width).OnlyEnforceIf(
                variables.present.Not()
            )
            context.model.Add(right == variables.x_end).OnlyEnforceIf(
                variables.present
            )
            context.model.Add(right == 0).OnlyEnforceIf(variables.present.Not())
            context.model.Add(front == variables.y).OnlyEnforceIf(
                variables.present
            )
            context.model.Add(front == floor.length).OnlyEnforceIf(
                variables.present.Not()
            )
            context.model.Add(back == variables.y_end).OnlyEnforceIf(
                variables.present
            )
            context.model.Add(back == 0).OnlyEnforceIf(variables.present.Not())

            left_candidates.append(left)
            right_candidates.append(right)
            front_candidates.append(front)
            back_candidates.append(back)

        left_edge = context.model.NewIntVar(
            0, floor.width, context.new_name("bbox_left")
        )
        right_edge = context.model.NewIntVar(
            0, floor.width, context.new_name("bbox_right")
        )
        front_edge = context.model.NewIntVar(
            0, floor.length, context.new_name("bbox_front")
        )
        back_edge = context.model.NewIntVar(
            0, floor.length, context.new_name("bbox_back")
        )
        context.model.AddMinEquality(left_edge, left_candidates)
        context.model.AddMaxEquality(right_edge, right_candidates)
        context.model.AddMinEquality(front_edge, front_candidates)
        context.model.AddMaxEquality(back_edge, back_candidates)

        width = context.model.NewIntVar(
            0, floor.width, context.new_name("bbox_width")
        )
        length = context.model.NewIntVar(
            0, floor.length, context.new_name("bbox_length")
        )
        context.model.Add(width == right_edge - left_edge)
        context.model.Add(length == back_edge - front_edge)

        bbox_area = context.model.NewIntVar(
            0, floor.area, context.new_name("bbox_area")
        )
        context.model.AddMultiplicationEquality(bbox_area, [width, length])

        room_area_sum = context.model.NewIntVar(
            0, floor.area, context.new_name("room_area_sum")
        )
        context.model.Add(room_area_sum == sum(room.area for room in rooms))

        dead_space = context.model.NewIntVar(
            0, floor.area, context.new_name("dead_space")
        )
        context.model.Add(dead_space == bbox_area - room_area_sum)
        denominator = context.model.NewIntVar(1, floor.area, context.new_name("gap_denominator"))
        context.model.AddMaxEquality(denominator, [1, bbox_area])
        return ceil_ratio(context, PENALTY_MAX * dead_space, denominator, PENALTY_MAX,
                          denominator_max=floor.area)
