class PostProcessingError(Exception):
    """Base error for the standalone post-processing component."""

    code = "post_processing_error"


class ConfigurationError(PostProcessingError):
    code = "invalid_configuration"


class ValidationError(PostProcessingError):
    code = "validation_failed"


class ProcessorError(PostProcessingError):
    code = "processor_failed"


class RollbackError(PostProcessingError):
    code = "rollback_failed"
