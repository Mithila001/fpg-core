from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .exceptions import InvalidProfileError


@dataclass(frozen=True, slots=True)
class SolverConfig:
    """OR-Tools runtime settings for one solve."""

    max_time_seconds: float = 30.0
    num_search_workers: int = 0
    random_seed: int | None = None
    log_search_progress: bool = False
    relative_gap_limit: float | None = None
    cp_model_presolve: bool = True

    def __post_init__(self) -> None:
        if self.max_time_seconds <= 0:
            raise InvalidProfileError("max_time_seconds must be greater than zero")
        if self.num_search_workers < 0:
            raise InvalidProfileError("num_search_workers cannot be negative")
        if self.random_seed is not None and self.random_seed < 0:
            raise InvalidProfileError("random_seed cannot be negative")
        if self.relative_gap_limit is not None and self.relative_gap_limit < 0:
            raise InvalidProfileError("relative_gap_limit cannot be negative")


@dataclass(frozen=True, slots=True)
class PreparationConfig:
    """Conversion settings between project units and CP-SAT integer units."""

    coordinate_scale: int = 10

    def __post_init__(self) -> None:
        if self.coordinate_scale < 1:
            raise InvalidProfileError("coordinate_scale must be at least 1")


class SeedSource(str, Enum):
    NONE = "none"
    CANDIDATE_HINTS = "candidate_hints"
    EXISTING_FLOOR_PLAN = "existing_floor_plan"


@dataclass(frozen=True, slots=True)
class SeedPolicy:
    """Controls how a profile uses candidate or existing-layout geometry.

    Tolerances are expressed in the same units used by FloorPlanGenerationSpec.
    A ``None`` tolerance leaves that dimension unbounded and uses only AddHint.
    A zero tolerance fixes the seeded value.
    """

    source: SeedSource = SeedSource.NONE
    require_source: bool = False
    apply_hints: bool = True
    position_tolerance: float | None = None
    size_tolerance: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("position_tolerance", self.position_tolerance),
            ("size_tolerance", self.size_tolerance),
        ):
            if value is not None and value < 0:
                raise InvalidProfileError(f"{name} cannot be negative")
