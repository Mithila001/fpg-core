"""Exceptions raised by candidate circulation refinement."""


class CandidateCirculationError(Exception):
    """Base exception for candidate circulation failures."""


class CandidateCirculationInputError(CandidateCirculationError, ValueError):
    """Raised when the circulation input or configuration is invalid."""


class GridAlignmentError(CandidateCirculationInputError):
    """Raised when a hint point does not align with the configured grid."""


class CirculationPathNotFoundError(CandidateCirculationError):
    """Raised when a configured route cannot be resolved on the grid."""
