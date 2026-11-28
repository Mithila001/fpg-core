from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain import ExecutionMode
from ..context import ScoringContext
from ..footprints import boundary_distance, proximity_score
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult
from .base import CandidateEvaluator
from .common import clamp_score, setting_float

CIRCULATION_QUALITY_KEY = EvaluatorKey("circulation_quality")

DEFAULT_PROXIMITY = {
    "attached_bathroom:bedroom": (2, 20),
    "living_room:veranda": (0, 30),
    "dining_room:kitchen": (5, 30),
    "kitchen:living_room": (10, 50),
    "dining_room:living_room": (5, 35),
    "bathroom:bedroom": (10, 50),
    "bedroom:living_room": (10, 60),
    "bathroom:living_room": (10, 50),
    "garage:kitchen": (15, 60),
    "garage:living_room": (5, 40),
    "garage:veranda": (5, 35),
}


def validate_proximity_preferences(preferences):
    if preferences is None:
        return
    if not isinstance(preferences, Mapping):
        raise TypeError("proximity_preferences must be a mapping")
    from ...domain import RoomType

    for key, preference in preferences.items():
        parts = key.split(":") if isinstance(key, str) else []
        if len(parts) != 2 or parts != sorted(parts):
            raise ValueError(
                "Proximity keys must be sorted room-type pairs separated by ':'."
            )
        for part in parts:
            RoomType(part)
        if isinstance(preference, Mapping):
            preferred, zero = (
                preference["preferred_distance"],
                preference["zero_score_distance"],
            )
        else:
            preferred, zero = preference
        proximity_score(0, float(preferred), float(zero))


class CirculationQualityEvaluator(CandidateEvaluator):
    """Score final route efficiency and separation of hallway traffic."""

    @property
    def key(self) -> EvaluatorKey:
        return CIRCULATION_QUALITY_KEY

    def evaluate(
        self, context: ScoringContext, settings: Mapping[str, Any]
    ) -> EvaluatorResult:
        for key in (
            "efficiency_weight",
            "proximity_weight",
            "traffic_separation_weight",
            "single_hallway_penalty_multiplier",
            "multiple_hallway_penalty_multiplier",
        ):
            if key in settings and (
                isinstance(settings[key], bool)
                or not isinstance(settings[key], (int, float))
            ):
                raise ValueError(f"Setting '{key}' must be numeric.")
        proximity_weight = setting_float(settings, "proximity_weight", 0.5)
        efficiency_weight = setting_float(settings, "efficiency_weight", 0.3)
        separation_weight = setting_float(settings, "traffic_separation_weight", 0.2)
        single = setting_float(settings, "single_hallway_penalty_multiplier", 0.5)
        multiple = setting_float(settings, "multiple_hallway_penalty_multiplier", 1.0)
        if (
            min(
                proximity_weight, efficiency_weight, separation_weight, single, multiple
            )
            < 0
            or proximity_weight + efficiency_weight + separation_weight <= 0
            or max(single, multiple) > 1
        ):
            raise ValueError(
                "Invalid circulation quality weights or penalty multipliers."
            )
        circulation = context.scoring_input.final_circulation
        if circulation is None:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        preferences = settings.get("proximity_preferences", DEFAULT_PROXIMITY)
        if not isinstance(preferences, Mapping):
            raise ValueError("proximity_preferences must be a mapping")
        footprints = {
            f.point.source_room_id: f
            for f in context.derived["footprints"].values()
            if f.point.room_type.value != "hallway"
        }
        relationships = {}
        for route in circulation.routes:
            key = tuple(sorted((route.source_room_id, route.destination_room_id)))
            if key in relationships:
                relationships[key]["weight"] = max(
                    relationships[key]["weight"], route.importance_weight
                )
                continue
            if any(room_id not in footprints for room_id in key):
                continue
            a, b = (footprints[room_id] for room_id in key)
            type_key = ":".join(
                sorted((a.point.room_type.value, b.point.room_type.value))
            )
            preference = preferences.get(type_key)
            if preference is None:
                continue
            if isinstance(preference, Mapping):
                preferred, zero = (
                    preference["preferred_distance"],
                    preference["zero_score_distance"],
                )
            else:
                preferred, zero = preference
            distance = boundary_distance(a, b)
            relationships[key] = {
                "room_ids": key,
                "distance": distance,
                "score": proximity_score(distance, float(preferred), float(zero)),
                "weight": route.importance_weight,
                "preferred_distance": preferred,
                "zero_score_distance": zero,
            }
        proximity_total = sum(item["weight"] for item in relationships.values())
        proximity = (
            sum(item["score"] * item["weight"] for item in relationships.values())
            / proximity_total
            if proximity_total
            else None
        )
        routes = []
        for route in circulation.routes:
            costs = route.costs
            cost = costs.movement_cost + costs.perimeter_bias_cost + costs.turn_cost
            score = (
                clamp_score(100 * route.manhattan_reference_cost / cost)
                if cost > 0
                else (100.0 if route.manhattan_reference_cost == 0 else 0.0)
            )
            routes.append((score, route.importance_weight))
        route_weight = sum(weight for _, weight in routes)
        efficiency = (
            sum(score * weight for score, weight in routes) / route_weight
            if route_weight
            else None
        )
        traffic: list[dict[str, Any]] = []
        multiplier = single if len(circulation.hallways) == 1 else multiple
        for hallway in circulation.hallways:
            public, private = (
                hallway.public_importance_weight,
                hallway.private_importance_weight,
            )
            total = public + private
            if total > 0:
                ratio = 2 * min(public, private) / total
                traffic.append(
                    {
                        "point_key": hallway.point_key,
                        "public_weight": public,
                        "private_weight": private,
                        "mixing_ratio": ratio,
                        "penalty": ratio * multiplier,
                        "weight": total,
                    }
                )
        total_traffic = sum(item["weight"] for item in traffic)
        separation = (
            clamp_score(
                100
                * (
                    1
                    - sum(item["penalty"] * item["weight"] for item in traffic)
                    / total_traffic
                )
            )
            if total_traffic
            else None
        )
        parts = [
            (proximity, proximity_weight),
            (efficiency, efficiency_weight),
            (separation, separation_weight),
        ]
        applicable = [
            (score, weight)
            for score, weight in parts
            if score is not None and weight > 0
        ]
        if not applicable:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        base_score = clamp_score(
            sum(value * weight for value, weight in applicable)
            / sum(weight for _, weight in applicable)
        )
        score = base_score
        details = (
            {
                "efficiency_score": efficiency,
                "proximity_score": proximity,
                "relationships": list(relationships.values()),
                "separation_score": separation,
                "hallways": traffic,
                "penalty_multiplier": multiplier,
                "base_score": base_score,
            }
            if context.mode is ExecutionMode.DEBUG
            else None
        )
        return EvaluatorResult(
            self.key, EvaluationStatus.COMPLETED, score, details=details
        )
