"""Door and window generation public API.

Exports are loaded lazily so configuration-only imports do not initialize OR-Tools.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import generate_openings
    from .config import (
        DimensionConfig,
        FeaturePolicy,
        FloorPlanOpeningsConfig,
        GeometryConfig,
        ObjectiveConfig,
        SolverConfig,
    )
    from .contracts import (
        OpeningDiagnostics,
        OpeningGenerationExecution,
        OpeningGenerationRequest,
        OpeningGenerationResult,
        OpeningGenerationStatus,
        OpeningIssue,
    )
    from .exceptions import OpeningConfigurationError, OpeningGenerationError
    from .profiles import (
        DEFAULT_OPENING_CONFIG,
        DEFAULT_OPENING_PROFILE,
        OpeningGenerationProfile,
    )
    from .registry import OpeningFeatureRegistry, create_default_registry

_EXPORTS: dict[str, tuple[str, str]] = {
    "generate_openings": (".api", "generate_openings"),
    "DimensionConfig": (".config", "DimensionConfig"),
    "FeaturePolicy": (".config", "FeaturePolicy"),
    "FloorPlanOpeningsConfig": (".config", "FloorPlanOpeningsConfig"),
    "GeometryConfig": (".config", "GeometryConfig"),
    "ObjectiveConfig": (".config", "ObjectiveConfig"),
    "SolverConfig": (".config", "SolverConfig"),
    "OpeningDiagnostics": (".contracts", "OpeningDiagnostics"),
    "OpeningGenerationExecution": (".contracts", "OpeningGenerationExecution"),
    "OpeningGenerationRequest": (".contracts", "OpeningGenerationRequest"),
    "OpeningGenerationResult": (".contracts", "OpeningGenerationResult"),
    "OpeningGenerationStatus": (".contracts", "OpeningGenerationStatus"),
    "OpeningIssue": (".contracts", "OpeningIssue"),
    "DEFAULT_OPENING_CONFIG": (".profiles", "DEFAULT_OPENING_CONFIG"),
    "DEFAULT_OPENING_PROFILE": (".profiles", "DEFAULT_OPENING_PROFILE"),
    "OpeningGenerationProfile": (".profiles", "OpeningGenerationProfile"),
    "OpeningFeatureRegistry": (".registry", "OpeningFeatureRegistry"),
    "create_default_registry": (".registry", "create_default_registry"),
    "OpeningConfigurationError": (".exceptions", "OpeningConfigurationError"),
    "OpeningGenerationError": (".exceptions", "OpeningGenerationError"),
}

__all__ = [
    "generate_openings",
    "DimensionConfig",
    "FeaturePolicy",
    "FloorPlanOpeningsConfig",
    "GeometryConfig",
    "ObjectiveConfig",
    "SolverConfig",
    "OpeningDiagnostics",
    "OpeningGenerationExecution",
    "OpeningGenerationRequest",
    "OpeningGenerationResult",
    "OpeningGenerationStatus",
    "OpeningIssue",
    "DEFAULT_OPENING_CONFIG",
    "DEFAULT_OPENING_PROFILE",
    "OpeningGenerationProfile",
    "OpeningFeatureRegistry",
    "create_default_registry",
    "OpeningConfigurationError",
    "OpeningGenerationError",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc

    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
