from __future__ import annotations

import math
from typing import TypeVar

from ..exceptions import ScoringConfigurationError

T = TypeVar("T")


def typed_settings(settings: object, expected: type[T], evaluator_key: str) -> T:
    if not isinstance(settings, expected):
        raise ScoringConfigurationError(
            f"Evaluator '{evaluator_key}' requires {expected.__name__} settings."
        )
    return settings


def require_positive(value: float, label: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ScoringConfigurationError(
            f"{label} must be finite and greater than zero."
        )


def require_non_negative(value: float, label: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ScoringConfigurationError(f"{label} must be finite and non-negative.")


def clamp_score(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
