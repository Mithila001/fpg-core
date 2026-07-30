"""CP-SAT floor-plan solver public API.

Exports are loaded lazily so importing configuration or unrelated core features does
not initialize OR-Tools.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import FloorPlanSolver, generate_floor_plan
    from .contracts import (
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
        GenerationProfile,
        HardConstraintUse,
        SoftConstraintUse,
        build_default_profiles,
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    "FloorPlanSolver": (".api", "FloorPlanSolver"),
    "generate_floor_plan": (".api", "generate_floor_plan"),
    "FloorPlanSolveRequest": (".contracts", "FloorPlanSolveRequest"),
    "FloorPlanSolveResult": (".contracts", "FloorPlanSolveResult"),
    "RoomPlacementHint": (".contracts", "RoomPlacementHint"),
    "SolverDiagnostics": (".contracts", "SolverDiagnostics"),
    "SolverStatus": (".contracts", "SolverStatus"),
    "DEFAULT_PROFILES": (".profiles", "DEFAULT_PROFILES"),
    "INITIAL_GENERATION_PROFILE": (".profiles", "INITIAL_GENERATION_PROFILE"),
    "REFINEMENT_A_PROFILE": (".profiles", "REFINEMENT_A_PROFILE"),
    "REFINEMENT_B_PROFILE": (".profiles", "REFINEMENT_B_PROFILE"),
    "GenerationProfile": (".profiles", "GenerationProfile"),
    "HardConstraintUse": (".profiles", "HardConstraintUse"),
    "SoftConstraintUse": (".profiles", "SoftConstraintUse"),
    "build_default_profiles": (".profiles", "build_default_profiles"),
    "FloorPlanSolverError": (".exceptions", "FloorPlanSolverError"),
}

__all__ = list(_EXPORTS)


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
