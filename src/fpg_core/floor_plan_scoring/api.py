"""Public API for completed floor-plan scoring."""

from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .config import (
    EvaluatorRule,
    FloorPlanScoringConfig,
    ScoringGroupRule,
    ScoringProfile,
)
from .context import ScoringContext
from .contracts import (
    FloorPlanScoringDetails,
    FloorPlanScoringExecution,
    FloorPlanScoringInput,
)
from .defaults import (
    DEFAULT_FLOOR_PLAN_SCORING_CONFIG,
    DEFAULT_SCORING_PROFILE,
    create_default_config,
    create_default_profile,
    create_default_registry,
)
from .evaluators import (
    BEDROOM_QUALITY_KEY,
    ENCLOSED_VOIDS_KEY,
    GEOMETRY_INTEGRITY_KEY,
    INWARD_RECESS_KEY,
    KITCHEN_DINING_KEY,
    LIVING_ROOM_BALANCE_KEY,
    REQUIRED_ADJACENCY_KEY,
    BedroomQualityEvaluator,
    BedroomQualitySettings,
    EnclosedVoidsEvaluator,
    EnclosedVoidsSettings,
    FloorPlanEvaluator,
    GeometryIntegrityEvaluator,
    GeometryIntegritySettings,
    InwardRecessEvaluator,
    InwardRecessSettings,
    KitchenDiningEvaluator,
    KitchenDiningSettings,
    LivingRoomBalanceEvaluator,
    LivingRoomBalanceSettings,
    RequiredAdjacencyEvaluator,
    RequiredAdjacencySettings,
)
from .manager import FloorPlanScoreManager
from .registry import EvaluatorRegistry
from .types import (
    AESTHETIC_GROUP,
    CRITICAL_GROUP,
    EXTRA_GROUP,
    FUNCTIONAL_GROUP,
    EvaluationStatus,
    EvaluatorExecutionResult,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    FloorPlanScoringResult,
    GroupKey,
    GroupStatus,
    ScoreFinding,
    ScoreMetric,
    ScoringGroupResult,
)


def score_floor_plan(
    scoring_input: FloorPlanScoringInput,
    *,
    registry: EvaluatorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanScoringExecution:
    """Score one completed floor plan without application-layer orchestration."""

    if not isinstance(scoring_input, FloorPlanScoringInput):
        raise TypeError("scoring_input must be a FloorPlanScoringInput instance.")
    if registry is not None and not isinstance(registry, EvaluatorRegistry):
        raise TypeError("registry must be an EvaluatorRegistry instance or None.")
    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance.")

    started_at = perf_counter()
    manager = FloorPlanScoreManager(
        registry=registry or create_default_registry(),
        config=scoring_input.config,
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


__all__ = [
    "AESTHETIC_GROUP",
    "BEDROOM_QUALITY_KEY",
    "CRITICAL_GROUP",
    "DEFAULT_FLOOR_PLAN_SCORING_CONFIG",
    "DEFAULT_SCORING_PROFILE",
    "ENCLOSED_VOIDS_KEY",
    "EXTRA_GROUP",
    "FUNCTIONAL_GROUP",
    "GEOMETRY_INTEGRITY_KEY",
    "INWARD_RECESS_KEY",
    "KITCHEN_DINING_KEY",
    "LIVING_ROOM_BALANCE_KEY",
    "REQUIRED_ADJACENCY_KEY",
    "BedroomQualityEvaluator",
    "BedroomQualitySettings",
    "EnclosedVoidsEvaluator",
    "EnclosedVoidsSettings",
    "EvaluationStatus",
    "EvaluatorExecutionResult",
    "EvaluatorKey",
    "EvaluatorRegistry",
    "EvaluatorResult",
    "EvaluatorRule",
    "FindingSeverity",
    "FloorPlanEvaluator",
    "FloorPlanScoringConfig",
    "FloorPlanScoringDetails",
    "FloorPlanScoringExecution",
    "FloorPlanScoringInput",
    "FloorPlanScoringResult",
    "GeometryIntegrityEvaluator",
    "GeometryIntegritySettings",
    "GroupKey",
    "GroupStatus",
    "InwardRecessEvaluator",
    "InwardRecessSettings",
    "KitchenDiningEvaluator",
    "KitchenDiningSettings",
    "LivingRoomBalanceEvaluator",
    "LivingRoomBalanceSettings",
    "RequiredAdjacencyEvaluator",
    "RequiredAdjacencySettings",
    "ScoreFinding",
    "ScoreMetric",
    "ScoringContext",
    "ScoringGroupResult",
    "ScoringGroupRule",
    "ScoringProfile",
    "create_default_config",
    "create_default_profile",
    "create_default_registry",
    "score_floor_plan",
]
