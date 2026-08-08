from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from ..domain import RoomWidthAxis
from .config import FloorPlanSolverConfig
from .preparation import PreparedProblem, PreparedRoom


@dataclass(slots=True)
class RoomVariables:
    room: PreparedRoom
    present: Any
    x: Any
    y: Any
    width: Any
    length: Any
    x_end: Any
    y_end: Any
    area: Any
    x_interval: Any
    y_interval: Any


@dataclass(slots=True)
class ModelContext:
    model: Any
    problem: PreparedProblem
    config: FloorPlanSolverConfig
    room_variables: dict[str, RoomVariables]
    adjacency_cache: dict[tuple[str, str, int], Any] = field(default_factory=dict)
    _name_counter: int = 0

    def variables_for(self, room_id_key: str) -> RoomVariables:
        return self.room_variables[room_id_key]

    def new_name(self, prefix: str, *parts: object) -> str:
        self._name_counter += 1
        suffix = "_".join(str(part) for part in parts if str(part))
        if suffix:
            return f"{prefix}_{suffix}_{self._name_counter}"
        return f"{prefix}_{self._name_counter}"


@dataclass(frozen=True, slots=True)
class BuiltModel:
    context: ModelContext
    has_objective: bool
    applied_hard_constraints: tuple[str, ...]
    applied_soft_constraints: tuple[str, ...]
    penalty_terms: tuple[str, ...]


def _create_room_variables(
    model: Any,
    problem: PreparedProblem,
    room: PreparedRoom,
) -> RoomVariables:
    prefix = room.variable_name
    floor = problem.floor

    # Presence is retained as an internal literal for constraint composition,
    # but it is an invariant: every supplied room must exist in the solution.
    present = model.NewBoolVar(f"{prefix}_present")
    model.Add(present == 1)
    x = model.NewIntVar(0, floor.width, f"{prefix}_x")
    y = model.NewIntVar(0, floor.length, f"{prefix}_y")
    width = model.NewIntVar(0, room.max_width, f"{prefix}_width")
    length = model.NewIntVar(0, room.max_length, f"{prefix}_length")
    x_end = model.NewIntVar(0, floor.width, f"{prefix}_x_end")
    y_end = model.NewIntVar(0, floor.length, f"{prefix}_y_end")
    area = model.NewIntVar(0, room.max_area, f"{prefix}_area")

    model.Add(x_end == x + width)
    model.Add(y_end == y + length)
    model.AddMultiplicationEquality(area, [width, length])

    model.Add(width >= room.min_width)
    model.Add(length >= room.min_length)
    model.Add(area >= room.min_area)
    model.Add(area <= room.max_area)

    if room.width_axis is RoomWidthAxis.X:
        # The reference min_width/max_width range applies to the X span.
        model.Add(width <= room.max_short_side)

    elif room.width_axis is RoomWidthAxis.Y:
        # The reference min_width/max_width range applies to the Y span.
        model.Add(length <= room.max_short_side)

    else:
        # Existing behavior: either axis may be the constrained width side.
        width_is_short = model.NewBoolVar(f"{prefix}_width_is_short")
        length_is_short = model.NewBoolVar(f"{prefix}_length_is_short")

        model.Add(width <= room.max_short_side).OnlyEnforceIf(width_is_short)

        model.Add(length <= room.max_short_side).OnlyEnforceIf(length_is_short)

        model.AddBoolOr([width_is_short, length_is_short])

    x_interval = model.NewIntervalVar(x, width, x_end, f"{prefix}_x_interval")
    y_interval = model.NewIntervalVar(y, length, y_end, f"{prefix}_y_interval")

    return RoomVariables(
        room=room,
        present=present,
        x=x,
        y=y,
        width=width,
        length=length,
        x_end=x_end,
        y_end=y_end,
        area=area,
        x_interval=x_interval,
        y_interval=y_interval,
    )


def create_model_context(
    problem: PreparedProblem,
    config: FloorPlanSolverConfig,
) -> ModelContext:
    """Create variables and mandatory model invariants.

    Containment, room size/area ranges, required-room presence, and non-overlap
    are structural invariants. Configurations cannot disable them.
    """

    model: Any = cp_model.CpModel()
    room_variables = {
        room.id_key: _create_room_variables(model, problem, room)
        for room in problem.rooms
    }

    model.AddNoOverlap2D(
        [variables.x_interval for variables in room_variables.values()],
        [variables.y_interval for variables in room_variables.values()],
    )

    return ModelContext(
        model=model,
        problem=problem,
        config=config,
        room_variables=room_variables,
    )


def _bounded_constraint(
    model: Any,
    variable: Any,
    lower: int,
    upper: int,
) -> None:
    model.Add(variable >= min(lower, upper))
    model.Add(variable <= max(lower, upper))


def apply_seed_policy(context: ModelContext) -> None:
    seed = context.problem.seed
    policy = context.config.seed
    if seed is None:
        return

    scale = context.problem.scale
    floor = context.problem.floor
    position_delta = (
        scale.minimum_length(policy.position_tolerance)
        if policy.position_tolerance is not None
        else None
    )
    size_delta = (
        scale.minimum_length(policy.size_tolerance)
        if policy.size_tolerance is not None
        else None
    )

    for room_id_key, room_seed in seed.rooms.items():
        variables = context.room_variables.get(room_id_key)
        if variables is None:
            continue
        room = variables.room

        if policy.apply_hints:
            context.model.AddHint(variables.x, room_seed.x)
            context.model.AddHint(variables.y, room_seed.y)
            if room_seed.width is not None:
                context.model.AddHint(variables.width, room_seed.width)
            if room_seed.length is not None:
                context.model.AddHint(variables.length, room_seed.length)

        if position_delta is not None:
            _bounded_constraint(
                context.model,
                variables.x,
                max(0, room_seed.x - position_delta),
                min(floor.width - room.min_width, room_seed.x + position_delta),
            )
            _bounded_constraint(
                context.model,
                variables.y,
                max(0, room_seed.y - position_delta),
                min(floor.length - room.min_length, room_seed.y + position_delta),
            )

        if size_delta is not None and room_seed.width is not None:
            _bounded_constraint(
                context.model,
                variables.width,
                max(room.min_width, room_seed.width - size_delta),
                min(room.max_width, room_seed.width + size_delta),
            )
        if size_delta is not None and room_seed.length is not None:
            _bounded_constraint(
                context.model,
                variables.length,
                max(room.min_length, room_seed.length - size_delta),
                min(room.max_length, room_seed.length + size_delta),
            )
