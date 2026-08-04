from __future__ import annotations

from dataclasses import dataclass


def _positive_int(field_name: str, value: object, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}.")
    return value


@dataclass(frozen=True, slots=True)
class CandidateSearchConfig:
    """Reusable Candidate Search safety limits."""

    max_grid_node_count: int

    def __post_init__(self) -> None:
        _positive_int("max_grid_node_count", self.max_grid_node_count, minimum=9)
