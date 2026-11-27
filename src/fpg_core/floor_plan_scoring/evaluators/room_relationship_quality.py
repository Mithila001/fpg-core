from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import dist
from statistics import mean

from ...domain import ExecutionMode, RoomType
from ..context import ScoringContext
from ..exceptions import ScoringConfigurationError
from ..types import EvaluationStatus, EvaluatorKey, EvaluatorResult, ScoreMetric
from .base import FloorPlanEvaluator
from .common import clamp_score, require_non_negative, require_positive, typed_settings

ROOM_RELATIONSHIP_QUALITY_KEY = EvaluatorKey("room_relationship_quality")


@dataclass(frozen=True, slots=True, kw_only=True)
class _DistanceRule:
    rule_id: str
    preferred_maximum_distance: float
    zero_score_distance: float
    weight: float = 1.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ScoringConfigurationError("Relationship rule ID must be non-empty.")
        require_non_negative(
            self.preferred_maximum_distance, "Preferred maximum distance"
        )
        require_positive(self.zero_score_distance, "Zero-score distance")
        require_positive(self.weight, "Relationship rule weight")
        if self.zero_score_distance <= self.preferred_maximum_distance:
            raise ScoringConfigurationError(
                "Zero-score distance must exceed preferred maximum distance."
            )

    def score(self, distance: float) -> float:
        preferred = self.preferred_maximum_distance
        if distance <= preferred:
            return 100.0
        if distance >= self.zero_score_distance:
            return 0.0
        return clamp_score(
            100 * (1 - (distance - preferred) / (self.zero_score_distance - preferred))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RoomProximityRule(_DistanceRule):
    source_type: RoomType
    target_type: RoomType

    def __post_init__(self) -> None:
        _DistanceRule.__post_init__(self)
        if not all(
            isinstance(kind, RoomType) for kind in (self.source_type, self.target_type)
        ):
            raise ScoringConfigurationError(
                "Proximity rules require canonical RoomType values."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RoomClusteringRule(_DistanceRule):
    room_types: tuple[RoomType, ...]

    def __post_init__(self) -> None:
        _DistanceRule.__post_init__(self)
        if not self.room_types or not all(
            isinstance(kind, RoomType) for kind in self.room_types
        ):
            raise ScoringConfigurationError(
                "Clustering rules require at least one canonical RoomType."
            )


@dataclass(frozen=True, slots=True)
class RoomRelationshipQualitySettings:
    proximity_rules: tuple[RoomProximityRule, ...] = ()
    clustering_rules: tuple[RoomClusteringRule, ...] = ()

    def __post_init__(self) -> None:
        for rules, expected in (
            (self.proximity_rules, RoomProximityRule),
            (self.clustering_rules, RoomClusteringRule),
        ):
            if not all(isinstance(rule, expected) for rule in rules):
                raise ScoringConfigurationError(f"Expected {expected.__name__} rules.")
        ids = [
            rule.rule_id.strip()
            for rule in (*self.proximity_rules, *self.clustering_rules)
        ]
        if len(ids) != len(set(ids)):
            raise ScoringConfigurationError("Relationship rule IDs must be unique.")


class RoomRelationshipQualityEvaluator(FloorPlanEvaluator):
    @property
    def key(self) -> EvaluatorKey:
        return ROOM_RELATIONSHIP_QUALITY_KEY

    @property
    def settings_type(self) -> type[object]:
        return RoomRelationshipQualitySettings

    def evaluate(self, context: ScoringContext, settings: object) -> EvaluatorResult:
        config = typed_settings(
            settings, RoomRelationshipQualitySettings, str(self.key)
        )
        debug = context.mode is ExecutionMode.DEBUG
        weighted_scores = []
        details = []
        for rule in config.proximity_rules:
            if not rule.enabled:
                continue
            targets = [
                (room.room_id, room.polygon.boundary)
                for room in context.rooms
                if room.room_type is rule.target_type
            ]
            scores = []
            pairs = []
            for source in context.rooms:
                if source.room_type is not rule.source_type:
                    continue
                boundary = source.polygon.boundary
                nearest = min(
                    (
                        (boundary.distance(target), target_id)
                        for target_id, target in targets
                        if source.room_id != target_id
                    ),
                    default=None,
                )
                if nearest is None:
                    continue
                distance, target_id = nearest
                score = rule.score(distance)
                scores.append(score)
                if debug:
                    pairs.append(
                        {
                            "source_id": source.room_id,
                            "target_id": target_id,
                            "distance": distance,
                            "score": score,
                        }
                    )
            if scores:
                score = mean(scores)
                weighted_scores.append((score, rule.weight))
                if debug:
                    details.append(
                        {
                            "kind": "proximity",
                            "rule": rule,
                            "score": score,
                            "pairs": pairs,
                        }
                    )

        for rule in config.clustering_rules:
            if not rule.enabled:
                continue
            rooms = [
                room for room in context.rooms if room.room_type in rule.room_types
            ]
            if len(rooms) < 2 or not set(rule.room_types) <= {
                room.room_type for room in rooms
            }:
                continue
            distance, first_id, second_id = max(
                (dist(first.centroid, second.centroid), first.room_id, second.room_id)
                for first, second in combinations(rooms, 2)
            )
            score = rule.score(distance)
            weighted_scores.append((score, rule.weight))
            if debug:
                details.append(
                    {
                        "kind": "clustering",
                        "rule": rule,
                        "score": score,
                        "distance": distance,
                        "room_ids": [room.room_id for room in rooms],
                        "pair": (first_id, second_id),
                    }
                )

        if not weighted_scores:
            return EvaluatorResult(self.key, EvaluationStatus.NOT_APPLICABLE, None)
        # Scale first so even the largest finite configured weights can be averaged.
        scale = max(weight for _, weight in weighted_scores)
        score = sum(score * (weight / scale) for score, weight in weighted_scores)
        score /= sum(weight / scale for _, weight in weighted_scores)
        return EvaluatorResult(
            self.key,
            EvaluationStatus.COMPLETED,
            clamp_score(score),
            metrics=(ScoreMetric("applicable_rule_count", len(weighted_scores)),)
            if debug
            else (),
            visualization_payload={"rules": details} if debug else None,
        )
