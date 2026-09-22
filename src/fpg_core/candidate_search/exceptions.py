"""Candidate-search exceptions exposed at the feature boundary."""


class CandidateSearchError(Exception):
    """Base exception for candidate-search execution failures."""


class CandidateSearchStateError(CandidateSearchError, RuntimeError):
    """Raised when session methods are called in an invalid order or state."""
