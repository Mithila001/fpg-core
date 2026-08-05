from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    ConstraintStrength,
    FloorSpec,
    HallwayRoomCountRange,
    MatchPolicy,
    ResolvedCandidateGrid,
    RoomRelationSpec,
    RoomSpec,
    RoomType,
)
from .contracts import (
    NormalizationRecord,
    RelationDecision,
    RoomDecision,
)


@dataclass(frozen=True, slots=True)
class NormalizedRoom:
    id: str
    room_type: RoomType
    name: str
    requested_size: str | None
    request_index: int


@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    raw_max_width: float
    raw_max_length: float
    max_width: int
    max_length: int
    aspect_ratio: float
    rooms: tuple[NormalizedRoom, ...]
    normalizations: tuple[NormalizationRecord, ...]
    room_decisions: tuple[RoomDecision, ...]
    applied_defaults: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedRoomSizeReference:
    room_type: RoomType
    size: str
    min_width: float
    max_width: float
    min_area: float
    max_area: float


@dataclass(frozen=True, slots=True)
class PreparedRoomRelationReference:
    source_room_type: RoomType
    target_room_types: tuple[RoomType, ...]
    match_policy: MatchPolicy
    strength: ConstraintStrength
    required: bool


@dataclass(frozen=True, slots=True)
class PreparedReferenceData:
    room_sizes: tuple[PreparedRoomSizeReference, ...]
    room_relations: tuple[PreparedRoomRelationReference, ...]


@dataclass(frozen=True, slots=True)
class RuledRequest:
    raw_max_width: float
    raw_max_length: float
    max_width: int
    max_length: int
    aspect_ratio: float
    rooms: tuple[NormalizedRoom, ...]
    selected_room_size: str
    normalizations: tuple[NormalizationRecord, ...]
    room_decisions: tuple[RoomDecision, ...]
    applied_defaults: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreprocessingContext:
    request: RuledRequest
    reference_data: PreparedReferenceData
    rooms: tuple[RoomSpec, ...]
    floor: FloorSpec
    relations: tuple[RoomRelationSpec, ...]
    relation_decisions: tuple[RelationDecision, ...]
    minimum_required_area: float
    maximum_target_area: float
    candidate_grid: ResolvedCandidateGrid
    hallway_room_count_range: HallwayRoomCountRange
