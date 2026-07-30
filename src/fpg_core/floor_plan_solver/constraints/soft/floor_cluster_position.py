from __future__ import annotations

from ...exceptions import InvalidProfileError
from ...model import ModelContext, RoomVariables
from ..base import ConstraintSettings, PenaltyTerm, require_room_types
from ..geometry import active_linear_penalty


class FloorClusterPositionConstraint:
    """Center the room cluster horizontally and bias it toward the front.

    Project coordinate convention:

    - X- is left.
    - X+ is right.
    - Y- is front.
    - Y+ is back.

    The constraint evaluates the outer bounding box of all included,
    currently-present rooms.

    It prefers:

    1. Equal unused space on the left and right sides of the cluster.
    2. The front edge of the cluster to be close to y = 0.

    It does not pull every room individually toward the floor center.
    """

    key = "floor_cluster_position"

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        horizontal_multiplier = int(settings.get("horizontal_multiplier", 1))
        front_multiplier = int(settings.get("front_multiplier", 1))

        if horizontal_multiplier < 0:
            raise InvalidProfileError(
                "floor_cluster_position.horizontal_multiplier cannot be negative"
            )

        if front_multiplier < 0:
            raise InvalidProfileError(
                "floor_cluster_position.front_multiplier cannot be negative"
            )

        excluded_room_types = require_room_types(
            settings.get("excluded_room_types", ()),
            "floor_cluster_position.excluded_room_types",
        )

        included_rooms = tuple(
            variables
            for variables in context.room_variables.values()
            if variables.room.room_type not in excluded_room_types
        )

        if not included_rooms:
            return ()

        floor = context.problem.floor
        model = context.model

        any_room_present = model.NewBoolVar(
            context.new_name("floor_cluster_any_room_present")
        )
        model.AddMaxEquality(
            any_room_present,
            [variables.present for variables in included_rooms],
        )

        left_candidates = []
        right_candidates = []
        front_candidates = []

        for variables in included_rooms:
            left_candidates.append(
                self._active_left_candidate(
                    context=context,
                    variables=variables,
                )
            )
            right_candidates.append(
                self._active_right_candidate(
                    context=context,
                    variables=variables,
                )
            )
            front_candidates.append(
                self._active_front_candidate(
                    context=context,
                    variables=variables,
                )
            )

        cluster_left = model.NewIntVar(
            0,
            floor.width,
            context.new_name("floor_cluster_left"),
        )
        cluster_right = model.NewIntVar(
            0,
            floor.width,
            context.new_name("floor_cluster_right"),
        )
        cluster_front = model.NewIntVar(
            0,
            floor.length,
            context.new_name("floor_cluster_front"),
        )

        model.AddMinEquality(cluster_left, left_candidates)
        model.AddMaxEquality(cluster_right, right_candidates)
        model.AddMinEquality(cluster_front, front_candidates)

        penalties: list[PenaltyTerm] = []

        if horizontal_multiplier > 0:
            # Left margin:
            #     cluster_left
            #
            # Right margin:
            #     floor.width - cluster_right
            #
            # Their difference is:
            #     cluster_left + cluster_right - floor.width
            cluster_center_delta = model.NewIntVar(
                -floor.width,
                floor.width,
                context.new_name("floor_cluster_center_delta"),
            )
            model.Add(
                cluster_center_delta == cluster_left + cluster_right - floor.width
            )

            horizontal_distance = model.NewIntVar(
                0,
                floor.width,
                context.new_name("floor_cluster_horizontal_distance"),
            )
            model.AddAbsEquality(
                horizontal_distance,
                cluster_center_delta,
            )

            horizontal_penalty = active_linear_penalty(
                context=context,
                expression=horizontal_distance,
                upper_bound=floor.width,
                present=any_room_present,
                name="floor_cluster_horizontal_penalty",
            )

            penalties.append(
                PenaltyTerm(
                    name="floor_cluster_position:horizontal_center",
                    expression=horizontal_penalty,
                    multiplier=horizontal_multiplier,
                )
            )

        if front_multiplier > 0:
            # In the project coordinate system, y = 0 is the front.
            # Minimizing cluster_front moves the complete room cluster forward.
            front_penalty = active_linear_penalty(
                context=context,
                expression=cluster_front,
                upper_bound=floor.length,
                present=any_room_present,
                name="floor_cluster_front_penalty",
            )

            penalties.append(
                PenaltyTerm(
                    name="floor_cluster_position:front",
                    expression=front_penalty,
                    multiplier=front_multiplier,
                )
            )

        return tuple(penalties)

    @staticmethod
    def _active_left_candidate(
        context: ModelContext,
        variables: RoomVariables,
    ):
        """Return room x when present, otherwise ignore it in minimum logic."""

        floor = context.problem.floor
        candidate = context.model.NewIntVar(
            0,
            floor.width,
            context.new_name(
                "floor_cluster_left_candidate",
                variables.room.id_key,
            ),
        )

        context.model.Add(candidate == variables.x).OnlyEnforceIf(variables.present)
        context.model.Add(candidate == floor.width).OnlyEnforceIf(
            variables.present.Not()
        )

        return candidate

    @staticmethod
    def _active_right_candidate(
        context: ModelContext,
        variables: RoomVariables,
    ):
        """Return room right edge when present, otherwise ignore it."""

        floor = context.problem.floor
        candidate = context.model.NewIntVar(
            0,
            floor.width,
            context.new_name(
                "floor_cluster_right_candidate",
                variables.room.id_key,
            ),
        )

        context.model.Add(candidate == variables.x_end).OnlyEnforceIf(variables.present)
        context.model.Add(candidate == 0).OnlyEnforceIf(variables.present.Not())

        return candidate

    @staticmethod
    def _active_front_candidate(
        context: ModelContext,
        variables: RoomVariables,
    ):
        """Return room y when present, otherwise ignore it in minimum logic."""

        floor = context.problem.floor
        candidate = context.model.NewIntVar(
            0,
            floor.length,
            context.new_name(
                "floor_cluster_front_candidate",
                variables.room.id_key,
            ),
        )

        context.model.Add(candidate == variables.y).OnlyEnforceIf(variables.present)
        context.model.Add(candidate == floor.length).OnlyEnforceIf(
            variables.present.Not()
        )

        return candidate
