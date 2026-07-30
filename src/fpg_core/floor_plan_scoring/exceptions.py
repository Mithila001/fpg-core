class FloorPlanScoringError(Exception):
    """Base exception for the floor-plan scoring package."""


class ScoringInputError(FloorPlanScoringError):
    """Raised when floor-plan or specification data is structurally broken."""


class ScoringConfigurationError(FloorPlanScoringError):
    """Raised when a scoring profile or registry is inconsistent."""


class EvaluatorRegistrationError(FloorPlanScoringError):
    """Raised for duplicate or missing evaluator registrations."""


class EvaluatorContractError(FloorPlanScoringError):
    """Raised when an evaluator returns a result outside the common contract."""


class EvaluatorExecutionError(FloorPlanScoringError):
    """Raised when an evaluator fails unexpectedly while scoring."""
