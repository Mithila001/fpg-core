from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from ..domain import FeatureExecution, FloorPlan, FloorPlanGenerationSpec
from .config import ScoringProfile
from .types import (
    EvaluatorExecutionResult,
    FloorPlanScoringResult,
    ScoreFinding,
    ScoringGroupResult,
)


@dataclass(frozen=True, slots=True)
class FloorPlanScoringInput:
    floor_plan: FloorPlan
    specification: FloorPlanGenerationSpec
    profile: ScoringProfile


@dataclass(frozen=True, slots=True)
class FloorPlanScoringDetails:
    group_results: tuple[ScoringGroupResult, ...]
    evaluator_results: tuple[EvaluatorExecutionResult, ...]
    findings: tuple[ScoreFinding, ...] = ()


FloorPlanScoringExecution: TypeAlias = FeatureExecution[
    FloorPlanScoringResult,
    FloorPlanScoringDetails,
]
