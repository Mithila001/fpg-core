from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import NewType

from ..domain import (
    CandidateMap,
    FinalCirculation,
    FloorPlanGenerationSpec,
    HallwayClassification,
    LandSide,
    RoomType,
)

EvaluatorKey = NewType("EvaluatorKey", str)

MIN_EVALUATOR_SCORE = 0.0
MAX_EVALUATOR_SCORE = 100.0


class EvaluatorCategory(str, Enum):
    """Determines how an evaluator participates in the scoring pipeline."""

    CRITICAL = "critical"
    QUALITY = "quality"


class EvaluationStatus(str, Enum):
    """Execution state of one evaluator."""

    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    ERROR = "error"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScoreFinding:
    """Structured explanation emitted by an evaluator or the manager."""

    code: str
    message: str
    severity: FindingSeverity = FindingSeverity.INFO
    subject_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ZoneSuitabilityPointDetails:
    """DEBUG-only score calculation for one zone-scored candidate point."""

    point_id: str
    source_room_id: str
    room_name: str
    room_type: RoomType
    hint_index: int
    x: float
    y: float
    preferred_cells: tuple[tuple[int, int], ...]
    distance_to_zone: float
    score: float
    inside_preferred_zone: bool


@dataclass(frozen=True, slots=True)
class ZoneSuitabilityRuleDetails:
    """DEBUG-only normalized preferred cells for one room type."""

    room_type: RoomType
    preferred_cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class ZoneSuitabilityDetails:
    """Zone-suitability scoring and R&D data collected in DEBUG mode."""

    floor_width: float
    floor_length: float
    zone_count_per_axis: int
    falloff_multiplier: float
    rules: tuple[ZoneSuitabilityRuleDetails, ...]
    points: tuple[ZoneSuitabilityPointDetails, ...]

    @property
    def grid_size(self) -> int:
        """Deprecated read-only alias for zone_count_per_axis."""

        return self.zone_count_per_axis


@dataclass(frozen=True, slots=True)
class SpatialDistributionPointDetails:
    """DEBUG-only candidate point used by spatial-distribution scoring."""

    point_id: str
    source_room_id: str
    room_name: str
    room_type: RoomType
    hint_index: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class SpatialDistributionDetails:
    """Spatial-distribution scoring and R&D data collected in DEBUG mode."""

    floor_width: float
    floor_length: float
    points: tuple[SpatialDistributionPointDetails, ...]
    sample_count_per_axis: int
    nearest_distances: tuple[tuple[float, ...], ...]
    ideal_point_distance: float
    theoretical_coverage_gap: float
    gap_zero_score_ratio: float

    @property
    def grid_size(self) -> int:
        """Deprecated read-only alias for sample_count_per_axis."""

        return self.sample_count_per_axis


@dataclass(frozen=True, slots=True)
class ClearanceCorridorBounds:
    """Axis-aligned no-hint-point corridor bounds in project units."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True, slots=True)
class ClearanceCorridorDebug:
    """Point-level exterior-clearance geometry collected in DEBUG mode."""

    rule_index: int
    point_id: str
    source_room_id: str
    room_name: str
    room_type: RoomType
    hint_x: float
    hint_y: float
    direction: LandSide
    bounds: ClearanceCorridorBounds
    blocker_point_ids: tuple[str, ...]
    blocker_room_ids: tuple[str, ...]
    is_clear: bool
    selected_for_score: bool


@dataclass(frozen=True, slots=True)
class ExteriorClearanceRoomEvaluation:
    """Room-level result after combining all hints for one source room."""

    source_room_id: str
    room_name: str
    room_type: RoomType
    point_ids: tuple[str, ...]
    clear_point_ids: tuple[str, ...]
    qualifies: bool
    selected_for_score: bool


@dataclass(frozen=True, slots=True)
class ExteriorClearanceRuleEvaluation:
    """Detailed score calculation for one configured clearance rule."""

    rule_index: int
    room_types: tuple[RoomType, ...]
    required_clear_room_count: int
    clearance_width: float
    direction: LandSide
    applicable: bool
    eligible_room_count: int
    clear_room_count: int
    score: float | None
    room_evaluations: tuple[ExteriorClearanceRoomEvaluation, ...]


@dataclass(frozen=True, slots=True)
class ExteriorClearanceDetails:
    """Exterior-clearance scoring and R&D data collected in DEBUG mode."""

    floor_width: float
    floor_length: float
    rule_evaluations: tuple[ExteriorClearanceRuleEvaluation, ...]
    corridors: tuple[ClearanceCorridorDebug, ...]


@dataclass(frozen=True, slots=True)
class EvaluatorResult:
    """Standard result returned by every concrete evaluator.

    ``score`` uses the common 0..100 scale when status is COMPLETED. ``metrics``
    and ``details`` are DEBUG-only and must be empty in PRODUCTION.
    """

    evaluator_key: EvaluatorKey
    status: EvaluationStatus
    score: float | None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    details: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionResult:
    """Manager-owned view of one evaluator's execution and contribution."""

    evaluator_key: EvaluatorKey
    category: EvaluatorCategory
    status: EvaluationStatus
    raw_score: float | None
    configured_weight: float
    normalized_weight: float
    contribution: float
    threshold: float | None = None
    passed_threshold: bool | None = None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    details: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Complete score-manager output for one candidate."""

    total_score: float
    passed_critical_checks: bool
    stopped_early: bool
    stop_reason: str | None
    evaluator_results: tuple[EvaluatorExecutionResult, ...]
    findings: tuple[ScoreFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateScoringInput:
    """One generation specification, candidate, and optional hallway tags."""

    specification: FloorPlanGenerationSpec
    candidate: CandidateMap
    hallway_classifications: tuple[HallwayClassification, ...] = ()
    final_circulation: FinalCirculation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.specification, FloorPlanGenerationSpec):
            raise TypeError("specification must be a FloorPlanGenerationSpec instance.")
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")
        if self.final_circulation is not None and not isinstance(
            self.final_circulation, FinalCirculation
        ):
            raise TypeError("final_circulation must be a FinalCirculation instance.")
        classifications = tuple(self.hallway_classifications)
        if any(not isinstance(item, HallwayClassification) for item in classifications):
            raise TypeError(
                "Every hallway classification must be a HallwayClassification."
            )
        identities = [(item.room_id, item.hint_index) for item in classifications]
        if len(identities) != len(set(identities)):
            raise ValueError("Hallway classifications must have unique identities.")
        object.__setattr__(self, "hallway_classifications", classifications)
