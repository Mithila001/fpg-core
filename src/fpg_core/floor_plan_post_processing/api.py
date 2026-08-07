from __future__ import annotations

from time import perf_counter

__all__ = [
    "FloorPlanProcessor",
    "PostProcessingDetails",
    "PostProcessingExecution",
    "PostProcessingProfile",
    "PostProcessingRequest",
    "PostProcessingResult",
    "ProcessorRegistry",
    "create_default_registry",
    "post_process_floor_plan",
]

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .contracts import (
    FloorPlanProcessor,
    PostProcessingDetails,
    PostProcessingExecution,
    PostProcessingProfile,
    PostProcessingRequest,
    PostProcessingResult,
)
from .pipeline import run_pipeline
from .profiles import create_default_registry
from .registry import ProcessorRegistry


def post_process_floor_plan(
    request: PostProcessingRequest,
    *,
    registry: ProcessorRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> PostProcessingExecution:
    """Run the selected standalone transformation profile on one typed floor plan."""

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
