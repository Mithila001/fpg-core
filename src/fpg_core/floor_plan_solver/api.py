# src/fpg_core/floor_plan_solver/api.py
from __future__ import annotations

from time import perf_counter

__all__ = [
    "ConstraintRegistry",
    "FloorPlanSolver",
    "FloorPlanSolveExecution",
    "FloorPlanSolveRequest",
    "FloorPlanSolveResult",
    "RoomPlacementHint",
    "PreparationConfig",
    "SolverConfig",
    "SolverDiagnostics",
    "SolverStatus",
    "generate_floor_plan",
]

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .builder import build_model
from .config import PreparationConfig, SolverConfig
from .constraints.defaults import build_default_registry
from .constraints.registry import ConstraintRegistry
from .contracts import (
    FloorPlanSolveExecution,
    FloorPlanSolveRequest,
    FloorPlanSolveResult,
    RoomPlacementHint,
    SolverDiagnostics,
    SolverStatus,
)
from .preparation import prepare_problem
from .runner import solve_built_model


class FloorPlanSolver:
    """Small application service that owns one generic CP-SAT pipeline."""

    def __init__(self, registry: ConstraintRegistry | None = None) -> None:
        self._registry = registry or build_default_registry()

    @property
    def registry(self) -> ConstraintRegistry:
        return self._registry

    def solve(
        self,
        request: FloorPlanSolveRequest,
        *,
        mode: ExecutionMode = ExecutionMode.PRODUCTION,
    ) -> FloorPlanSolveExecution:
        if not isinstance(mode, ExecutionMode):
            raise TypeError("mode must be an ExecutionMode instance")

        started_at = perf_counter()
        self._registry.validate_profile(request.profile)
        problem = prepare_problem(request)
        built = build_model(problem, request.profile, self._registry)
        result, details = solve_built_model(
            built,
            request.profile,
            collect_details=mode is ExecutionMode.DEBUG,
        )
        return FeatureExecution(
            result=result,
            details=details,
            metadata=ExecutionMetadata(
                mode=mode,
                duration_seconds=perf_counter() - started_at,
            ),
        )


def generate_floor_plan(
    request: FloorPlanSolveRequest,
    *,
    registry: ConstraintRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution:
    return FloorPlanSolver(registry=registry).solve(request, mode=mode)
