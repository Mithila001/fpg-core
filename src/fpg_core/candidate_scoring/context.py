from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .types import CandidateScoringInput


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """Read-only data shared with evaluators.

    `derived` is prepared once by the context factory and may contain indexes or
    reusable geometry required by several evaluators. Concrete evaluators should
    not mutate any value held by this object.
    """

    scoring_input: CandidateScoringInput
    derived: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "derived", MappingProxyType(dict(self.derived)))


class ScoringContextFactory:
    """Single extension point for preparing shared evaluator data."""

    def build(self, scoring_input: CandidateScoringInput) -> ScoringContext:
        return ScoringContext(scoring_input=scoring_input)
