from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from ..domain import (
    FeatureExecution,
    FloorPlanGenerationSpec,
    RoomType,
)
from .config import PreprocessingConfig


@dataclass(frozen=True, slots=True)
class FloorLimits:
    max_width: float
    max_length: float


@dataclass(frozen=True, slots=True)
class RequestedRoom:
    room_type: RoomType
    id: str | None = None
    name: str | None = None
    requested_size: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.room_type, RoomType):
            raise TypeError("room_type must be a RoomType enum member")


@dataclass(frozen=True, slots=True)
class PreprocessingRequest:
    floor_limits: FloorLimits
    aspect_ratio: float | str
    rooms: tuple[RequestedRoom, ...]


@dataclass(frozen=True, slots=True)
class PreprocessingInput:
    request: PreprocessingRequest
    config: PreprocessingConfig

    @property
    def reference_data(self) -> PreprocessingConfig:
        return self.config

    @property
    def policy(self) -> PreprocessingConfig:
        return self.config


PreprocessingReferenceData = PreprocessingConfig


@dataclass(frozen=True, slots=True)
class NormalizationRecord:
    field: str
    original: str
    normalized: str


@dataclass(frozen=True, slots=True)
class RoomDecision:
    room_id: str
    room_type: RoomType
    action: str
    reason: str


@dataclass(frozen=True, slots=True)
class RelationDecision:
    source_room_type: RoomType
    action: str
    detail: str


@dataclass(frozen=True, slots=True)
class FloorSelection:
    requested_width: float
    requested_length: float
    normalized_max_width: int
    normalized_max_length: int
    selected_width: int
    selected_length: int
    requested_aspect_ratio: float
    selected_aspect_ratio: float
    aspect_residual_units: float
    minimum_required_area: float
    maximum_target_area: float
    unused_limit_area: float

    @property
    def aspect_ratio(self) -> float:
        """Deprecated alias for requested_aspect_ratio."""

        return self.requested_aspect_ratio


@dataclass(frozen=True, slots=True)
class PreprocessingReport:
    """Debug-only preprocessing decisions and normalized input information."""

    normalizations: tuple[NormalizationRecord, ...]
    room_decisions: tuple[RoomDecision, ...]
    relation_decisions: tuple[RelationDecision, ...]
    selected_room_size: str
    floor_selection: FloorSelection
    applied_defaults: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedGenerationInput:
    """Normal production result consumed by later generation features."""

    generation_spec: FloorPlanGenerationSpec


PreprocessingExecution: TypeAlias = FeatureExecution[
    PreparedGenerationInput,
    PreprocessingReport,
]
