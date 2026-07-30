from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from ..types import FloorPlan, FloorPlanGenerationSpec, Polygon, RoomId


class PipelineStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ProcessorStatus(str, Enum):
    CHANGED = "changed"
    NO_CHANGE = "no_change"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class NumericPolicy:
    tolerance: float = 1e-6
    grid_size: float = 1.0


@dataclass(frozen=True)
class ProcessorOutcome:
    status: ProcessorStatus
    message: str
    affected_room_ids: tuple[RoomId, ...] = ()
    identity_redirects: Mapping[RoomId, RoomId] = field(default_factory=dict)
    metrics: Mapping[str, int | float | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessingFailure:
    code: str
    message: str
    processor_id: str | None = None


@dataclass(frozen=True)
class ProcessorExecution:
    processor_id: str
    status: ProcessorStatus
    duration_ms: float
    rolled_back: bool = False
    outcome: ProcessorOutcome | None = None
    failure: ProcessingFailure | None = None


@dataclass(frozen=True)
class ProcessorUse:
    processor_id: str
    config: object
    required: bool = False
    validate_after: bool = False


@dataclass(frozen=True)
class PostProcessingProfile:
    name: str
    processors: tuple[ProcessorUse, ...]
    numeric: NumericPolicy = field(default_factory=NumericPolicy)
    reject_existing_openings: bool = True


@dataclass(frozen=True)
class PostProcessingRequest:
    floor_plan: FloorPlan
    profile: PostProcessingProfile
    specification: FloorPlanGenerationSpec | None = None


@dataclass(frozen=True)
class PostProcessingContext:
    specification: FloorPlanGenerationSpec | None
    floor_boundary: Polygon
    numeric: NumericPolicy
    profile_name: str


@dataclass(frozen=True)
class PostProcessingResult:
    status: PipelineStatus
    floor_plan: FloorPlan
    executions: tuple[ProcessorExecution, ...]
    failure: ProcessingFailure | None = None


class FloorPlanProcessor(ABC):
    processor_id: ClassVar[str]
    description: ClassVar[str]
    config_type: ClassVar[type]
    prerequisites: ClassVar[tuple[str, ...]] = ()

    def is_applicable(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> tuple[bool, str]:
        return True, "applicable"

    @abstractmethod
    def process(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> ProcessorOutcome:
        raise NotImplementedError
