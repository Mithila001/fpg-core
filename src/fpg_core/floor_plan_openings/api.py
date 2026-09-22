from __future__ import annotations

from time import perf_counter

from ..domain import ExecutionMetadata, ExecutionMode, FeatureExecution
from .analysis import analyze_floor_plan
from .config import (
    DimensionConfig,
    FeaturePolicy,
    FloorPlanOpeningsConfig,
    GeometryConfig,
    ObjectiveConfig,
    SolverConfig,
)
from .contracts import (
    OpeningDiagnostics,
    OpeningGenerationExecution,
    OpeningGenerationRequest,
    OpeningGenerationResult,
    OpeningGenerationStatus,
    OpeningIssue,
)
from .exceptions import (
    OpeningConfigurationError,
    OpeningGenerationError,
    OpeningInputError,
)
from .model import build_opening_model
from .profiles import (
    DEFAULT_OPENING_CONFIG,
    DEFAULT_OPENING_PROFILE,
    OpeningGenerationProfile,
)
from .registry import OpeningFeatureRegistry, create_default_registry
from .runner import solve_opening_model
from .validation import validate_request_floor_plan

__all__ = [
    "DEFAULT_OPENING_CONFIG",
    "DEFAULT_OPENING_PROFILE",
    "DimensionConfig",
    "FeaturePolicy",
    "FloorPlanOpeningsConfig",
    "GeometryConfig",
    "ObjectiveConfig",
    "OpeningConfigurationError",
    "OpeningDiagnostics",
    "OpeningFeatureRegistry",
    "OpeningGenerationError",
    "OpeningGenerationExecution",
    "OpeningGenerationProfile",
    "OpeningGenerationRequest",
    "OpeningGenerationResult",
    "OpeningGenerationStatus",
    "OpeningIssue",
    "SolverConfig",
    "create_default_registry",
    "generate_openings",
]


def generate_openings(
    request: OpeningGenerationRequest,
    *,
    registry: OpeningFeatureRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> OpeningGenerationExecution:
    """Generate openings on a finalized floor plan without mutating it."""

    if not isinstance(request, OpeningGenerationRequest):
        raise TypeError("request must be an OpeningGenerationRequest instance")
    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode must be an ExecutionMode instance")

    started_at = perf_counter()
    try:
        validate_request_floor_plan(request.floor_plan, request.config)
        prepared = analyze_floor_plan(request.floor_plan, request.config)
    except OpeningInputError as exc:
        result = OpeningGenerationResult(
            status=OpeningGenerationStatus.INVALID_INPUT,
            floor_plan=None,
            profile_name=request.config.name,
            message=str(exc),
        )
        details = (
            OpeningDiagnostics(
                raw_status="INVALID_INPUT",
                issues=(OpeningIssue("invalid_input", str(exc)),),
            )
            if mode is ExecutionMode.DEBUG
            else None
        )
        return FeatureExecution(
            result=result,
            details=details,
            metadata=ExecutionMetadata(
                mode=mode,
                duration_seconds=perf_counter() - started_at,
            ),
        )
    built = build_opening_model(
        prepared,
        request.config,
        registry or create_default_registry(),
    )
    result, details = solve_opening_model(
        request.floor_plan,
        built,
        request.config,
        collect_details=mode is ExecutionMode.DEBUG,
    )
    return FeatureExecution(
        result=result,
        details=details,
        metadata=ExecutionMetadata(
            mode=mode,
            duration_seconds=perf_counter() - started_at,
        ),
    )
