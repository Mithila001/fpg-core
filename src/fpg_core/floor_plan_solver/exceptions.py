class FloorPlanSolverError(Exception):
    """Base exception for invalid solver input or configuration."""


class InvalidSpecificationError(FloorPlanSolverError):
    """Raised when the generation specification cannot form a valid model."""


class InvalidProfileError(FloorPlanSolverError):
    """Raised when a generation profile is invalid."""


class MissingSeedError(FloorPlanSolverError):
    """Raised when a profile requires seed data that was not supplied."""


class UnknownConstraintError(InvalidProfileError):
    """Raised when a profile refers to an unregistered constraint."""
