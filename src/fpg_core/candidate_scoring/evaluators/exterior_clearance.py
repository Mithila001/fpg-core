from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ...domain import ExecutionMode, LandSide, RoomType
from ..config import ExteriorClearanceRule
from ..context import ScoringContext
from ..types import (
    ClearanceCorridorBounds,
    ClearanceCorridorDebug,
    EvaluationStatus,
    EvaluatorKey,
    EvaluatorResult,
    ExteriorClearanceDetails,
    ExteriorClearanceRoomEvaluation,
    ExteriorClearanceRuleEvaluation,
    FindingSeverity,
    ScoreFinding,
)
from .base import CandidateEvaluator
from .common import EvaluationPoint, build_evaluation_data, clamp_score

EXTERIOR_CLEARANCE_KEY = EvaluatorKey("exterior_clearance")


@dataclass(frozen=True, slots=True)
class _PointAssessment:
    point: EvaluationPoint
    bounds: ClearanceCorridorBounds
    blockers: tuple[EvaluationPoint, ...]

    @property
    def is_clear(self) -> bool:
        return not self.blockers


@dataclass(frozen=True, slots=True)
class _RoomAssessment:
    source_room_id: str
    room_name: str
    room_type: RoomType
    points: tuple[_PointAssessment, ...]

    @property
    def clear_points(self) -> tuple[_PointAssessment, ...]:
        return tuple(point for point in self.points if point.is_clear)

    @property
    def qualifies(self) -> bool:
        return bool(self.clear_points)


