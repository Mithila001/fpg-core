from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .config import (
    FloorPlanPostProcessingConfig,
    GridSnapConfig,
    HallwayMergeConfig,
    NumericPolicy,
    PlaceholderRemovalConfig,
    PostProcessingProfile,
    ProcessorUse,
    RectilinearSimplificationConfig,
    VerandaAdjustmentConfig,
    WallExtensionConfig,
    WallExtensionRule,
)
from .contracts import (
    FloorPlanProcessor,
    PipelineStatus,
    PostProcessingContext,
    PostProcessingDetails,
    PostProcessingExecution,
    PostProcessingRequest,
    PostProcessingResult,
    ProcessingFailure,
    ProcessorExecution,
    ProcessorOutcome,
    ProcessorStatus,
)
from .exceptions import (
    ConfigurationError,
    PostProcessingError,
    ProcessorError,
    RollbackError,
    ValidationError,
)
from .pipeline import run_pipeline
from .profiles import INITIAL_GENERATION_PROFILE, create_default_registry
from .registry import ProcessorRegistry

__all__ = [
    "ConfigurationError",
    "FloorPlanPostProcessingConfig",
    "FloorPlanProcessor",
    "GridSnapConfig",
    "HallwayMergeConfig",
    "INITIAL_GENERATION_PROFILE",
    "NumericPolicy",
    "PipelineStatus",
    "PlaceholderRemovalConfig",
    "PostProcessingContext",
    "PostProcessingDetails",
    "PostProcessingError",
    "PostProcessingExecution",
    "PostProcessingProfile",
    "PostProcessingRequest",
    "PostProcessingResult",
    "ProcessingFailure",
    "ProcessorError",
    "ProcessorExecution",
    "ProcessorOutcome",
    "ProcessorRegistry",
    "ProcessorStatus",
    "ProcessorUse",
    "RectilinearSimplificationConfig",
    "RollbackError",
    "ValidationError",
    "VerandaAdjustmentConfig",
    "WallExtensionConfig",
    "WallExtensionRule",
    "create_default_registry",
    "post_process_floor_plan",
]


def post_process_floor_plan(
    request: PostProcessingRequest,
    *,
    registry: ProcessorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PostProcessingExecution:
    """Run one configured post-processing pipeline on a typed floor plan."""

    if not isinstance(request, PostProcessingRequest):
        raise TypeError("request must be a PostProcessingRequest instance")
    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance")

    started_at = perf_counter()
    result, details = run_pipeline(
        request,
        registry or create_default_registry(),
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
