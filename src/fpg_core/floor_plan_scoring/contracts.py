from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from ..domain import FeatureExecution, FloorPlan, FloorPlanGenerationSpec
from .config import FloorPlanScoringConfig
from .types import (
    EvaluatorExecutionResult,
    FloorPlanScoringResult,
    ScoreFinding,
    ScoringGroupResult,
)


@dataclass(frozen=True, slots=True)
class FloorPlanScoringInput:
    """Request-specific scoring data plus reusable scoring configuration."""

    floor_plan: FloorPlan
    specification: FloorPlanGenerationSpec
    config: FloorPlanScoringConfig

    def __post_init__(self) -> None:
        if not isinstance(self.floor_plan, FloorPlan):
            raise TypeError("floor_plan must be a FloorPlan instance.")
        if not isinstance(self.specification, FloorPlanGenerationSpec):
            raise TypeError(
                "specification must be a FloorPlanGenerationSpec instance."
            )
        if not isinstance(self.config, FloorPlanScoringConfig):
            raise TypeError("config must be a FloorPlanScoringConfig instance.")


@dataclass(frozen=True, slots=True)
class FloorPlanScoringDetails:
    """DEBUG-only scoring breakdown and evaluator diagnostics."""

    group_results: tuple[ScoringGroupResult, ...]
    evaluator_results: tuple[EvaluatorExecutionResult, ...]
    findings: tuple[ScoreFinding, ...] = ()


FloorPlanScoringExecution: TypeAlias = FeatureExecution[
    FloorPlanScoringResult,
    FloorPlanScoringDetails,
]


__all__ = [
    "FloorPlanScoringDetails",
    "FloorPlanScoringExecution",
    "FloorPlanScoringInput",
]
