from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import EvaluatorKey, GroupKey


@dataclass(frozen=True, slots=True)
class ScoringGroupRule:
    key: GroupKey
    enabled: bool = True
    order: int = 0
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class EvaluatorRule:
    key: EvaluatorKey
    group_key: GroupKey
    settings: Any
    enabled: bool = True
    order: int = 0
    weight: float = 1.0
    minimum_score: float | None = None


@dataclass(frozen=True, slots=True)
class ScoringProfile:
    groups: tuple[ScoringGroupRule, ...]
    evaluators: tuple[EvaluatorRule, ...]
