# src/fpg_core/floor_plan_scoring/api.py
from __future__ import annotations

from time import perf_counter

__all__ = [
    "EvaluatorRegistry",
    "FloorPlanScoringDetails",
    "FloorPlanScoringExecution",
    "FloorPlanScoringInput",
    "FloorPlanScoringResult",
    "ScoringProfile",
    "create_default_profile",
    "create_default_registry",
    "score_floor_plan",
]

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .config import ScoringProfile
from .contracts import (
    FloorPlanScoringDetails,
    FloorPlanScoringExecution,
    FloorPlanScoringInput,
)
from .defaults import create_default_profile, create_default_registry
from .manager import FloorPlanScoreManager
from .registry import EvaluatorRegistry
from .types import FloorPlanScoringResult


def score_floor_plan(
    scoring_input: FloorPlanScoringInput,
    *,
    registry: EvaluatorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanScoringExecution:
    """Score one completed floor plan without invoking application orchestration."""

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance")

    started_at = perf_counter()
    manager = FloorPlanScoreManager(
        registry=registry or create_default_registry(),
        profile=scoring_input.profile,
    )
    result, details = manager.score(
        scoring_input.floor_plan,
        scoring_input.specification,
        mode=mode,
    )
    return FeatureExecution(
        result=result,
        details=details,
        metadata=ExecutionMetadata(
            mode=mode,
            duration_seconds=perf_counter() - started_at,
        ),
    )
