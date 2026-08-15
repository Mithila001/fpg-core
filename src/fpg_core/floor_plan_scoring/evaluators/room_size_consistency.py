from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ...domain import RoomType
from ..context import NormalizedRoom, NormalizedRoomSpec, ScoringContext
from ..exceptions import ScoringConfigurationError
from ..types import (
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    FindingSeverity,
    ScoreFinding,
    ScoreMetric,
)
from .base import FloorPlanEvaluator
from .common import clamp_score, require_non_negative, require_positive, typed_settings

ROOM_SIZE_CONSISTENCY_KEY = EvaluatorKey("room_size_consistency")


class RoomAreaAggregation(str, Enum):
    """How multiple rooms of the same type are reduced to one comparable area."""

    MIN = "min"
    AVERAGE = "average"
    MAX = "max"
    TOTAL = "total"


@dataclass(frozen=True, slots=True)
class RoomSizeRelationRule:
    """Preferred area ratio between two room types.

    The evaluated ratio is:

        compared_area / reference_area

    For example, ``reference_type=LIVING_ROOM``, ``compared_type=KITCHEN`` and
    ``max_ratio=0.8`` means the selected kitchen area should preferably be no
    more than 80% of the selected living-room area.
    """

    reference_type: RoomType
    compared_type: RoomType
    min_ratio: float | None = None
    max_ratio: float | None = None
    reference_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX
    compared_aggregation: RoomAreaAggregation = RoomAreaAggregation.MAX
    weight: float = 1.0
    full_penalty_ratio_delta: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference_type, RoomType):
            raise TypeError("reference_type must be a RoomType enum member.")
        if not isinstance(self.compared_type, RoomType):
            raise TypeError("compared_type must be a RoomType enum member.")
        if self.reference_type is self.compared_type:
            raise ScoringConfigurationError(
                "Room-size relation rules must compare different room types. "
                "Use RoomTypeConsistencyRule for same-type consistency."
            )
        if not isinstance(self.reference_aggregation, RoomAreaAggregation):
            raise TypeError(
                "reference_aggregation must be a RoomAreaAggregation enum member."
            )
        if not isinstance(self.compared_aggregation, RoomAreaAggregation):
            raise TypeError(
                "compared_aggregation must be a RoomAreaAggregation enum member."
            )
        if self.min_ratio is None and self.max_ratio is None:
            raise ScoringConfigurationError(
                "Room-size relation rules require min_ratio, max_ratio, or both."
            )
        if self.min_ratio is not None:
            require_positive(self.min_ratio, "Room-size relation min_ratio")
        if self.max_ratio is not None:
            require_positive(self.max_ratio, "Room-size relation max_ratio")
        if (
            self.min_ratio is not None
            and self.max_ratio is not None
            and self.min_ratio > self.max_ratio
        ):
            raise ScoringConfigurationError(
                "Room-size relation min_ratio cannot exceed max_ratio."
            )
        require_positive(self.weight, "Room-size relation weight")
        if self.full_penalty_ratio_delta is not None:
            require_positive(
                self.full_penalty_ratio_delta,
                "Room-size relation full_penalty_ratio_delta",
            )


@dataclass(frozen=True, slots=True)
class RoomTypeConsistencyRule:
    """Preferred spread among multiple rooms of one type.

    ``maximum_spread_ratio`` is ``largest_area / smallest_area - 1``. A value
    of ``0.25`` therefore allows the largest room to be up to 25% larger than
    the smallest room before a penalty begins.
    """

    room_type: RoomType
    maximum_spread_ratio: float
    weight: float = 1.0
    full_penalty_ratio_delta: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.room_type, RoomType):
            raise TypeError("room_type must be a RoomType enum member.")
        require_non_negative(
            self.maximum_spread_ratio,
            "Room-type consistency maximum_spread_ratio",
        )
        require_positive(self.weight, "Room-type consistency weight")
        if self.full_penalty_ratio_delta is not None:
            require_positive(
                self.full_penalty_ratio_delta,
                "Room-type consistency full_penalty_ratio_delta",
            )


