from __future__ import annotations

from dataclasses import dataclass

from ..domain import UsableLandConstraints


@dataclass(frozen=True, slots=True)
class UsableLandConfig:
    """Reusable search limits and dimensional requirements."""

    minimum_width: int
    minimum_length: int
    search_resolution: int
    maximum_sweep_lines: int

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_width", self.minimum_width),
            ("minimum_length", self.minimum_length),
            ("search_resolution", self.search_resolution),
            ("maximum_sweep_lines", self.maximum_sweep_lines),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

    @classmethod
    def from_constraints(cls, constraints: UsableLandConstraints) -> UsableLandConfig:
        """Create feature configuration from the legacy shared constraints type."""

        if not isinstance(constraints, UsableLandConstraints):
            raise TypeError("constraints must be a UsableLandConstraints instance.")
        return cls(
            minimum_width=constraints.minimum_width,
            minimum_length=constraints.minimum_length,
            search_resolution=constraints.search_resolution,
            maximum_sweep_lines=constraints.maximum_sweep_lines,
        )


__all__ = ["UsableLandConfig"]
