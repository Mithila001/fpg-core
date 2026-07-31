from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import NewType

from ..domain import FloorPlanGenerationSpec

EvaluatorKey = NewType("EvaluatorKey", str)

MIN_EVALUATOR_SCORE = 0.0
MAX_EVALUATOR_SCORE = 100.0


class EvaluatorCategory(str, Enum):
    """Determines how an evaluator participates in the scoring pipeline."""

    CRITICAL = "critical"
    QUALITY = "quality"


class EvaluationStatus(str, Enum):
    """Execution state of one evaluator."""

    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    ERROR = "error"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScoreFinding:
    """Structured explanation emitted by an evaluator or the manager."""

    code: str
    message: str
    severity: FindingSeverity = FindingSeverity.INFO
    subject_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluatorResult:
    """Standard result returned by every concrete evaluator.

    `score` is always expressed on the common 0..100 scale when status is
    COMPLETED. For other statuses, score must be None.
    """

    evaluator_key: EvaluatorKey
    status: EvaluationStatus
    score: float | None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    visualization_payload: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionResult:
    """Manager-owned view of one evaluator's execution and contribution."""

    evaluator_key: EvaluatorKey
    category: EvaluatorCategory
    status: EvaluationStatus
    raw_score: float | None
    configured_weight: float
    normalized_weight: float
    contribution: float
    threshold: float | None = None
    passed_threshold: bool | None = None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    visualization_payload: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Complete score-manager output for one candidate."""

    total_score: float
    passed_critical_checks: bool
    stopped_early: bool
    stop_reason: str | None
    evaluator_results: tuple[EvaluatorExecutionResult, ...]
    findings: tuple[ScoreFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateScoringInput:
    """Scoring input for one typed generation specification and candidate.

    Candidate arrangements remain structurally typed because Candidate Search
    owns their point contract. The shared generation specification comes from
    the project's shared ``fpg_core.domain`` package.
    """

    specification: FloorPlanGenerationSpec
    candidate: object
