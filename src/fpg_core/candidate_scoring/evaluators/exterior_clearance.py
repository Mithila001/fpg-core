from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import box

from ...domain import ExecutionMode, LandSide
from ..config import ExteriorClearanceRule
from ..context import ScoringContext
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult
from .base import CandidateEvaluator
from .common import build_evaluation_data

EXTERIOR_CLEARANCE_KEY = EvaluatorKey("exterior_clearance")


class ExteriorClearanceEvaluator(CandidateEvaluator):
    """Score the unobstructed projected width of eligible room footprints."""

    @property
    def key(self):
        return EXTERIOR_CLEARANCE_KEY

    def evaluate(self, context: ScoringContext, settings: Mapping[str, Any]):
        rules = settings.get("rules", ())
        if not isinstance(rules, Sequence) or any(
            not isinstance(r, ExteriorClearanceRule) for r in rules
        ):
            raise TypeError("rules must contain ExteriorClearanceRule values")
        data = build_evaluation_data(context)
        footprints = context.derived["footprints"]
        circles = context.derived["circles"]
        results = []
        for index, rule in enumerate(rules):
            rooms = {}
            assessments = []
            for key, footprint in footprints.items():
                point, radius = footprint.point, footprint.radius
                if point.room_type not in rule.room_types:
                    continue
                if rule.direction is LandSide.FRONT:
                    bounds = (point.x - radius, 0, point.x + radius, point.y)
                elif rule.direction is LandSide.BACK:
                    bounds = (
                        point.x - radius,
                        point.y,
                        point.x + radius,
                        data.floor_length,
                    )
                elif rule.direction is LandSide.LEFT:
                    bounds = (0, point.y - radius, point.x, point.y + radius)
                else:
                    bounds = (
                        point.x,
                        point.y - radius,
                        data.floor_width,
                        point.y + radius,
                    )
                projection = box(*bounds)
                intervals, blockers = [], []
                horizontal = rule.direction in (LandSide.FRONT, LandSide.BACK)
                for other_key, other in footprints.items():
                    if other.point.source_room_id == point.source_room_id:
                        continue
                    intersection = projection.intersection(circles[other_key])
                    if intersection.is_empty or intersection.area <= 0:
                        continue
                    x0, y0, x1, y1 = intersection.bounds
                    intervals.append((x0, x1) if horizontal else (y0, y1))
                    blockers.append(
                        {"point_id": other_key, "room_id": other.point.source_room_id}
                    )
                intervals.sort()
                merged = []
                for start, end in intervals:
                    if merged and start <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                    else:
                        merged.append((start, end))
                obstructed = sum(end - start for start, end in merged)
                ratio = min(1.0, obstructed / (2 * radius))
                assessment = {
                    "point_id": key,
                    "room_id": point.source_room_id,
                    "bounds": bounds,
                    "blockers": blockers,
                    "obstructed_width": obstructed,
                    "clearance_ratio": 1 - ratio,
                    "score": 100 * (1 - ratio),
                }
                assessments.append(assessment)
                if (
                    point.source_room_id not in rooms
                    or assessment["score"] > rooms[point.source_room_id]["score"]
                ):
                    rooms[point.source_room_id] = assessment
            if rooms:
                selected = sorted(
                    rooms.values(), key=lambda item: (-item["score"], item["room_id"])
                )[: rule.required_clear_room_count]
                score = (
                    sum(item["score"] for item in selected)
                    / rule.required_clear_room_count
                )
                results.append(
                    {
                        "rule_index": index,
                        "direction": rule.direction.value,
                        "score": score,
                        "required_count": rule.required_clear_room_count,
                        "rooms": list(rooms.values()),
                        "projections": assessments,
                        "selected_room_ids": [item["room_id"] for item in selected],
                    }
                )
        if not results:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        score = sum(item["score"] for item in results) / len(results)
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            score,
            metrics={
                "applicable_rule_count": float(len(results)),
                "final_clearance_score": score,
            }
            if context.mode is ExecutionMode.DEBUG
            else {},
            details={
                "floor_width": data.floor_width,
                "floor_length": data.floor_length,
                "rules": results,
            }
            if context.mode is ExecutionMode.DEBUG
            else None,
        )
