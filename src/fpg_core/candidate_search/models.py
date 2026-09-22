from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from ..domain import (
    CandidateMap,
    CandidatePoint,
    HallwayRoomCountRange,
    ResolvedCandidateGrid,
    RoomId,
    RoomType,
)
from .config import CandidateSearchConfig


@dataclass(frozen=True, slots=True)
class CandidateSearchTarget:
    """Identifies one concrete room that may receive one candidate point."""

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


CandidateEvaluator: TypeAlias = Callable[[CandidateMap], float]


@dataclass(frozen=True, slots=True)
class CandidateSearchInput:
    """Processing input and execution dependency for one Candidate Search.

    ``grid`` and ``hallway_room_count_range`` describe the prepared floor-plan
    operation. ``config`` controls how Candidate Search performs that operation.
    All possible hallway room targets must be supplied. Each trial selects one
    global hallway count and activates that many hallway targets. Every active
    target receives exactly one point.
    """

    targets: tuple[CandidateSearchTarget, ...]
    grid: ResolvedCandidateGrid
    hallway_room_count_range: HallwayRoomCountRange
    evaluator: CandidateEvaluator
    config: CandidateSearchConfig

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
        if not isinstance(self.grid, ResolvedCandidateGrid):
            raise TypeError("grid must be a ResolvedCandidateGrid instance.")
        if not isinstance(self.hallway_room_count_range, HallwayRoomCountRange):
            raise TypeError(
                "hallway_room_count_range must be a HallwayRoomCountRange instance."
            )
        if not callable(self.evaluator):
            raise TypeError("evaluator must be callable.")
        if not isinstance(self.config, CandidateSearchConfig):
            raise TypeError("config must be a CandidateSearchConfig instance.")

        if self.grid.node_count > self.config.max_grid_node_count:
            raise ValueError(
                "Prepared candidate grid contains "
                f"{self.grid.node_count} nodes, exceeding "
                f"max_grid_node_count={self.config.max_grid_node_count}."
            )
        if self.grid.interior_node_count < 1:
            raise ValueError(
                "Prepared candidate grid must contain at least one non-edge "
                "hint-point node."
            )

        hallway_target_count = sum(target.is_hallway for target in normalized_targets)
        expected_hallway_target_count = self.hallway_room_count_range.maximum
        if hallway_target_count != expected_hallway_target_count:
            raise ValueError(
                "The number of hallway targets must equal the prepared maximum "
                "hallway room count: "
                f"expected {expected_hallway_target_count}, received "
                f"{hallway_target_count}."
            )

        non_hallway_count = len(normalized_targets) - hallway_target_count
        maximum_point_count = non_hallway_count + expected_hallway_target_count
        if maximum_point_count > self.grid.interior_node_count:
            raise ValueError(
                "Candidate search may request up to "
                f"{maximum_point_count} room points but the prepared grid contains "
                f"only {self.grid.interior_node_count} non-edge nodes."
            )
        object.__setattr__(self, "targets", normalized_targets)

    @property
    def hallway_targets(self) -> tuple[CandidateSearchTarget, ...]:
        return tuple(target for target in self.targets if target.is_hallway)

    @property
    def non_hallway_targets(self) -> tuple[CandidateSearchTarget, ...]:
        return tuple(target for target in self.targets if not target.is_hallway)


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

    @property
    def hallway_room_count(self) -> int:
        return sum(point.room_type is RoomType.HALLWAY for point in self.points)


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

    @property
    def hallway_room_count(self) -> int:
        return sum(point.room_type is RoomType.HALLWAY for point in self.points)


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

    @property
    def hallway_room_count(self) -> int:
        return sum(point.room_type is RoomType.HALLWAY for point in self.points)


@dataclass(frozen=True, slots=True)
class CandidateSearchDetails:
    """DEBUG-only grid and Optuna trial information."""

    grid: ResolvedCandidateGrid
    optuna_trial_count: int
    completed_trial_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.grid, ResolvedCandidateGrid):
            raise TypeError("grid must be a ResolvedCandidateGrid instance.")
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
