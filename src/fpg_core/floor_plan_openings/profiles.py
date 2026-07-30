from __future__ import annotations

from dataclasses import dataclass, field

from .config import (
    DimensionConfig,
    FeaturePolicy,
    GeometryConfig,
    ObjectiveConfig,
    SolverConfig,
)
from .exceptions import OpeningConfigurationError


@dataclass(frozen=True, slots=True)
class OpeningGenerationProfile:
    name: str
    enabled_features: tuple[str, ...] = (
        "interior_doors",
        "exterior_doors",
        "windows",
    )
    enabled_constraints: tuple[str, ...] = (
        "shared_placement",
        "room_door_limits",
    )
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    dimensions: DimensionConfig = field(default_factory=DimensionConfig)
    policy: FeaturePolicy = field(default_factory=FeaturePolicy)
    objective: ObjectiveConfig = field(default_factory=ObjectiveConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise OpeningConfigurationError("profile name cannot be empty")
        if len(self.enabled_features) != len(set(self.enabled_features)):
            raise OpeningConfigurationError("enabled feature IDs must be unique")
        if len(self.enabled_constraints) != len(set(self.enabled_constraints)):
            raise OpeningConfigurationError("enabled constraint IDs must be unique")
        if "shared_placement" not in self.enabled_constraints:
            raise OpeningConfigurationError(
                "shared_placement is a structural opening-model invariant"
            )


DEFAULT_OPENING_PROFILE = OpeningGenerationProfile(name="default_openings")
