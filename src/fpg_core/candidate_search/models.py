from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from ..domain import (
    CandidateMap,
    CandidatePoint,
    FloorSpec,
    ResolvedCandidateGrid,
    RoomId,
    RoomType,
)
from .config import (
    DEFAULT_MAX_HALLWAY_HINT_COUNT,
    DEFAULT_MIN_HALLWAY_HINT_COUNT,
)
from .grid import build_candidate_grid


@dataclass(frozen=True, slots=True)
class CandidateSearchTarget:
    """Identifies one room that needs one or more candidate coordinates."""

    room_id: RoomId
    room_type: RoomType | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.room_id, str):
            raise TypeError("Candidate target room_id must be a string-based RoomId.")
        cleaned_room_id = self.room_id.strip()
        if not cleaned_room_id:
            raise ValueError("Candidate target room_id cannot be empty.")
        if self.room_type is not None and not isinstance(self.room_type, RoomType):
            raise TypeError("Candidate target room_type must be a RoomType or None.")
        object.__setattr__(self, "room_id", RoomId(cleaned_room_id))

    @property
    def is_hallway(self) -> bool:
        return self.room_type is RoomType.HALLWAY


@dataclass(frozen=True, slots=True)
class CandidateSearchSettings:
    """Configuration controlling adaptive-grid candidate exploration."""

    floor: FloorSpec
    long_axis_node_count: int
    max_grid_node_count: int
    max_internal_sampling_attempts: int
    trial_count: int
    random_seed: int | None = None
    min_hallway_hint_count: int = DEFAULT_MIN_HALLWAY_HINT_COUNT
    max_hallway_hint_count: int = DEFAULT_MAX_HALLWAY_HINT_COUNT

    def __post_init__(self) -> None:
        if not isinstance(self.floor, FloorSpec):
            raise TypeError("floor must be a FloorSpec instance.")
        _validate_positive_integer(
            "long_axis_node_count", self.long_axis_node_count, minimum=2
        )
        _validate_positive_integer(
            "max_grid_node_count", self.max_grid_node_count, minimum=4
        )
        _validate_positive_integer(
            "max_internal_sampling_attempts",
            self.max_internal_sampling_attempts,
        )
        _validate_positive_integer("trial_count", self.trial_count)
        _validate_positive_integer(
            "min_hallway_hint_count",
            self.min_hallway_hint_count,
        )
        _validate_positive_integer(
            "max_hallway_hint_count",
            self.max_hallway_hint_count,
        )
        if self.min_hallway_hint_count > self.max_hallway_hint_count:
            raise ValueError(
                "min_hallway_hint_count cannot be greater than "
                "max_hallway_hint_count."
            )
        if self.random_seed is not None and (
            isinstance(self.random_seed, bool)
            or not isinstance(self.random_seed, int)
        ):
            raise TypeError("random_seed must be an integer or None.")

        # Fail during settings construction rather than after Optuna starts.
        build_candidate_grid(
            self.floor,
            long_axis_node_count=self.long_axis_node_count,
            max_grid_node_count=self.max_grid_node_count,
        )


CandidateEvaluator: TypeAlias = Callable[[CandidateMap], float]


@dataclass(frozen=True, slots=True)
class CandidateSearchInput:
    """Complete input contract for one candidate-search operation or session."""

    targets: tuple[CandidateSearchTarget, ...]
    settings: CandidateSearchSettings
    evaluator: CandidateEvaluator

    def __post_init__(self) -> None:
        normalized_targets = tuple(self.targets)
        if not normalized_targets:
            raise ValueError("At least one candidate search target is required.")
        if any(
            not isinstance(target, CandidateSearchTarget)
            for target in normalized_targets
        ):
            raise TypeError("Every target must be a CandidateSearchTarget instance.")

        room_ids = [target.room_id for target in normalized_targets]
        duplicate_room_ids = _find_duplicate_room_ids(room_ids)
        if duplicate_room_ids:
            formatted_ids = ", ".join(sorted(duplicate_room_ids))
            raise ValueError(
                f"Candidate search target room IDs must be unique: {formatted_ids}"
            )
        if not isinstance(self.settings, CandidateSearchSettings):
            raise TypeError("settings must be a CandidateSearchSettings instance.")
        if not callable(self.evaluator):
            raise TypeError("evaluator must be callable.")

        grid = build_candidate_grid(
            self.settings.floor,
            long_axis_node_count=self.settings.long_axis_node_count,
            max_grid_node_count=self.settings.max_grid_node_count,
        )
        maximum_point_count = sum(
            self.settings.max_hallway_hint_count if target.is_hallway else 1
            for target in normalized_targets
        )
        if maximum_point_count > grid.node_count:
            raise ValueError(
                "Candidate search may request up to "
                f"{maximum_point_count} points but the resolved grid contains only "
                f"{grid.node_count} nodes."
            )
        object.__setattr__(self, "targets", normalized_targets)


@dataclass(frozen=True, slots=True)
class CandidateSuggestion:
    """One valid, non-overlapping candidate produced by an Optuna trial."""

    trial_number: int
    candidate: CandidateMap

    def __post_init__(self) -> None:
        _validate_non_negative_integer("trial_number", self.trial_number)
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")

    @property
    def points(self) -> tuple[CandidatePoint, ...]:
        return self.candidate.points

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self.candidate.grid


@dataclass(frozen=True, slots=True)
class CandidateTrialResult:
    """Candidate and score produced by one completed search trial."""

    trial_number: int
    candidate: CandidateMap
    score: float
    completed_trials: int

    def __post_init__(self) -> None:
        _validate_non_negative_integer("trial_number", self.trial_number)
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")
        object.__setattr__(self, "score", _validated_finite_number("score", self.score))
        _validate_positive_integer("completed_trials", self.completed_trials)

    @property
    def points(self) -> tuple[CandidatePoint, ...]:
        return self.candidate.points

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self.candidate.grid


@dataclass(frozen=True, slots=True)
class CandidateSearchResult:
    """Best candidate arrangement discovered by a completed search."""

    candidate: CandidateMap
    score: float
    completed_trials: int

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")
        object.__setattr__(self, "score", _validated_finite_number("score", self.score))
        _validate_positive_integer("completed_trials", self.completed_trials)

    @property
    def points(self) -> tuple[CandidatePoint, ...]:
        return self.candidate.points

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self.candidate.grid


@dataclass(frozen=True, slots=True)
class CandidateSearchDetails:
    """DEBUG-only adaptive-grid and internal trial-rejection information."""

    grid: ResolvedCandidateGrid
    overlap_rejection_count: int
    optuna_trial_count: int
    completed_trial_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.grid, ResolvedCandidateGrid):
            raise TypeError("grid must be a ResolvedCandidateGrid instance.")
        _validate_non_negative_integer(
            "overlap_rejection_count", self.overlap_rejection_count
        )
        _validate_non_negative_integer("optuna_trial_count", self.optuna_trial_count)
        _validate_non_negative_integer(
            "completed_trial_count", self.completed_trial_count
        )


def _validated_finite_number(field_name: str, value: object) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not boolean.")
    try:
        numeric_value = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite.")
    return numeric_value


def _validate_positive_integer(
    field_name: str,
    value: object,
    *,
    minimum: int = 1,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}.")


def _validate_non_negative_integer(field_name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _find_duplicate_room_ids(room_ids: list[RoomId]) -> set[RoomId]:
    seen: set[RoomId] = set()
    duplicates: set[RoomId] = set()
    for room_id in room_ids:
        if room_id in seen:
            duplicates.add(room_id)
        else:
            seen.add(room_id)
    return duplicates