class ExteriorClearanceEvaluator(CandidateEvaluator):
    """Scores directional no-hint-point corridors from hints to the boundary."""

    @property
    def key(self) -> EvaluatorKey:
        return EXTERIOR_CLEARANCE_KEY

    def evaluate(
        self,
        context: ScoringContext,
        settings: Mapping[str, Any],
    ) -> EvaluatorResult:
        data = build_evaluation_data(context)
        rules = _clearance_rules(settings)
        debug_enabled = context.mode is ExecutionMode.DEBUG

        if not rules:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_EXTERIOR_CLEARANCE_RULES",
                        message="No exterior-clearance rules were configured.",
                    ),
                ),
                details=(
                    ExteriorClearanceDetails(
                        floor_width=data.floor_width,
                        floor_length=data.floor_length,
                        rule_evaluations=(),
                        corridors=(),
                    )
                    if debug_enabled
                    else None
                ),
            )

        findings: list[ScoreFinding] = []
        scores: list[float] = []
        rule_details: list[ExteriorClearanceRuleEvaluation] = []
        corridor_details: list[ClearanceCorridorDebug] = []
        metrics: dict[str, float] = {}

        for rule_index, rule in enumerate(rules):
            eligible_points = tuple(
                point for point in data.points if point.room_type in rule.room_types
            )
            points_by_room = _group_by_source_room(eligible_points)

            if not points_by_room:
                if debug_enabled:
                    rule_details.append(
                        ExteriorClearanceRuleEvaluation(
                            rule_index=rule_index,
                            room_types=rule.room_types,
                            required_clear_room_count=rule.required_clear_room_count,
                            clearance_width=rule.clearance_width,
                            direction=rule.direction,
                            applicable=False,
                            eligible_room_count=0,
                            clear_room_count=0,
                            score=None,
                            room_evaluations=(),
                        )
                    )
                continue

            room_assessments = tuple(
                _assess_room(
                    room_points,
                    rule=rule,
                    all_points=data.points,
                    floor_width=data.floor_width,
                    floor_length=data.floor_length,
                )
                for room_points in points_by_room.values()
            )
            clear_rooms = tuple(room for room in room_assessments if room.qualifies)
            selected_rooms = clear_rooms[: rule.required_clear_room_count]
            selected_room_ids = {
                room.source_room_id for room in selected_rooms
            }

            rule_score = clamp_score(
                100.0
                * min(len(clear_rooms), rule.required_clear_room_count)
                / rule.required_clear_room_count
            )
            scores.append(rule_score)

            if len(clear_rooms) < rule.required_clear_room_count:
                eligible_ids = tuple(
                    room.source_room_id for room in room_assessments
                )
                findings.append(
                    ScoreFinding(
                        code="EXTERIOR_CLEARANCE_REQUIREMENT_UNMET",
                        message=(
                            f"Exterior-clearance rule {rule_index + 1} requires "
                            f"{rule.required_clear_room_count} clear room(s), but "
                            f"{len(clear_rooms)} of {len(room_assessments)} eligible "
                            "room(s) qualified."
                        ),
                        severity=FindingSeverity.WARNING,
                        subject_ids=eligible_ids,
                    )
                )

            if debug_enabled:
                room_details: list[ExteriorClearanceRoomEvaluation] = []
                for room in room_assessments:
                    selected = room.source_room_id in selected_room_ids
                    selected_point_id = (
                        room.clear_points[0].point.room_id
                        if selected and room.clear_points
                        else None
                    )
                    room_details.append(
                        ExteriorClearanceRoomEvaluation(
                            source_room_id=room.source_room_id,
                            room_name=room.room_name,
                            room_type=room.room_type,
                            point_ids=tuple(
                                assessment.point.room_id
                                for assessment in room.points
                            ),
                            clear_point_ids=tuple(
                                assessment.point.room_id
                                for assessment in room.clear_points
                            ),
                            qualifies=room.qualifies,
                            selected_for_score=selected,
                        )
                    )

                    for assessment in room.points:
                        corridor_details.append(
                            ClearanceCorridorDebug(
                                rule_index=rule_index,
                                point_id=assessment.point.room_id,
                                source_room_id=assessment.point.source_room_id,
                                room_name=assessment.point.source_room_name,
                                room_type=assessment.point.room_type,
                                hint_x=assessment.point.x,
                                hint_y=assessment.point.y,
                                direction=rule.direction,
                                bounds=assessment.bounds,
                                blocker_point_ids=tuple(
                                    blocker.room_id
                                    for blocker in assessment.blockers
                                ),
                                blocker_room_ids=_unique_source_room_ids(
                                    assessment.blockers
                                ),
                                is_clear=assessment.is_clear,
                                selected_for_score=(
                                    assessment.point.room_id == selected_point_id
                                ),
                            )
                        )

                rule_details.append(
                    ExteriorClearanceRuleEvaluation(
                        rule_index=rule_index,
                        room_types=rule.room_types,
                        required_clear_room_count=rule.required_clear_room_count,
                        clearance_width=rule.clearance_width,
                        direction=rule.direction,
                        applicable=True,
                        eligible_room_count=len(room_assessments),
                        clear_room_count=len(clear_rooms),
                        score=rule_score,
                        room_evaluations=tuple(room_details),
                    )
                )
                metrics[f"rule.{rule_index}.score"] = rule_score
                metrics[f"rule.{rule_index}.eligible_room_count"] = float(
                    len(room_assessments)
                )
                metrics[f"rule.{rule_index}.clear_room_count"] = float(
                    len(clear_rooms)
                )

        details = (
            ExteriorClearanceDetails(
                floor_width=data.floor_width,
                floor_length=data.floor_length,
                rule_evaluations=tuple(rule_details),
                corridors=tuple(corridor_details),
            )
            if debug_enabled
            else None
        )

        if not scores:
            return EvaluatorResult(
                evaluator_key=self.key,
                status=EvaluationStatus.NOT_APPLICABLE,
                score=None,
                findings=(
                    ScoreFinding(
                        code="NO_ELIGIBLE_EXTERIOR_CLEARANCE_ROOMS",
                        message=(
                            "No candidate room matched any configured "
                            "exterior-clearance rule."
                        ),
                    ),
                ),
                details=details,
            )

        final_score = clamp_score(sum(scores) / len(scores))
        if debug_enabled:
            metrics["applicable_rule_count"] = float(len(scores))
            metrics["final_clearance_score"] = final_score

        return EvaluatorResult(
            evaluator_key=self.key,
            status=EvaluationStatus.COMPLETED,
            score=final_score,
            findings=tuple(findings),
            metrics=metrics,
            details=details,
        )


