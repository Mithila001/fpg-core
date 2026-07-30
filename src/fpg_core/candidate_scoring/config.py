from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .types import EvaluatorCategory, EvaluatorKey


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class EvaluatorRule:
    """Manager-owned configuration for one registered evaluator."""

    key: EvaluatorKey
    category: EvaluatorCategory
    enabled: bool = True
    order: int = 0
    weight: float = 1.0
    minimum_score: float | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Configuration for the complete evaluator pipeline."""

    evaluator_rules: tuple[EvaluatorRule, ...]
    fail_fast_on_critical_failure: bool = True
    not_applicable_quality_contributes: bool = False
    raise_on_evaluator_error: bool = False
