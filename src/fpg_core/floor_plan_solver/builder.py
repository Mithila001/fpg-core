from __future__ import annotations

from ortools.sat.python import cp_model

from .config import FloorPlanSolverConfig
from .constraints.base import PenaltyTerm
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

    applied_hard: list[str] = []
    for hard_use in config.hard_constraints:
        registry.get_hard(hard_use.key).apply(context, hard_use.settings)
        applied_hard.append(hard_use.key)

    all_penalties: list[PenaltyTerm] = []
    weighted_expressions = []
    applied_soft: list[str] = []

    for soft_use in config.soft_constraints:
        terms = registry.get_soft(soft_use.key).build_penalties(
            context, soft_use.settings
        )
        applied_soft.append(soft_use.key)
        all_penalties.extend(terms)
        for term in terms:
            weighted_expressions.append(
                term.expression * (soft_use.weight * term.multiplier)
            )

    if weighted_expressions:
        context.model.Minimize(cp_model.LinearExpr.Sum(weighted_expressions))

    return BuiltModel(
        context=context,
        has_objective=bool(weighted_expressions),
        applied_hard_constraints=tuple(applied_hard),
        applied_soft_constraints=tuple(applied_soft),
        penalty_terms=tuple(term.name for term in all_penalties),
    )
