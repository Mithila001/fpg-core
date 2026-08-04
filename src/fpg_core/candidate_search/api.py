"""Public entry points and contracts for Candidate Search."""

from ..domain import FloorPlanGenerationSpec
from .grid import build_candidate_grid
from .models import (
    CandidateEvaluator,
    CandidateSearchDetails,
    CandidateSearchInput,
    CandidateSearchResult,
    CandidateSearchSettings,
    CandidateSearchTarget,
    CandidateSuggestion,
    CandidateTrialResult,
)
from .optimizer import CandidateSearchSession, search_candidates

__all__ = [
    "CandidateEvaluator",
    "CandidateSearchDetails",
    "CandidateSearchInput",
    "CandidateSearchResult",
    "CandidateSearchSession",
    "CandidateSearchSettings",
    "CandidateSearchTarget",
    "CandidateSuggestion",
    "CandidateTrialResult",
    "build_candidate_grid",
    "build_candidate_search_targets",
    "search_candidates",
]


def build_candidate_search_targets(
    specification: FloorPlanGenerationSpec,
) -> tuple[CandidateSearchTarget, ...]:
    """Create one concrete Candidate Search target for every prepared room."""

    if not isinstance(specification, FloorPlanGenerationSpec):
        raise TypeError(
            "specification must be a FloorPlanGenerationSpec instance."
        )
    return tuple(
        CandidateSearchTarget(
            room_id=room.id,
            room_type=room.room_type,
        )
        for room in specification.rooms
    )
