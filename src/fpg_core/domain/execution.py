from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar


class ExecutionMode(StrEnum):
    """Controls how much non-result execution data a feature may collect."""

    PRODUCTION = "production"
    RND = "rnd"
    DEBUG = "debug"


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    """Small execution-wide metadata shared by all feature operations."""

    mode: ExecutionMode
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ExecutionMode):
            raise TypeError("mode must be an ExecutionMode instance.")
        if isinstance(self.duration_seconds, bool):
            raise TypeError("duration_seconds must be numeric, not boolean.")

        try:
            duration_seconds = float(self.duration_seconds)
        except (TypeError, ValueError) as exc:
            raise TypeError("duration_seconds must be numeric.") from exc

        if not math.isfinite(duration_seconds):
            raise ValueError("duration_seconds must be finite.")
        if duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative.")

        object.__setattr__(self, "duration_seconds", duration_seconds)


TResult = TypeVar("TResult")
TDetails = TypeVar("TDetails")


@dataclass(frozen=True, slots=True)
class FeatureExecution(Generic[TResult, TDetails]):
    """Standard envelope returned by completed FPG Core feature operations."""

    result: TResult
    details: TDetails | None
    metadata: ExecutionMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, ExecutionMetadata):
            raise TypeError("metadata must be an ExecutionMetadata instance.")
