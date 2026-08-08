from __future__ import annotations

from dataclasses import dataclass

from ..domain import BuildableLand, NormalizedLand, Point, Polygon
from .config import UsableLandConfig


@dataclass(frozen=True, slots=True)
class UsableLandInput:
    """Land geometry being processed plus reusable usable-land configuration."""

    buildable_land: BuildableLand
    land: NormalizedLand
    config: UsableLandConfig

    def __post_init__(self) -> None:
        if not isinstance(self.buildable_land, BuildableLand):
            raise TypeError("buildable_land must be a BuildableLand instance.")
        if not isinstance(self.land, NormalizedLand):
            raise TypeError("land must be a NormalizedLand instance.")
        if not isinstance(self.config, UsableLandConfig):
            raise TypeError("config must be a UsableLandConfig instance.")


@dataclass(frozen=True, slots=True)
class UsableLandDetails:
    """DEBUG-only search and road-aligned geometry information."""

    evaluated_rectangle_pairs: int
    local_buildable_boundary: Polygon
    selected_local_boundary: Polygon
    transform_origin: Point
    transform_x_axis: tuple[float, float]
    transform_y_axis: tuple[float, float]

    def __post_init__(self) -> None:
        if (
            isinstance(self.evaluated_rectangle_pairs, bool)
            or not isinstance(self.evaluated_rectangle_pairs, int)
            or self.evaluated_rectangle_pairs < 0
        ):
            raise ValueError("evaluated_rectangle_pairs must be a non-negative integer.")


__all__ = ["UsableLandDetails", "UsableLandInput"]
