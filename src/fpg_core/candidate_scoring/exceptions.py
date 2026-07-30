class CandidateScoringError(Exception):
    """Base exception for the candidate scoring framework."""


class ScoringConfigurationError(CandidateScoringError):
    """Raised when manager or evaluator configuration is invalid."""


class ScoringInputError(CandidateScoringError):
    """Raised when the candidate scoring input is structurally invalid."""


class EvaluatorContractError(CandidateScoringError):
    """Raised when an evaluator violates the standard evaluator contract."""


class EvaluatorRegistrationError(CandidateScoringError):
    """Raised for duplicate or missing evaluator registrations."""
