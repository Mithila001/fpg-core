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


def is_rectilinear(points: tuple[tuple[float, float], ...], tolerance: float) -> bool:
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx <= tolerance and dy <= tolerance:
            continue
        if dx > tolerance and dy > tolerance:
            return False
    return True


def clamp_score(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
