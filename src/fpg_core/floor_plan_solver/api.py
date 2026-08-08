# src/fpg_core/floor_plan_solver/api.py
from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .builder import build_model
from .config import (
    FloorPlanSolverConfig,
    HardConstraintUse,
    PreparationConfig,
    SeedPolicy,
    SeedSource,
    SoftConstraintUse,
    SolverConfig,
)
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
from .profiles import (
    DEFAULT_PROFILES,
    INITIAL_GENERATION_PROFILE,
    REFINEMENT_A_PROFILE,
    REFINEMENT_B_PROFILE,
    DefaultProfileSettings,
    GenerationProfile,
    ProfileCatalog,
    build_default_profiles,
)
from .runner import solve_built_model

__all__ = [
    "ConstraintRegistry",
    "DEFAULT_PROFILES",
    "DefaultProfileSettings",
    "FloorPlanSolveExecution",
    "FloorPlanSolveRequest",
    "FloorPlanSolveResult",
    "FloorPlanSolver",
    "FloorPlanSolverConfig",
    "GenerationProfile",
    "HardConstraintUse",
    "INITIAL_GENERATION_PROFILE",
    "PreparationConfig",
    "ProfileCatalog",
    "REFINEMENT_A_PROFILE",
    "REFINEMENT_B_PROFILE",
    "RoomPlacementHint",
    "SeedPolicy",
    "SeedSource",
    "SoftConstraintUse",
    "SolverConfig",
    "SolverDiagnostics",
    "SolverStatus",
    "build_default_profiles",
    "generate_floor_plan",
]


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
        if not isinstance(request, FloorPlanSolveRequest):
            raise TypeError("request must be a FloorPlanSolveRequest instance")
        if not isinstance(mode, ExecutionMode):
            raise TypeError("mode must be an ExecutionMode instance")

        started_at = perf_counter()
        self._registry.validate_config(request.config)
        problem = prepare_problem(request)
        built = build_model(problem, request.config, self._registry)
        result, details = solve_built_model(
            built,
            request.config,
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
