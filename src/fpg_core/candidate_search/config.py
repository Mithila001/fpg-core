from __future__ import annotations

from dataclasses import dataclass

# Default Optuna search range for the number of hint points generated for each
# hallway target. Required non-hallway targets always receive exactly one point.
DEFAULT_MIN_HALLWAY_HINT_COUNT = 1
DEFAULT_MAX_HALLWAY_HINT_COUNT = 5


@dataclass(frozen=True, slots=True)
class CandidateSearchConfig:
    min_hallway_hint_count: int
    max_hallway_hint_count: int

    def __post_init__(self) -> None:
        if self.min_hallway_hint_count < 1:
            raise ValueError("min_hallway_hint_count must be positive")
        if self.max_hallway_hint_count < self.min_hallway_hint_count:
            raise ValueError(
                "max_hallway_hint_count cannot be below min_hallway_hint_count"
            )
