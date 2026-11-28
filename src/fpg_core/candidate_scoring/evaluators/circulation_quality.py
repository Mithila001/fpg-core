from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain import ExecutionMode
from ..context import ScoringContext
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult
from .base import CandidateEvaluator
from .common import clamp_score, setting_float

CIRCULATION_QUALITY_KEY = EvaluatorKey("circulation_quality")


class CirculationQualityEvaluator(CandidateEvaluator):
    """Score final route efficiency and separation of hallway traffic."""

    @property
    def key(self) -> EvaluatorKey:
        return CIRCULATION_QUALITY_KEY

    def evaluate(self, context: ScoringContext, settings: Mapping[str, Any]) -> EvaluatorResult:
        for key in ("efficiency_weight", "traffic_separation_weight", "single_hallway_penalty_multiplier", "multiple_hallway_penalty_multiplier"):
            if key in settings and (isinstance(settings[key], bool) or not isinstance(settings[key], (int, float))):
                raise ValueError(f"Setting '{key}' must be numeric.")
        efficiency_weight = setting_float(settings, "efficiency_weight", 0.7)
        separation_weight = setting_float(settings, "traffic_separation_weight", 0.3)
        single = setting_float(settings, "single_hallway_penalty_multiplier", 0.5)
        multiple = setting_float(settings, "multiple_hallway_penalty_multiplier", 1.0)
        if min(efficiency_weight, separation_weight, single, multiple) < 0 or efficiency_weight + separation_weight <= 0 or max(single, multiple) > 1:
            raise ValueError("Invalid circulation quality weights or penalty multipliers.")
        circulation = context.scoring_input.final_circulation
        if circulation is None:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        routes = []
        for route in circulation.routes:
            costs = route.costs
            cost = costs.movement_cost + costs.perimeter_bias_cost + costs.turn_cost
            score = clamp_score(100 * route.manhattan_reference_cost / cost) if cost > 0 else (100.0 if route.manhattan_reference_cost == 0 else 0.0)
            routes.append((score, route.importance_weight))
        route_weight = sum(weight for _, weight in routes)
        efficiency = sum(score * weight for score, weight in routes) / route_weight if route_weight else None
        traffic = []
        multiplier = single if len(circulation.hallways) == 1 else multiple
        for hallway in circulation.hallways:
            public, private = hallway.public_importance_weight, hallway.private_importance_weight
            total = public + private
            if total > 0:
                ratio = 2 * min(public, private) / total
                traffic.append({"point_key": hallway.point_key, "public_weight": public, "private_weight": private, "mixing_ratio": ratio, "penalty": ratio * multiplier, "weight": total})
        total_traffic = sum(item["weight"] for item in traffic)
        separation = clamp_score(100 * (1 - sum(item["penalty"] * item["weight"] for item in traffic) / total_traffic)) if total_traffic else None
        parts = [(efficiency, efficiency_weight), (separation, separation_weight)]
        applicable = [(score, weight) for score, weight in parts if score is not None and weight > 0]
        if not applicable:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        base_score = clamp_score(sum(value * weight for value, weight in applicable) / sum(weight for _, weight in applicable))
        violations = [route for route in circulation.routes if route.distance_violation]
        distance_multiplier = min((route.distance_policy.over_limit_score_multiplier for route in violations), default=1.0)
        score = clamp_score(base_score * distance_multiplier)
        details = {"efficiency_score": efficiency, "separation_score": separation, "hallways": traffic, "penalty_multiplier": multiplier, "base_score": base_score, "distance_multiplier": distance_multiplier, "distance_violations": [{"rule_id": route.rule_id, "source_room_id": route.source_room_id, "destination_room_id": route.destination_room_id, "step_count": route.step_count, "preferred_max_grid_steps": route.distance_policy.preferred_max_grid_steps, "multiplier": route.distance_policy.over_limit_score_multiplier} for route in violations]} if context.mode is ExecutionMode.DEBUG else None
        return EvaluatorResult(self.key, EvaluationStatus.COMPLETED, score, details=details)
