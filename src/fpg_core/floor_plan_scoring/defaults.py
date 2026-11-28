from __future__ import annotations

from ..domain import RoomType
from ..domain.room_size_preferences import (
    DEFAULT_ROOM_SIZE_MAX_RATIO,
    DEFAULT_ROOM_SIZE_PAIRS,
    DEFAULT_ROOM_SIZE_SPREADS,
)
from .config import (
    EvaluatorRule,
    FloorPlanScoringConfig,
    ScoringGroupRule,
    ScoringProfile,
)
from .evaluators import (
    BEDROOM_QUALITY_KEY,
    ENCLOSED_VOIDS_KEY,
    GEOMETRY_INTEGRITY_KEY,
    INWARD_RECESS_KEY,
    LIVING_ROOM_BALANCE_KEY,
    ROOM_RELATIONSHIP_QUALITY_KEY,
    ROOM_SIZE_CONSISTENCY_KEY,
    BedroomQualityEvaluator,
    BedroomQualitySettings,
    EnclosedVoidsEvaluator,
    EnclosedVoidsSettings,
    GeometryIntegrityEvaluator,
    GeometryIntegritySettings,
    InwardRecessEvaluator,
    InwardRecessSettings,
    LivingRoomBalanceEvaluator,
    LivingRoomBalanceSettings,
    RoomAreaAggregation,
    RoomClusteringRule,
    RoomProximityRule,
    RoomRelationshipQualityEvaluator,
    RoomRelationshipQualitySettings,
    RoomSizeConsistencyEvaluator,
    RoomSizeConsistencySettings,
    RoomSizeRelationRule,
    RoomTypeConsistencyRule,
)
from .registry import EvaluatorRegistry
from .types import CRITICAL_GROUP, FUNCTIONAL_GROUP

DEFAULT_GEOMETRY_TOLERANCE = 1e-6


def create_default_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        (
            GeometryIntegrityEvaluator(),
            EnclosedVoidsEvaluator(),
            InwardRecessEvaluator(),
            LivingRoomBalanceEvaluator(),
            BedroomQualityEvaluator(),
            RoomSizeConsistencyEvaluator(),
            RoomRelationshipQualityEvaluator(),
        )
    )


DEFAULT_FLOOR_PLAN_SCORING_CONFIG = FloorPlanScoringConfig(
    groups=(
        ScoringGroupRule(CRITICAL_GROUP, order=10, weight=1.0),
        ScoringGroupRule(FUNCTIONAL_GROUP, order=20, weight=1.0),
    ),
    evaluators=(
        EvaluatorRule(
            GEOMETRY_INTEGRITY_KEY,
            CRITICAL_GROUP,
            GeometryIntegritySettings(DEFAULT_GEOMETRY_TOLERANCE),
            order=10,
            minimum_score=100.0,
        ),
        EvaluatorRule(
            ENCLOSED_VOIDS_KEY,
            CRITICAL_GROUP,
            EnclosedVoidsSettings(DEFAULT_GEOMETRY_TOLERANCE),
            order=30,
            minimum_score=100.0,
        ),
        EvaluatorRule(
            INWARD_RECESS_KEY,
            CRITICAL_GROUP,
            InwardRecessSettings(),
            order=40,
            minimum_score=100.0,
        ),
        EvaluatorRule(
            ROOM_SIZE_CONSISTENCY_KEY,
            FUNCTIONAL_GROUP,
            RoomSizeConsistencySettings(
                relation_rules=tuple(
                    RoomSizeRelationRule(
                        reference_type=reference,
                        compared_type=compared,
                        max_ratio=DEFAULT_ROOM_SIZE_MAX_RATIO,
                        reference_aggregation=RoomAreaAggregation.MIN,
                        compared_aggregation=RoomAreaAggregation.MAX,
                    )
                    for compared, reference in DEFAULT_ROOM_SIZE_PAIRS
                ),
                consistency_rules=tuple(
                    RoomTypeConsistencyRule(
                        room_type=room_type, maximum_spread_ratio=spread
                    )
                    for room_type, spread in DEFAULT_ROOM_SIZE_SPREADS
                ),
                default_full_penalty_ratio_delta=0.50,
            ),
            order=10,
            weight=2.0,
        ),
        EvaluatorRule(
            ROOM_RELATIONSHIP_QUALITY_KEY,
            FUNCTIONAL_GROUP,
            RoomRelationshipQualitySettings(
                proximity_rules=(
                    RoomProximityRule(
                        rule_id="kitchen_dining",
                        source_type=RoomType.KITCHEN,
                        target_type=RoomType.DINING_ROOM,
                        preferred_maximum_distance=5,
                        zero_score_distance=30,
                    ),
                    RoomProximityRule(
                        rule_id="living_dining",
                        source_type=RoomType.LIVING_ROOM,
                        target_type=RoomType.DINING_ROOM,
                        preferred_maximum_distance=5,
                        zero_score_distance=30,
                    ),
                ),
                clustering_rules=(
                    RoomClusteringRule(
                        rule_id="communal",
                        room_types=(
                            RoomType.LIVING_ROOM,
                            RoomType.DINING_ROOM,
                            RoomType.KITCHEN,
                        ),
                        preferred_maximum_distance=60,
                        zero_score_distance=120,
                        weight=0.5,
                    ),
                    RoomClusteringRule(
                        rule_id="bedrooms",
                        room_types=(RoomType.BEDROOM,),
                        preferred_maximum_distance=50,
                        zero_score_distance=100,
                    ),
                ),
            ),
            order=20,
        ),
        EvaluatorRule(
            LIVING_ROOM_BALANCE_KEY,
            FUNCTIONAL_GROUP,
            LivingRoomBalanceSettings(maximum_excess_ratio=2.0),
            order=30,
        ),
        EvaluatorRule(
            BEDROOM_QUALITY_KEY,
            FUNCTIONAL_GROUP,
            BedroomQualitySettings(
                area_compliance_weight=3.0,
                consistency_weight=1.0,
                full_spread_penalty_ratio=0.5,
                maximum_spread_penalty=40.0,
            ),
            order=40,
        ),
    ),
)


# Compatibility constant retained for existing consumers.
DEFAULT_SCORING_PROFILE = DEFAULT_FLOOR_PLAN_SCORING_CONFIG


def create_default_config() -> FloorPlanScoringConfig:
    return DEFAULT_FLOOR_PLAN_SCORING_CONFIG


def create_default_profile() -> ScoringProfile:
    """Compatibility alias for create_default_config()."""

    return DEFAULT_FLOOR_PLAN_SCORING_CONFIG
