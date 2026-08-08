from __future__ import annotations

from dataclasses import dataclass

from .types import EvaluatorKey, GroupKey


@dataclass(frozen=True, slots=True)
class ScoringGroupRule:
    """Configuration for one scoring group."""

    key: GroupKey
    enabled: bool = True
    order: int = 0
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class EvaluatorRule:
    """Configuration for one registered evaluator inside a scoring group."""

    key: EvaluatorKey
    group_key: GroupKey
    settings: object
    enabled: bool = True
    order: int = 0
    weight: float = 1.0
    minimum_score: float | None = None


@dataclass(frozen=True, slots=True)
class FloorPlanScoringConfig:
    """Reusable configuration controlling how a floor plan is scored."""

    groups: tuple[ScoringGroupRule, ...]
    evaluators: tuple[EvaluatorRule, ...]

    def __post_init__(self) -> None:
        groups = tuple(self.groups)
        evaluators = tuple(self.evaluators)

        if any(not isinstance(group, ScoringGroupRule) for group in groups):
            raise TypeError("Every scoring group must be a ScoringGroupRule instance.")
        if any(not isinstance(rule, EvaluatorRule) for rule in evaluators):
            raise TypeError("Every evaluator rule must be an EvaluatorRule instance.")

        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "evaluators", evaluators)


# Compatibility name retained for existing consumers. A scoring profile is the
# reusable floor-plan-scoring configuration.
ScoringProfile = FloorPlanScoringConfig


__all__ = [
    "EvaluatorRule",
    "FloorPlanScoringConfig",
    "ScoringGroupRule",
    "ScoringProfile",
]
