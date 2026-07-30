# src/fpg_core/floor_plan_solver/api.py
from __future__ import annotations

from .builder import build_model
from .constraints.defaults import build_default_registry
from .constraints.registry import ConstraintRegistry
from .contracts import FloorPlanSolveRequest, FloorPlanSolveResult
from .preparation import prepare_problem
from .runner import solve_built_model


class FloorPlanSolver:
    """Small application service that owns one generic CP-SAT pipeline."""

    def __init__(self, registry: ConstraintRegistry | None = None) -> None:
        self._registry = registry or build_default_registry()

    @property
    def registry(self) -> ConstraintRegistry:
        return self._registry

    def solve(self, request: FloorPlanSolveRequest) -> FloorPlanSolveResult:
        self._registry.validate_profile(request.profile)
        problem = prepare_problem(request)
        built = build_model(problem, request.profile, self._registry)
        return solve_built_model(built, request.profile)


def generate_floor_plan(
    request: FloorPlanSolveRequest,
    *,
    registry: ConstraintRegistry | None = None,
) -> FloorPlanSolveResult:
    return FloorPlanSolver(registry=registry).solve(request)
