from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    BuildableLand,
    BuildableSpaceRequestData,
    EdgeClassification,
    NormalizedLand,
)
from .config import BuildableLandConfig


@dataclass(frozen=True, slots=True)
class BuildableLandInput:
    """Request-specific land data plus reusable buildable-land configuration."""

    request: BuildableSpaceRequestData
    config: BuildableLandConfig

    def __post_init__(self) -> None:
        if not isinstance(self.request, BuildableSpaceRequestData):
            raise TypeError("request must be a BuildableSpaceRequestData instance.")
        if not isinstance(self.config, BuildableLandConfig):
            raise TypeError("config must be a BuildableLandConfig instance.")


@dataclass(frozen=True, slots=True)
class BuildableLandResult:
    """Production output required by later land-processing stages."""

    buildable_land: BuildableLand
    normalized_land: NormalizedLand

    def __post_init__(self) -> None:
        if not isinstance(self.buildable_land, BuildableLand):
            raise TypeError("buildable_land must be a BuildableLand instance.")
        if not isinstance(self.normalized_land, NormalizedLand):
            raise TypeError("normalized_land must be a NormalizedLand instance.")


@dataclass(frozen=True, slots=True)
class BuildableLandDetails:
    """DEBUG-only land-side classification information."""

    edge_classifications: tuple[EdgeClassification, ...]

    def __post_init__(self) -> None:
        classifications = tuple(self.edge_classifications)
        if any(not isinstance(item, EdgeClassification) for item in classifications):
            raise TypeError(
                "Every edge classification must be an EdgeClassification instance."
            )
        object.__setattr__(self, "edge_classifications", classifications)


__all__ = [
    "BuildableLandDetails",
    "BuildableLandInput",
    "BuildableLandResult",
]
