from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from ..domain import (
    CandidateMap,
    CandidateSearchSpace,
    FeatureExecution,
    FloorPlanGenerationSpec,
    HallwayRoomCountRange,
    ResolvedCandidateGrid,
    RoomRelationSpec,
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
class CandidateGridSelection:
    """DEBUG explanation of the grid prepared for downstream features."""

    floor_width: int
    floor_length: int
    grid: ResolvedCandidateGrid

    @property
    def removed_width(self) -> float:
        return self.floor_width - float(self.grid.width)

    @property
    def removed_length(self) -> float:
        return self.floor_length - float(self.grid.length)

    @property
    def left_trim(self) -> float:
        return float(self.grid.origin_x)

    @property
    def right_trim(self) -> float:
        return self.floor_width - float(self.grid.max_x)

    @property
    def front_trim(self) -> float:
        return float(self.grid.origin_y)

    @property
    def back_trim(self) -> float:
        return self.floor_length - float(self.grid.max_y)

    @property
    def edge_node_count(self) -> int:
        return self.grid.node_count - self.grid.interior_node_count

    @property
    def search_space(self) -> CandidateSearchSpace:
        """Compatibility view of the rectangle used to prepare ``grid``."""

        return CandidateSearchSpace(
            origin_x=self.grid.origin_x,
            origin_y=self.grid.origin_y,
            width=int(self.grid.width),
            length=int(self.grid.length),
            grid_spacing=int(self.grid.grid_spacing),
        )


# Backward-compatible name for callers that only need the selection report.
CandidateSearchSpaceSelection = CandidateGridSelection


@dataclass(frozen=True, slots=True)
class PreprocessingReport:
    """Debug-only preprocessing decisions and normalized input information."""

    normalizations: tuple[NormalizationRecord, ...]
    room_decisions: tuple[RoomDecision, ...]
    relation_decisions: tuple[RelationDecision, ...]
    selected_room_size: str
    floor_selection: FloorSelection
    candidate_search_space_selection: CandidateGridSelection
    hallway_room_count_range: HallwayRoomCountRange
    applied_defaults: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def candidate_grid_selection(self) -> CandidateGridSelection:
        return self.candidate_search_space_selection


@dataclass(frozen=True, slots=True)
class PreparedGenerationInput:
    """Production result shared with Candidate Search and later generation stages.

    ``generation_spec`` contains every possible hallway room up to the configured
    maximum. Candidate Search activates a subset of those hallway IDs. Call
    ``generation_spec_for_candidate`` before passing the specification to a solver
    so unused hallway rooms are removed.
    """

    generation_spec: FloorPlanGenerationSpec
    candidate_grid: ResolvedCandidateGrid
    hallway_room_count_range: HallwayRoomCountRange

    @property
    def candidate_search_space(self) -> CandidateSearchSpace:
        """Compatibility view derived from the prepared candidate grid."""

        return CandidateSearchSpace(
            origin_x=self.candidate_grid.origin_x,
            origin_y=self.candidate_grid.origin_y,
            width=int(self.candidate_grid.width),
            length=int(self.candidate_grid.length),
            grid_spacing=int(self.candidate_grid.grid_spacing),
        )

    def generation_spec_for_candidate(
        self,
        candidate: CandidateMap,
    ) -> FloorPlanGenerationSpec:
        """Return a specification containing exactly the candidate's hallway rooms."""

        if not isinstance(candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")
        if candidate.grid != self.candidate_grid:
            raise ValueError(
                "Candidate grid does not match the grid prepared by preprocessing."
            )

        prepared_rooms = {str(room.id): room for room in self.generation_spec.rooms}
        candidate_room_ids = [str(point.room_id) for point in candidate.points]
        if len(candidate_room_ids) != len(set(candidate_room_ids)):
            raise ValueError(
                "Candidate must contain at most one hint point for each room ID."
            )

        unknown_ids = sorted(set(candidate_room_ids).difference(prepared_rooms))
        if unknown_ids:
            raise ValueError(
                "Candidate contains room IDs not prepared by preprocessing: "
                + ", ".join(unknown_ids)
            )

        for point in candidate.points:
            prepared_room = prepared_rooms[str(point.room_id)]
            if (
                point.room_type is not None
                and point.room_type is not prepared_room.room_type
            ):
                raise ValueError(
                    f"Candidate room type for '{point.room_id}' does not match "
                    "the preprocessing specification."
                )

        required_non_hallway_ids = {
            str(room.id)
            for room in self.generation_spec.rooms
            if room.room_type is not RoomType.HALLWAY
        }
        missing_non_hallway_ids = sorted(
            required_non_hallway_ids.difference(candidate_room_ids)
        )
        if missing_non_hallway_ids:
            raise ValueError(
                "Candidate is missing non-hallway room IDs: "
                + ", ".join(missing_non_hallway_ids)
            )

        selected_hallway_ids = {
            room_id
            for room_id in candidate_room_ids
            if prepared_rooms[room_id].room_type is RoomType.HALLWAY
        }
        selected_hallway_count = len(selected_hallway_ids)
        if not (
            self.hallway_room_count_range.minimum
            <= selected_hallway_count
            <= self.hallway_room_count_range.maximum
        ):
            raise ValueError(
                "Candidate hallway room count is outside the prepared range."
            )

        active_ids = required_non_hallway_ids | selected_hallway_ids
        rooms = tuple(
            room
            for room in self.generation_spec.rooms
            if str(room.id) in active_ids
        )
        relations = _filter_relations(
            self.generation_spec.room_relations,
            active_ids=active_ids,
        )
        return FloorPlanGenerationSpec(
            floor=self.generation_spec.floor,
            rooms=rooms,
            room_relations=relations,
        )


def _filter_relations(
    relations: tuple[RoomRelationSpec, ...],
    *,
    active_ids: set[str],
) -> tuple[RoomRelationSpec, ...]:
    filtered: list[RoomRelationSpec] = []
    for relation in relations:
        if str(relation.source_room_id) not in active_ids:
            continue
        targets = tuple(
            target
            for target in relation.target_room_ids
            if str(target) in active_ids
        )
        if not targets:
            continue
        filtered.append(
            RoomRelationSpec(
                source_room_id=relation.source_room_id,
                target_room_ids=targets,
                match_policy=relation.match_policy,
                strength=relation.strength,
            )
        )
    return tuple(filtered)


PreprocessingExecution: TypeAlias = FeatureExecution[
    PreparedGenerationInput,
    PreprocessingReport,
]
