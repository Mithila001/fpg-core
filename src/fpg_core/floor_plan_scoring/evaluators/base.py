from __future__ import annotations

from abc import ABC, abstractmethod

from ..context import ScoringContext
from ..types import EvaluatorKey, EvaluatorResult


class FloorPlanEvaluator(ABC):
    """Common contract for all floor-plan evaluators."""

    @property
    @abstractmethod
    def key(self) -> EvaluatorKey: ...

    @property
    @abstractmethod
    def settings_type(self) -> type[object]: ...

    @abstractmethod
    def evaluate(
        self, context: ScoringContext, settings: object
    ) -> EvaluatorResult: ...
