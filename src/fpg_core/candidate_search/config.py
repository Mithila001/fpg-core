from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MIN_HALLWAY_HINT_COUNT = 1
DEFAULT_MAX_HALLWAY_HINT_COUNT = 5


def _positive_int(field_name: str, value: object, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}.")
    return value


@dataclass(frozen=True, slots=True)
class CandidateSearchConfig:
    """Reusable adaptive-grid and hallway search profile."""

    long_axis_node_count: int
    max_grid_node_count: int
    max_internal_sampling_attempts: int
    min_hallway_hint_count: int = DEFAULT_MIN_HALLWAY_HINT_COUNT
    max_hallway_hint_count: int = DEFAULT_MAX_HALLWAY_HINT_COUNT

    def __post_init__(self) -> None:
        _positive_int("long_axis_node_count", self.long_axis_node_count, minimum=2)
        _positive_int("max_grid_node_count", self.max_grid_node_count, minimum=4)
        _positive_int(
            "max_internal_sampling_attempts",
            self.max_internal_sampling_attempts,
        )
        _positive_int("min_hallway_hint_count", self.min_hallway_hint_count)
        _positive_int("max_hallway_hint_count", self.max_hallway_hint_count)
        if self.max_hallway_hint_count < self.min_hallway_hint_count:
            raise ValueError(
                "max_hallway_hint_count cannot be below min_hallway_hint_count."
            )
