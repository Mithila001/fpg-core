# src/fpg_core/floor_plan_scoring/api.py
from __future__ import annotations

__all__ = [
    "score_floor_plan",
]

from .config import ScoringProfile
from .defaults import create_default_registry
from .domain import FloorPlan, FloorPlanGenerationSpec
from .manager import FloorPlanScoreManager
from .registry import EvaluatorRegistry
from .types import FloorPlanScoringResult


def score_floor_plan(
    floor_plan: FloorPlan,
    specification: FloorPlanGenerationSpec,
    profile: ScoringProfile,
    *,
    registry: EvaluatorRegistry | None = None,
) -> FloorPlanScoringResult:
    """Score one completed floor plan without invoking application orchestration."""

    manager = FloorPlanScoreManager(
        registry=registry or create_default_registry(),
        profile=profile,
    )
    return manager.score(floor_plan, specification)