@dataclass(frozen=True, slots=True)
class RoomSizeConsistencySettings:
    relation_rules: tuple[RoomSizeRelationRule, ...] = ()
    consistency_rules: tuple[RoomTypeConsistencyRule, ...] = ()
    default_full_penalty_ratio_delta: float = 0.5

    def __post_init__(self) -> None:
        relation_rules = tuple(self.relation_rules)
        consistency_rules = tuple(self.consistency_rules)
        if any(not isinstance(rule, RoomSizeRelationRule) for rule in relation_rules):
            raise TypeError("Every relation rule must be a RoomSizeRelationRule.")
        if any(
            not isinstance(rule, RoomTypeConsistencyRule)
            for rule in consistency_rules
        ):
            raise TypeError(
                "Every consistency rule must be a RoomTypeConsistencyRule."
            )
        if not relation_rules and not consistency_rules:
            raise ScoringConfigurationError(
                "Room-size consistency requires at least one configured rule."
            )
        require_positive(
            self.default_full_penalty_ratio_delta,
            "Room-size consistency default_full_penalty_ratio_delta",
        )

        relation_keys: set[tuple[RoomType, RoomType]] = set()
        for rule in relation_rules:
            key = (rule.reference_type, rule.compared_type)
            if key in relation_keys:
                raise ScoringConfigurationError(
                    "Duplicate room-size relation rule for "
                    f"'{rule.reference_type.value}' -> '{rule.compared_type.value}'."
                )
            relation_keys.add(key)

        consistency_types: set[RoomType] = set()
        for rule in consistency_rules:
            if rule.room_type in consistency_types:
                raise ScoringConfigurationError(
                    "Duplicate room-type consistency rule for "
                    f"'{rule.room_type.value}'."
                )
            consistency_types.add(rule.room_type)

        object.__setattr__(self, "relation_rules", relation_rules)
        object.__setattr__(self, "consistency_rules", consistency_rules)


@dataclass(frozen=True, slots=True)
class _RuleScore:
    score: float
    weight: float
    findings: tuple[ScoreFinding, ...]
    metrics: tuple[ScoreMetric, ...]


class RoomSizeConsistencyEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return ROOM_SIZE_CONSISTENCY_KEY

    @property
    def settings_type(self) -> type[object]:
        return RoomSizeConsistencySettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(
            settings,
            RoomSizeConsistencySettings,
            str(self.key),
        )
        scored_rules: list[_RuleScore] = []

        for rule in config.relation_rules:
            scored = _score_relation(context, rule, config)
            if scored is not None:
                scored_rules.append(scored)

        for rule in config.consistency_rules:
            scored = _score_same_type(context, rule, config)
            if scored is not None:
                scored_rules.append(scored)

        if not scored_rules:
            return EvaluatorResult(
                self.key,
                EvaluationStatus.NOT_APPLICABLE,
                None,
            )

        total_weight = sum(item.weight for item in scored_rules)
        score = sum(item.score * item.weight for item in scored_rules) / total_weight
        findings = tuple(
            finding
            for item in scored_rules
            for finding in item.findings
        )
        metrics = (
            ScoreMetric("applicable_rule_count", float(len(scored_rules))),
            *(
                metric
                for item in scored_rules
                for metric in item.metrics
            ),
        )
        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=clamp_score(score),
            findings=findings,
            metrics=tuple(metrics),
        )


