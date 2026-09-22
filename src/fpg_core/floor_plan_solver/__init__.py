"""CP-SAT floor-plan solver public API.

Exports are loaded lazily so importing configuration or unrelated core features does
not initialize OR-Tools.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import FloorPlanSolver, generate_floor_plan
    from .config import (
        FloorPlanSolverConfig,
        HardConstraintUse,
        PreparationConfig,
        SeedPolicy,
        SeedSource,
        SoftConstraintUse,
        SolverConfig,
    )
    from .constraints.registry import ConstraintRegistry
    from .contracts import (
        FloorPlanSolveExecution,
        FloorPlanSolveRequest,
        FloorPlanSolveResult,
        RoomPlacementHint,
        SolverDiagnostics,
        SolverStatus,
    )
    from .exceptions import FloorPlanSolverError
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

_EXPORTS: dict[str, tuple[str, str]] = {
    "FloorPlanSolver": (".api", "FloorPlanSolver"),
    "generate_floor_plan": (".api", "generate_floor_plan"),
    "ConstraintRegistry": (".constraints.registry", "ConstraintRegistry"),
    "FloorPlanSolverConfig": (".config", "FloorPlanSolverConfig"),
    "HardConstraintUse": (".config", "HardConstraintUse"),
    "PreparationConfig": (".config", "PreparationConfig"),
    "SeedPolicy": (".config", "SeedPolicy"),
    "SeedSource": (".config", "SeedSource"),
    "SoftConstraintUse": (".config", "SoftConstraintUse"),
    "SolverConfig": (".config", "SolverConfig"),
    "FloorPlanSolveRequest": (".contracts", "FloorPlanSolveRequest"),
    "FloorPlanSolveExecution": (".contracts", "FloorPlanSolveExecution"),
    "FloorPlanSolveResult": (".contracts", "FloorPlanSolveResult"),
    "RoomPlacementHint": (".contracts", "RoomPlacementHint"),
    "SolverDiagnostics": (".contracts", "SolverDiagnostics"),
    "SolverStatus": (".contracts", "SolverStatus"),
    "DEFAULT_PROFILES": (".profiles", "DEFAULT_PROFILES"),
    "INITIAL_GENERATION_PROFILE": (".profiles", "INITIAL_GENERATION_PROFILE"),
    "REFINEMENT_A_PROFILE": (".profiles", "REFINEMENT_A_PROFILE"),
    "REFINEMENT_B_PROFILE": (".profiles", "REFINEMENT_B_PROFILE"),
    "DefaultProfileSettings": (".profiles", "DefaultProfileSettings"),
    "GenerationProfile": (".profiles", "GenerationProfile"),
    "ProfileCatalog": (".profiles", "ProfileCatalog"),
    "build_default_profiles": (".profiles", "build_default_profiles"),
    "FloorPlanSolverError": (".exceptions", "FloorPlanSolverError"),
}

__all__ = [
    "DEFAULT_PROFILES",
    "DefaultProfileSettings",
    "ConstraintRegistry",
    "FloorPlanSolveExecution",
    "FloorPlanSolveRequest",
    "FloorPlanSolveResult",
    "FloorPlanSolver",
    "FloorPlanSolverConfig",
    "FloorPlanSolverError",
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


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc

    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
