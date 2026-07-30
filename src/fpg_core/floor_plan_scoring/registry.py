from __future__ import annotations

from collections.abc import Iterable

from .evaluators.base import FloorPlanEvaluator
from .exceptions import EvaluatorRegistrationError
from .types import EvaluatorKey


class EvaluatorRegistry:
    def __init__(self, evaluators: Iterable[FloorPlanEvaluator] = ()) -> None:
        self._evaluators: dict[EvaluatorKey, FloorPlanEvaluator] = {}
        for evaluator in evaluators:
            self.register(evaluator)

    def register(self, evaluator: FloorPlanEvaluator) -> None:
        if not isinstance(evaluator, FloorPlanEvaluator):
            raise EvaluatorRegistrationError(
                "Registered evaluators must implement FloorPlanEvaluator."
            )
        if evaluator.key in self._evaluators:
            raise EvaluatorRegistrationError(
                f"Evaluator '{evaluator.key}' is already registered."
            )
        self._evaluators[evaluator.key] = evaluator

    def get(self, key: EvaluatorKey) -> FloorPlanEvaluator:
        try:
            return self._evaluators[key]
        except KeyError as exc:
            raise EvaluatorRegistrationError(
                f"No evaluator is registered for key '{key}'."
            ) from exc

    def contains(self, key: EvaluatorKey) -> bool:
        return key in self._evaluators
