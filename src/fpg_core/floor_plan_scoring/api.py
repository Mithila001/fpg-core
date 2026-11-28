"""Public API for completed floor-plan scoring."""

from __future__ import annotations

from time import perf_counter

from ..domain import (
    ExecutionMetadata,
    ExecutionMode,
    FeatureExecution,
    FloorPlan,
    FloorPlanGenerationSpec,
)
from .config import (
    EvaluatorRule,
    FloorPlanScoringConfig,
    ScoringGroupRule,
    ScoringProfile,
)
from .context import ScoringContext, ScoringContextFactory
from .contracts import (
    EvaluatorDiagnostic,
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
    LIVING_ROOM_BALANCE_KEY,
    ROOM_RELATIONSHIP_QUALITY_KEY,
    ROOM_SIZE_CONSISTENCY_KEY,
    BedroomQualityEvaluator,
    BedroomQualitySettings,
    EnclosedVoidsEvaluator,
    EnclosedVoidsSettings,
    FloorPlanEvaluator,
    GeometryIntegrityEvaluator,
    GeometryIntegritySettings,
    InwardRecessEvaluator,
    InwardRecessSettings,
    InwardRecessVisualizationData,
    LivingRoomBalanceEvaluator,
    LivingRoomBalanceSettings,
    RecessRoomBoundary,
    RecessSectionVisualization,
    RecessVisualization,
    RoomAreaAggregation,
    RoomClusteringRule,
    RoomProximityRule,
    RoomRelationshipQualityEvaluator,
    RoomRelationshipQualitySettings,
    RoomSizeConsistencyEvaluator,
    RoomSizeConsistencySettings,
    RoomSizeRelationRule,
    RoomTypeConsistencyRule,
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
from .validation import validate_config


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


def validate_scoring_input(
    floor_plan: FloorPlan, specification: FloorPlanGenerationSpec
) -> None:
    """Validate the scoring input contract without requiring passing geometry."""
    ScoringContextFactory().build(
        floor_plan, specification, mode=ExecutionMode.PRODUCTION
    )


def validate_scoring_config(config: FloorPlanScoringConfig) -> None:
    """Validate group and evaluator rules against the built-in registry."""
    validate_config(config, create_default_registry())


def diagnose_skipped_evaluators(
    scoring_input: FloorPlanScoringInput,
    official: FloorPlanScoringExecution,
    *,
    registry: EvaluatorRegistry | None = None,
) -> tuple[EvaluatorDiagnostic, ...]:
    """Independently run gated evaluators from the matching official DEBUG execution."""
    if official.metadata.mode is not ExecutionMode.DEBUG or official.details is None:
        raise ValueError(
            "Diagnostics require the official DEBUG execution for this input."
        )
    if official.result.passed_critical:
        return ()
    skipped = {
        item.evaluator_key
        for item in official.details.evaluator_results
        if item.status is EvaluationStatus.SKIPPED
        and any(f.code == "SKIPPED_AFTER_CRITICAL_FAILURE" for f in item.findings)
    }
    manager = FloorPlanScoreManager(
        registry or create_default_registry(), scoring_input.config
    )
    return manager.diagnose(
        scoring_input.floor_plan, scoring_input.specification, skipped
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
    "ROOM_RELATIONSHIP_QUALITY_KEY",
    "LIVING_ROOM_BALANCE_KEY",
    "ROOM_SIZE_CONSISTENCY_KEY",
    "BedroomQualityEvaluator",
    "BedroomQualitySettings",
    "EnclosedVoidsEvaluator",
    "EnclosedVoidsSettings",
    "EvaluatorDiagnostic",
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
    "InwardRecessVisualizationData",
    "RecessRoomBoundary",
    "RecessSectionVisualization",
    "RecessVisualization",
    "RoomRelationshipQualityEvaluator",
    "RoomClusteringRule",
    "RoomProximityRule",
    "RoomRelationshipQualitySettings",
    "LivingRoomBalanceEvaluator",
    "LivingRoomBalanceSettings",
    "RoomAreaAggregation",
    "RoomSizeConsistencyEvaluator",
    "RoomSizeConsistencySettings",
    "RoomSizeRelationRule",
    "RoomTypeConsistencyRule",
    "ScoreFinding",
    "ScoreMetric",
    "ScoringContext",
    "ScoringGroupResult",
    "ScoringGroupRule",
    "ScoringProfile",
    "create_default_config",
    "create_default_profile",
    "create_default_registry",
    "diagnose_skipped_evaluators",
    "score_floor_plan",
    "validate_scoring_config",
    "validate_scoring_input",
]
