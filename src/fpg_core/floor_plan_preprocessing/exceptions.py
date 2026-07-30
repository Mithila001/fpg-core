from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class PreprocessingStage(StrEnum):
    INPUT_VALIDATION = "input_validation"
    NORMALIZATION = "normalization"
    REFERENCE_DATA = "reference_data"
    BUSINESS_RULES = "business_rules"
    ROOM_PREPARATION = "room_preparation"
    RELATION_PREPARATION = "relation_preparation"
    FLOOR_PREPARATION = "floor_preparation"
    CONTEXT_VALIDATION = "context_validation"
    OUTPUT_VALIDATION = "output_validation"


class PreprocessingErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    INVALID_ASPECT_RATIO = "invalid_aspect_ratio"
    INVALID_ROOM_COUNT = "invalid_room_count"
    FORBIDDEN_ROOM_TYPE = "forbidden_room_type"
    DUPLICATE_ROOM_ID = "duplicate_room_id"
    ATTACHED_BATHROOM_COUNT_EXCEEDS_BEDROOMS = (
        "attached_bathroom_count_exceeds_bedrooms"
    )
    NORMALIZATION_FAILED = "normalization_failed"
    INVALID_REFERENCE_DATA = "invalid_reference_data"
    MISSING_ROOM_REFERENCE = "missing_room_reference"
    INVALID_ROOM_RELATION = "invalid_room_relation"
    FLOOR_LIMITS_INSUFFICIENT = "floor_limits_insufficient"
    INVALID_PREPARED_CONTEXT = "invalid_prepared_context"
    INVALID_PREPROCESSING_OUTPUT = "invalid_preprocessing_output"


class FloorPlanPreprocessingError(Exception):
    """Base class for expected preprocessing failures."""

    stage = PreprocessingStage.INPUT_VALIDATION
    default_code = PreprocessingErrorCode.INVALID_INPUT

    def __init__(
        self,
        message: str,
        *,
        code: PreprocessingErrorCode | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = MappingProxyType(dict(details or {}))


class InputValidationError(FloorPlanPreprocessingError):
    pass


class NormalizationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.NORMALIZATION
    default_code = PreprocessingErrorCode.NORMALIZATION_FAILED


class ReferenceDataError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.REFERENCE_DATA
    default_code = PreprocessingErrorCode.INVALID_REFERENCE_DATA


class BusinessRuleError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.BUSINESS_RULES
    default_code = PreprocessingErrorCode.INVALID_ROOM_COUNT


class RoomPreparationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.ROOM_PREPARATION
    default_code = PreprocessingErrorCode.MISSING_ROOM_REFERENCE


class RelationPreparationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.RELATION_PREPARATION
    default_code = PreprocessingErrorCode.INVALID_ROOM_RELATION


class FloorPreparationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.FLOOR_PREPARATION
    default_code = PreprocessingErrorCode.FLOOR_LIMITS_INSUFFICIENT


class ContextValidationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.CONTEXT_VALIDATION
    default_code = PreprocessingErrorCode.INVALID_PREPARED_CONTEXT


class OutputValidationError(FloorPlanPreprocessingError):
    stage = PreprocessingStage.OUTPUT_VALIDATION
    default_code = PreprocessingErrorCode.INVALID_PREPROCESSING_OUTPUT
