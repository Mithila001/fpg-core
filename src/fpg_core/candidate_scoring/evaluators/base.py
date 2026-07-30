from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from ..context import ScoringContext
from ..types import EvaluatorKey, EvaluatorResult


class CandidateEvaluator(ABC):
    """Contract implemented by every candidate-scoring evaluator.

    Evaluators know only their own scoring logic. They do not know their
    category, contribution weight, critical threshold, execution order, or the
    final total-score calculation.
    """

    @property
    @abstractmethod
    def key(self) -> EvaluatorKey:
        """Stable key used to register and configure the evaluator."""

    @abstractmethod
    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        """Evaluate one candidate and return a standardized 0..100 result."""
