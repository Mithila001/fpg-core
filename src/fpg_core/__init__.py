"""Core algorithms and domain contracts for floor-plan generation.

Feature operations are exposed through each feature's ``api.py``. The root package
keeps imports lazy and limits itself to package metadata and selected package-wide
configuration conveniences.
"""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import (
        BuildableSpaceConfig,
        CandidateSearchConfig,
        FpgCoreConfig,
        FpgCoreConfigError,
        PreprocessingConfig,
        validate_fpg_core_config,
    )
    from .floor_plan_preprocessing.config import canonical_aspect_ratio

try:
    __version__ = version("fpg-core")
except PackageNotFoundError:  # Source checkout without an installed distribution.
    __version__ = "0.1.0"

_EXPORTS: dict[str, tuple[str, str]] = {
    "BuildableSpaceConfig": (".config", "BuildableSpaceConfig"),
    "CandidateSearchConfig": (".config", "CandidateSearchConfig"),
    "FpgCoreConfig": (".config", "FpgCoreConfig"),
    "FpgCoreConfigError": (".config", "FpgCoreConfigError"),
    "PreprocessingConfig": (".config", "PreprocessingConfig"),
    "validate_fpg_core_config": (".config", "validate_fpg_core_config"),
    "canonical_aspect_ratio": (
        ".floor_plan_preprocessing.config",
        "canonical_aspect_ratio",
    ),
}

__all__ = [
    "__version__",
    "BuildableSpaceConfig",
    "CandidateSearchConfig",
    "FpgCoreConfig",
    "FpgCoreConfigError",
    "PreprocessingConfig",
    "validate_fpg_core_config",
    "canonical_aspect_ratio",
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
