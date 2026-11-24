from __future__ import annotations

from ortools.sat.python import cp_model

from ..domain import RoomType
from .config import FloorPlanSolverConfig
from .constraints.registry import ConstraintRegistry
from .model import BuiltModel, apply_seed_policy, create_model_context
from .preparation import PreparedProblem


def build_model(
    problem: PreparedProblem,
    config: FloorPlanSolverConfig,
    registry: ConstraintRegistry,
) -> BuiltModel:
    registry.validate_config(config)
    context = create_model_context(problem, config)
    apply_seed_policy(context)
    for variables in context.room_variables.values():
        if variables.room.room_type == RoomType.HALLWAY:
            context.model.Add(variables.width >= problem.scale.minimum_length(10)).OnlyEnforceIf(variables.present)
            context.model.Add(variables.length >= problem.scale.minimum_length(10)).OnlyEnforceIf(variables.present)

    applied_hard: list[str] = []
    for hard_use in config.hard_constraints:
        registry.get_hard(hard_use.key).apply(context, hard_use.settings)
        applied_hard.append(hard_use.key)

    weighted_expressions = []
    applied_soft: list[str] = []

    for soft_use in config.soft_constraints:
        if soft_use.weight == 0:
            continue
        soft_constraint_penalty = registry.get_soft(soft_use.key).build_penalty(
            context, soft_use.settings
        )
        if type(soft_constraint_penalty) is int and soft_constraint_penalty == 0:
            continue
        applied_soft.append(soft_use.key)
        weighted_expressions.append(soft_constraint_penalty * round(soft_use.weight * 10))

    if weighted_expressions:
        context.model.Minimize(cp_model.LinearExpr.Sum(weighted_expressions))

    return BuiltModel(
        context=context,
        has_objective=bool(weighted_expressions),
        applied_hard_constraints=tuple(applied_hard),
        applied_soft_constraints=tuple(applied_soft),
        penalty_terms=tuple(applied_soft),
    )
