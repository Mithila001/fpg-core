from __future__ import annotations

from .contracts import PostProcessingRequest, PostProcessingResult
from .pipeline import run_pipeline
from .profiles import create_default_registry
from .registry import ProcessorRegistry


def post_process_floor_plan(
    request: PostProcessingRequest,
    *,
    registry: ProcessorRegistry | None = None,
) -> PostProcessingResult:
    """Run the selected standalone transformation profile on one typed floor plan."""

    return run_pipeline(request, registry or create_default_registry())
