from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from ..domain import FeatureExecution, FloorPlan
from .profiles import OpeningGenerationProfile


class OpeningGenerationStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    MODEL_INVALID = "model_invalid"
    UNKNOWN = "unknown"
    INVALID_INPUT = "invalid_input"

    @property
    def has_solution(self) -> bool:
        return self in {
            OpeningGenerationStatus.OPTIMAL,
            OpeningGenerationStatus.FEASIBLE,
        }


@dataclass(frozen=True, slots=True)
class OpeningIssue:
    code: str
    message: str
    feature_id: str | None = None
    demand_id: str | None = None
    wall_id: str | None = None


@dataclass(frozen=True, slots=True)
class OpeningDiagnostics:
    raw_status: str
    wall_time_seconds: float = 0.0
    objective_value: float | None = None
    best_objective_bound: float | None = None
    conflicts: int = 0
    branches: int = 0
    analyzed_wall_count: int = 0
    demand_counts: Mapping[str, int] = field(default_factory=dict)
    candidate_counts: Mapping[str, int] = field(default_factory=dict)
    selected_counts: Mapping[str, int] = field(default_factory=dict)
    applied_constraints: tuple[str, ...] = ()
    objective_terms: tuple[str, ...] = ()
    issues: tuple[OpeningIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class OpeningGenerationRequest:
    floor_plan: FloorPlan
    profile: OpeningGenerationProfile


@dataclass(frozen=True, slots=True)
class OpeningGenerationResult:
    status: OpeningGenerationStatus
    floor_plan: FloorPlan | None
    profile_name: str
    message: str

    @property
    def solved(self) -> bool:
        return self.status.has_solution and self.floor_plan is not None


OpeningGenerationExecution: TypeAlias = FeatureExecution[
    OpeningGenerationResult,
    OpeningDiagnostics,
]
