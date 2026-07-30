from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NewType

GroupKey = NewType("GroupKey", str)
EvaluatorKey = NewType("EvaluatorKey", str)

CRITICAL_GROUP = GroupKey("critical")
FUNCTIONAL_GROUP = GroupKey("functional")
AESTHETIC_GROUP = GroupKey("aesthetic")
EXTRA_GROUP = GroupKey("extra")


class EvaluationStatus(str, Enum):
    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"


class GroupStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScoreMetric:
    name: str
    value: float
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreFinding:
    code: str
    message: str
    severity: FindingSeverity = FindingSeverity.INFO
    subject_ids: tuple[str, ...] = ()
    metrics: tuple[ScoreMetric, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluatorResult:
    evaluator_key: EvaluatorKey
    status: EvaluationStatus
    score: float | None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: tuple[ScoreMetric, ...] = ()
    visualization_payload: object | None = None


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionResult:
    evaluator_key: EvaluatorKey
    group_key: GroupKey
    status: EvaluationStatus
    raw_score: float | None
    configured_weight: float
    normalized_weight: float = 0.0
    contribution: float = 0.0
    threshold: float | None = None
    passed_threshold: bool | None = None
    findings: tuple[ScoreFinding, ...] = ()
    metrics: tuple[ScoreMetric, ...] = ()
    visualization_payload: object | None = None


@dataclass(frozen=True, slots=True)
class ScoringGroupResult:
    group_key: GroupKey
    status: GroupStatus
    normalized_maximum: float
    raw_score: float | None
    contribution: float


@dataclass(frozen=True, slots=True)
class FloorPlanScoringResult:
    total_score: float
    passed_critical: bool
    critical_failure: ScoreFinding | None
    group_results: tuple[ScoringGroupResult, ...]
    evaluator_results: tuple[EvaluatorExecutionResult, ...]
    findings: tuple[ScoreFinding, ...] = field(default_factory=tuple)
