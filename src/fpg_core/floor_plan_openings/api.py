from __future__ import annotations

__all__ = [
    "generate_openings",
]

from .analysis import analyze_floor_plan
from .contracts import (
    OpeningDiagnostics,
    OpeningGenerationRequest,
    OpeningGenerationResult,
    OpeningGenerationStatus,
    OpeningIssue,
)
from .exceptions import OpeningInputError
from .model import build_opening_model
from .registry import OpeningFeatureRegistry, create_default_registry
from .runner import solve_opening_model
from .validation import validate_request_floor_plan


def generate_openings(
    request: OpeningGenerationRequest,
    *,
    registry: OpeningFeatureRegistry | None = None,
) -> OpeningGenerationResult:
    """Generate openings on a finalized floor plan without mutating it."""

    try:
        validate_request_floor_plan(request.floor_plan, request.profile)
        prepared = analyze_floor_plan(request.floor_plan, request.profile)
    except OpeningInputError as exc:
        return OpeningGenerationResult(
            status=OpeningGenerationStatus.INVALID_INPUT,
            floor_plan=None,
            profile_name=request.profile.name,
            message=str(exc),
            diagnostics=OpeningDiagnostics(
                raw_status="INVALID_INPUT",
                issues=(OpeningIssue("invalid_input", str(exc)),),
            ),
        )
    built = build_opening_model(
        prepared,
        request.profile,
        registry or create_default_registry(),
    )
    return solve_opening_model(request.floor_plan, built, request.profile)