def _clearance_rules(
    settings: Mapping[str, Any],
) -> tuple[ExteriorClearanceRule, ...]:
    raw_rules = settings.get("rules", ())
    if isinstance(raw_rules, (str, bytes)) or not isinstance(raw_rules, Sequence):
        raise TypeError(
            "Exterior-clearance setting 'rules' must be a sequence of "
            "ExteriorClearanceRule values."
        )

    rules = tuple(raw_rules)
    if any(not isinstance(rule, ExteriorClearanceRule) for rule in rules):
        raise TypeError(
            "Every exterior-clearance rule must be an ExteriorClearanceRule."
        )
    return rules


def _group_by_source_room(
    points: tuple[EvaluationPoint, ...],
) -> dict[str, tuple[EvaluationPoint, ...]]:
    grouped: dict[str, list[EvaluationPoint]] = {}
    for point in points:
        grouped.setdefault(point.source_room_id, []).append(point)
    return {room_id: tuple(room_points) for room_id, room_points in grouped.items()}


def _assess_room(
    room_points: tuple[EvaluationPoint, ...],
    *,
    rule: ExteriorClearanceRule,
    all_points: tuple[EvaluationPoint, ...],
    floor_width: float,
    floor_length: float,
) -> _RoomAssessment:
    first = room_points[0]
    assessments = tuple(
        _assess_point(
            point,
            rule=rule,
            all_points=all_points,
            floor_width=floor_width,
            floor_length=floor_length,
        )
        for point in room_points
    )
    return _RoomAssessment(
        source_room_id=first.source_room_id,
        room_name=first.source_room_name,
        room_type=first.room_type,
        points=assessments,
    )


def _assess_point(
    point: EvaluationPoint,
    *,
    rule: ExteriorClearanceRule,
    all_points: tuple[EvaluationPoint, ...],
    floor_width: float,
    floor_length: float,
) -> _PointAssessment:
    bounds = _corridor_bounds(
        point,
        direction=rule.direction,
        clearance_width=rule.clearance_width,
        floor_width=floor_width,
        floor_length=floor_length,
    )
    blockers = tuple(
        other
        for other in all_points
        if other.source_room_id != point.source_room_id
        and _inside_corridor(other, bounds)
    )
    return _PointAssessment(point=point, bounds=bounds, blockers=blockers)


def _corridor_bounds(
    point: EvaluationPoint,
    *,
    direction: LandSide,
    clearance_width: float,
    floor_width: float,
    floor_length: float,
) -> ClearanceCorridorBounds:
    if not 0.0 <= point.x <= floor_width or not 0.0 <= point.y <= floor_length:
        raise ValueError(
            f"Hint point '{point.room_id}' lies outside the floor-plan boundary."
        )

    half_width = clearance_width / 2.0

    if direction is LandSide.RIGHT:
        return ClearanceCorridorBounds(
            min_x=point.x,
            min_y=max(0.0, point.y - half_width),
            max_x=floor_width,
            max_y=min(floor_length, point.y + half_width),
        )
    if direction is LandSide.LEFT:
        return ClearanceCorridorBounds(
            min_x=0.0,
            min_y=max(0.0, point.y - half_width),
            max_x=point.x,
            max_y=min(floor_length, point.y + half_width),
        )
    if direction is LandSide.FRONT:
        return ClearanceCorridorBounds(
            min_x=max(0.0, point.x - half_width),
            min_y=0.0,
            max_x=min(floor_width, point.x + half_width),
            max_y=point.y,
        )
    if direction is LandSide.BACK:
        return ClearanceCorridorBounds(
            min_x=max(0.0, point.x - half_width),
            min_y=point.y,
            max_x=min(floor_width, point.x + half_width),
            max_y=floor_length,
        )
    raise ValueError(f"Unsupported exterior-clearance direction: {direction!r}")


def _inside_corridor(
    point: EvaluationPoint,
    bounds: ClearanceCorridorBounds,
) -> bool:
    return (
        bounds.min_x <= point.x <= bounds.max_x
        and bounds.min_y <= point.y <= bounds.max_y
    )


def _unique_source_room_ids(
    points: tuple[EvaluationPoint, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(point.source_room_id for point in points))
