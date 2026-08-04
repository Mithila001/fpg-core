"""Public entry points and contracts for candidate search."""

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
    "search_candidates",
]
