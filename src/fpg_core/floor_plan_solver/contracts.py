from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from ..domain import FeatureExecution, FloorPlan, FloorPlanGenerationSpec, RoomId
from .profiles import GenerationProfile


@dataclass(frozen=True, slots=True)
class RoomPlacementHint:
    """Candidate-search hint for a room's lower-left position and optional size."""

    room_id: RoomId
    x: float
    y: float
    width: float | None = None
    length: float | None = None

    def __post_init__(self) -> None:
        if self.width is not None and self.width <= 0:
            raise ValueError("Hint width must be greater than zero")
        if self.length is not None and self.length <= 0:
            raise ValueError("Hint length must be greater than zero")


@dataclass(frozen=True, slots=True)
class FloorPlanSolveRequest:
    specification: FloorPlanGenerationSpec
    profile: GenerationProfile
    candidate_hints: tuple[RoomPlacementHint, ...] = ()
    existing_floor_plan: FloorPlan | None = None


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    MODEL_INVALID = "model_invalid"
    UNKNOWN = "unknown"

    @property
    def has_solution(self) -> bool:
        return self in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}


@dataclass(frozen=True, slots=True)
class SolverDiagnostics:
    raw_status: str
    wall_time_seconds: float
    objective_value: float | None
    best_objective_bound: float | None
    conflicts: int
    branches: int
    applied_hard_constraints: tuple[str, ...]
    applied_soft_constraints: tuple[str, ...]
    penalty_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FloorPlanSolveResult:
    status: SolverStatus
    floor_plan: FloorPlan | None
    profile_name: str
    message: str

    @property
    def solved(self) -> bool:
        return self.status.has_solution and self.floor_plan is not None


FloorPlanSolveExecution: TypeAlias = FeatureExecution[
    FloorPlanSolveResult,
    SolverDiagnostics,
]
