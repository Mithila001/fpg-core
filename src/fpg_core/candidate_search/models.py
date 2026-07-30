from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from ..types import RoomId, RoomType
from .config import (
    DEFAULT_MAX_HALLWAY_HINT_COUNT,
    DEFAULT_MIN_HALLWAY_HINT_COUNT,
)


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
        """Whether Optuna may vary this target's hint-point count."""

        return self.room_type is RoomType.HALLWAY


@dataclass(frozen=True, slots=True)
class CandidatePoint:
    """A generated hint coordinate associated with one room."""

    room_id: RoomId
    x: float
    y: float
    room_type: RoomType | None = None
    hint_index: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.room_id, str):
            raise TypeError("Candidate point room_id must be a string-based RoomId.")

        cleaned_room_id = self.room_id.strip()
        if not cleaned_room_id:
            raise ValueError("Candidate point room_id cannot be empty.")

        if self.room_type is not None and not isinstance(self.room_type, RoomType):
            raise TypeError("Candidate point room_type must be a RoomType or None.")

        if isinstance(self.hint_index, bool) or not isinstance(self.hint_index, int):
            raise TypeError("Candidate point hint_index must be an integer.")
        if self.hint_index <= 0:
            raise ValueError("Candidate point hint_index must be greater than zero.")
        if self.room_type is not RoomType.HALLWAY and self.hint_index != 1:
            raise ValueError(
                "Only hallway candidate points may use a hint_index greater than one."
            )

        object.__setattr__(self, "room_id", RoomId(cleaned_room_id))
        object.__setattr__(self, "x", _validated_finite_number("x", self.x))
        object.__setattr__(self, "y", _validated_finite_number("y", self.y))


@dataclass(frozen=True, slots=True)
class CandidateSearchSettings:
    """Configuration controlling the candidate coordinate search space."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float
    grid_resolution: float
    trial_count: int
    random_seed: int | None = None
    min_hallway_hint_count: int = DEFAULT_MIN_HALLWAY_HINT_COUNT
    max_hallway_hint_count: int = DEFAULT_MAX_HALLWAY_HINT_COUNT

    def __post_init__(self) -> None:
        object.__setattr__(self, "min_x", _validated_finite_number("min_x", self.min_x))
        object.__setattr__(self, "max_x", _validated_finite_number("max_x", self.max_x))
        object.__setattr__(self, "min_y", _validated_finite_number("min_y", self.min_y))
        object.__setattr__(self, "max_y", _validated_finite_number("max_y", self.max_y))
        object.__setattr__(
            self,
            "grid_resolution",
            _validated_finite_number("grid_resolution", self.grid_resolution),
        )

        if self.min_x > self.max_x:
            raise ValueError("min_x cannot be greater than max_x.")
        if self.min_y > self.max_y:
            raise ValueError("min_y cannot be greater than max_y.")
        if self.grid_resolution <= 0:
            raise ValueError("grid_resolution must be greater than zero.")

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

        if self.random_seed is not None:
            if isinstance(self.random_seed, bool) or not isinstance(
                self.random_seed,
                int,
            ):
                raise TypeError("random_seed must be an integer or None.")


CandidateEvaluator: TypeAlias = Callable[[tuple[CandidatePoint, ...]], float]


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

        for target in normalized_targets:
            if not isinstance(target, CandidateSearchTarget):
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

        object.__setattr__(self, "targets", normalized_targets)


@dataclass(frozen=True, slots=True)
class CandidateSuggestion:
    """Unscored candidate points produced by one Optuna trial."""

    trial_number: int
    points: tuple[CandidatePoint, ...]

    def __post_init__(self) -> None:
        _validate_non_negative_integer("trial_number", self.trial_number)
        object.__setattr__(self, "points", _validated_candidate_points(self.points))


@dataclass(frozen=True, slots=True)
class CandidateTrialResult:
    """The points and score produced by one completed candidate-search trial."""

    trial_number: int
    points: tuple[CandidatePoint, ...]
    score: float
    completed_trials: int

    def __post_init__(self) -> None:
        _validate_non_negative_integer("trial_number", self.trial_number)

        normalized_points = _validated_candidate_points(self.points)
        numeric_score = _validated_finite_number("score", self.score)

        _validate_positive_integer("completed_trials", self.completed_trials)

        object.__setattr__(self, "points", normalized_points)
        object.__setattr__(self, "score", numeric_score)


@dataclass(frozen=True, slots=True)
class CandidateSearchResult:
    """Best candidate arrangement discovered by a completed search."""

    points: tuple[CandidatePoint, ...]
    score: float
    completed_trials: int

    def __post_init__(self) -> None:
        normalized_points = _validated_candidate_points(self.points)
        numeric_score = _validated_finite_number("score", self.score)

        _validate_positive_integer("completed_trials", self.completed_trials)

        object.__setattr__(self, "points", normalized_points)
        object.__setattr__(self, "score", numeric_score)


def _validated_candidate_points(
    points: tuple[CandidatePoint, ...],
) -> tuple[CandidatePoint, ...]:
    normalized_points = tuple(points)
    if not normalized_points:
        raise ValueError("Candidate result must contain at least one point.")

    for point in normalized_points:
        if not isinstance(point, CandidatePoint):
            raise TypeError("Every result point must be a CandidatePoint instance.")

    points_by_room_id: dict[RoomId, list[CandidatePoint]] = defaultdict(list)
    for point in normalized_points:
        points_by_room_id[point.room_id].append(point)

    for room_id, room_points in points_by_room_id.items():
        if len(room_points) == 1:
            continue

        if any(point.room_type is not RoomType.HALLWAY for point in room_points):
            raise ValueError(
                "Only hallway rooms may contain multiple candidate points: "
                f"{room_id}"
            )

        hint_indices = [point.hint_index for point in room_points]
        if len(set(hint_indices)) != len(hint_indices):
            raise ValueError(
                f"Hallway candidate hint indexes must be unique for room '{room_id}'."
            )

    return normalized_points


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


def _validate_positive_integer(field_name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")


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