def _score_relation(
    context: ScoringContext,
    rule: RoomSizeRelationRule,
    config: RoomSizeConsistencySettings,
) -> _RuleScore | None:
    reference_rooms = _rooms_of_type(context, rule.reference_type)
    compared_rooms = _rooms_of_type(context, rule.compared_type)
    if not reference_rooms or not compared_rooms:
        return None

    reference_specs = _specs_for_rooms(context, reference_rooms)
    compared_specs = _specs_for_rooms(context, compared_rooms)

    reference_area = _aggregate_actual(reference_rooms, rule.reference_aggregation)
    compared_area = _aggregate_actual(compared_rooms, rule.compared_aggregation)
    reference_min, reference_max = _aggregate_feasible_range(
        reference_specs,
        rule.reference_aggregation,
    )
    compared_min, compared_max = _aggregate_feasible_range(
        compared_specs,
        rule.compared_aggregation,
    )

    actual_ratio = compared_area / reference_area
    feasible_min_ratio = compared_min / reference_max
    feasible_max_ratio = compared_max / reference_min

    effective_min = rule.min_ratio
    effective_max = rule.max_ratio
    min_adjusted = False
    max_adjusted = False
    if effective_min is not None and effective_min > feasible_max_ratio:
        effective_min = feasible_max_ratio
        min_adjusted = True
    if effective_max is not None and effective_max < feasible_min_ratio:
        effective_max = feasible_min_ratio
        max_adjusted = True

    full_penalty_delta = (
        rule.full_penalty_ratio_delta
        if rule.full_penalty_ratio_delta is not None
        else config.default_full_penalty_ratio_delta
    )
    violation_delta = _ratio_violation_delta(
        actual_ratio,
        effective_min,
        effective_max,
    )
    score = clamp_score(100.0 * (1.0 - violation_delta / full_penalty_delta))

    relation_name = f"{rule.reference_type.value}_to_{rule.compared_type.value}"
    metrics = [
        ScoreMetric(f"{relation_name}.score", score),
        ScoreMetric(f"{relation_name}.actual_ratio", actual_ratio),
        ScoreMetric(f"{relation_name}.feasible_min_ratio", feasible_min_ratio),
        ScoreMetric(f"{relation_name}.feasible_max_ratio", feasible_max_ratio),
        ScoreMetric(f"{relation_name}.violation_delta", violation_delta),
    ]
    configured_min = rule.min_ratio
    if configured_min is not None:
        # effective_min starts from configured_min and can only be replaced by
        # a feasible float threshold above, so it cannot be None here.
        assert effective_min is not None
        metrics.extend(
            (
                ScoreMetric(f"{relation_name}.configured_min_ratio", configured_min),
                ScoreMetric(f"{relation_name}.effective_min_ratio", effective_min),
            )
        )

    configured_max = rule.max_ratio
    if configured_max is not None:
        # effective_max follows the same invariant as effective_min.
        assert effective_max is not None
        metrics.extend(
            (
                ScoreMetric(f"{relation_name}.configured_max_ratio", configured_max),
                ScoreMetric(f"{relation_name}.effective_max_ratio", effective_max),
            )
        )

    findings: list[ScoreFinding] = []
    if min_adjusted or max_adjusted:
        findings.append(
            ScoreFinding(
                code="ROOM_SIZE_RELATION_ADJUSTED_FOR_FEASIBILITY",
                message=(
                    "Room-size preference for "
                    f"'{rule.reference_type.value}' -> '{rule.compared_type.value}' "
                    "was adjusted because the configured room-area limits make the "
                    "original ratio impossible."
                ),
                severity=FindingSeverity.INFO,
                metrics=tuple(
                    metric
                    for metric in metrics
                    if "configured_" in metric.name
                    or "effective_" in metric.name
                    or "feasible_" in metric.name
                ),
            )
        )
    if violation_delta > 0:
        findings.append(
            ScoreFinding(
                code="ROOM_SIZE_RELATION_VIOLATION",
                message=(
                    f"The actual {rule.compared_type.value}/{rule.reference_type.value} "
                    "area ratio is outside the effective preferred range."
                ),
                severity=FindingSeverity.WARNING,
                subject_ids=tuple(
                    room.room_id for room in (*reference_rooms, *compared_rooms)
                ),
                metrics=(
                    ScoreMetric("actual_ratio", actual_ratio),
                    ScoreMetric("violation_delta", violation_delta),
                    ScoreMetric("rule_score", score),
                ),
            )
        )

    return _RuleScore(
        score=score,
        weight=rule.weight,
        findings=tuple(findings),
        metrics=tuple(metrics),
    )


