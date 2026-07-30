from __future__ import annotations

from collections.abc import Iterable

from .evaluators.base import CandidateEvaluator
from .exceptions import EvaluatorRegistrationError
from .types import EvaluatorKey


class EvaluatorRegistry:
    """Maps stable evaluator keys to evaluator implementations."""

    def __init__(self, evaluators: Iterable[CandidateEvaluator] = ()) -> None:
        self._evaluators: dict[EvaluatorKey, CandidateEvaluator] = {}
        for evaluator in evaluators:
            self.register(evaluator)

    def register(self, evaluator: CandidateEvaluator) -> None:
        if evaluator.key in self._evaluators:
            raise EvaluatorRegistrationError(
                f"Evaluator '{evaluator.key}' is already registered."
            )
        self._evaluators[evaluator.key] = evaluator

    def get(self, key: EvaluatorKey) -> CandidateEvaluator:
        try:
            return self._evaluators[key]
        except KeyError as exc:
            raise EvaluatorRegistrationError(
                f"No evaluator is registered for key '{key}'."
            ) from exc

    def contains(self, key: EvaluatorKey) -> bool:
        return key in self._evaluators
