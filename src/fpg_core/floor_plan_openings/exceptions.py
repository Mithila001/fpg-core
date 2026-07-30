class OpeningGenerationError(Exception):
    """Base class for opening-generation failures."""


class OpeningConfigurationError(OpeningGenerationError):
    """Raised for programmer-facing profile or registry errors."""


class OpeningInputError(OpeningGenerationError):
    """Raised when a floor plan cannot be analyzed safely."""


class OpeningExtractionError(OpeningGenerationError):
    """Raised when a solved model cannot be converted safely."""