def _score_same_type(
    context: ScoringContext,
    rule: RoomTypeConsistencyRule,
    config: RoomSizeConsistencySettings,
) -> _RuleScore | None:
    rooms = _rooms_of_type(context, rule.room_type)
    if len(rooms) < 2:
        return None

    specs = _specs_for_rooms(context, rooms)
    smallest_area = min(room.area for room in rooms)
    largest_area = max(room.area for room in rooms)
    actual_spread = largest_area / smallest_area - 1.0

    largest_required_minimum = max(spec.size.min_area for spec in specs)
    smallest_allowed_maximum = min(spec.size.max_area for spec in specs)
    feasible_minimum_spread = max(
        0.0,
        largest_required_minimum / smallest_allowed_maximum - 1.0,
    )
    effective_maximum_spread = max(
        rule.maximum_spread_ratio,
        feasible_minimum_spread,
    )
    adjusted = effective_maximum_spread > rule.maximum_spread_ratio

    full_penalty_delta = (
        rule.full_penalty_ratio_delta
        if rule.full_penalty_ratio_delta is not None
        else config.default_full_penalty_ratio_delta
    )
    violation_delta = max(0.0, actual_spread - effective_maximum_spread)
    score = clamp_score(100.0 * (1.0 - violation_delta / full_penalty_delta))

    metric_prefix = f"{rule.room_type.value}_consistency"
    metrics = (
        ScoreMetric(f"{metric_prefix}.score", score),
        ScoreMetric(f"{metric_prefix}.actual_spread_ratio", actual_spread),
        ScoreMetric(
            f"{metric_prefix}.configured_maximum_spread_ratio",
            rule.maximum_spread_ratio,
        ),
        ScoreMetric(
            f"{metric_prefix}.feasible_minimum_spread_ratio",
            feasible_minimum_spread,
        ),
        ScoreMetric(
            f"{metric_prefix}.effective_maximum_spread_ratio",
            effective_maximum_spread,
        ),
        ScoreMetric(f"{metric_prefix}.violation_delta", violation_delta),
    )

    findings: list[ScoreFinding] = []
    if adjusted:
        findings.append(
            ScoreFinding(
                code="ROOM_TYPE_CONSISTENCY_ADJUSTED_FOR_FEASIBILITY",
                message=(
                    f"The '{rule.room_type.value}' consistency preference was "
                    "relaxed because the configured room-area limits make the "
                    "original spread impossible."
                ),
                severity=FindingSeverity.INFO,
                subject_ids=tuple(room.room_id for room in rooms),
                metrics=(
                    ScoreMetric(
                        "configured_maximum_spread_ratio",
                        rule.maximum_spread_ratio,
                    ),
                    ScoreMetric(
                        "feasible_minimum_spread_ratio",
                        feasible_minimum_spread,
                    ),
                    ScoreMetric(
                        "effective_maximum_spread_ratio",
                        effective_maximum_spread,
                    ),
                ),
            )
        )
    if violation_delta > 0:
        findings.append(
            ScoreFinding(
                code="ROOM_TYPE_SIZE_INCONSISTENCY",
                message=(
                    f"The '{rule.room_type.value}' room areas exceed the preferred "
                    "size spread."
                ),
                severity=FindingSeverity.WARNING,
                subject_ids=tuple(room.room_id for room in rooms),
                metrics=(
                    ScoreMetric("actual_spread_ratio", actual_spread),
                    ScoreMetric(
                        "effective_maximum_spread_ratio",
                        effective_maximum_spread,
                    ),
                    ScoreMetric("violation_delta", violation_delta),
                    ScoreMetric("rule_score", score),
                ),
            )
        )

    return _RuleScore(
        score=score,
        weight=rule.weight,
        findings=tuple(findings),
        metrics=metrics,
    )


def _rooms_of_type(
    context: ScoringContext,
    room_type: RoomType,
) -> tuple[NormalizedRoom, ...]:
    return tuple(room for room in context.rooms if room.room_type is room_type)


def _specs_for_rooms(
    context: ScoringContext,
    rooms: tuple[NormalizedRoom, ...],
) -> tuple[NormalizedRoomSpec, ...]:
    return tuple(context.specs_by_id[room.room_id] for room in rooms)


def _aggregate_actual(
    rooms: tuple[NormalizedRoom, ...],
    aggregation: RoomAreaAggregation,
) -> float:
    return _aggregate_values(tuple(room.area for room in rooms), aggregation)


def _aggregate_feasible_range(
    specs: tuple[NormalizedRoomSpec, ...],
    aggregation: RoomAreaAggregation,
) -> tuple[float, float]:
    minimums = tuple(spec.size.min_area for spec in specs)
    maximums = tuple(spec.size.max_area for spec in specs)
    if aggregation is RoomAreaAggregation.MIN:
        return min(minimums), min(maximums)
    if aggregation is RoomAreaAggregation.MAX:
        return max(minimums), max(maximums)
    if aggregation is RoomAreaAggregation.TOTAL:
        return sum(minimums), sum(maximums)
    return sum(minimums) / len(minimums), sum(maximums) / len(maximums)


def _aggregate_values(
    values: tuple[float, ...],
    aggregation: RoomAreaAggregation,
) -> float:
    if aggregation is RoomAreaAggregation.MIN:
        return min(values)
    if aggregation is RoomAreaAggregation.MAX:
        return max(values)
    if aggregation is RoomAreaAggregation.TOTAL:
        return sum(values)
    return sum(values) / len(values)


def _ratio_violation_delta(
    actual_ratio: float,
    minimum_ratio: float | None,
    maximum_ratio: float | None,
) -> float:
    if minimum_ratio is not None and actual_ratio < minimum_ratio:
        return minimum_ratio - actual_ratio
    if maximum_ratio is not None and actual_ratio > maximum_ratio:
        return actual_ratio - maximum_ratio
    return 0.0


__all__ = [
    "ROOM_SIZE_CONSISTENCY_KEY",
    "RoomAreaAggregation",
    "RoomSizeConsistencyEvaluator",
    "RoomSizeConsistencySettings",
    "RoomSizeRelationRule",
    "RoomTypeConsistencyRule",
]
