from __future__ import annotations

from .exceptions import OpeningConfigurationError
from .features import ExteriorDoorFeature, InteriorDoorFeature, WindowFeature
from .features.base import OpeningFeature


class OpeningFeatureRegistry:
    def __init__(self) -> None:
        self._features: dict[str, OpeningFeature] = {}

    def register(self, feature: OpeningFeature) -> None:
        if feature.feature_id in self._features:
            raise OpeningConfigurationError(
                f"opening feature '{feature.feature_id}' is already registered"
            )
        self._features[feature.feature_id] = feature

    def resolve(self, feature_id: str) -> OpeningFeature:
        try:
            return self._features[feature_id]
        except KeyError as exc:
            raise OpeningConfigurationError(
                f"unknown opening feature '{feature_id}'"
            ) from exc


def create_default_registry() -> OpeningFeatureRegistry:
    registry = OpeningFeatureRegistry()
    registry.register(InteriorDoorFeature())
    registry.register(ExteriorDoorFeature())
    registry.register(WindowFeature())
    return registry
