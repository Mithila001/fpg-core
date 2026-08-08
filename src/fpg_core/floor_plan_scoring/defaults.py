from __future__ import annotations

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
    KITCHEN_DINING_KEY,
    LIVING_ROOM_BALANCE_KEY,
    REQUIRED_ADJACENCY_KEY,
    BedroomQualityEvaluator,
    BedroomQualitySettings,
    EnclosedVoidsEvaluator,
    EnclosedVoidsSettings,
    GeometryIntegrityEvaluator,
    GeometryIntegritySettings,
    InwardRecessEvaluator,
    InwardRecessSettings,
    KitchenDiningEvaluator,
    KitchenDiningSettings,
    LivingRoomBalanceEvaluator,
    LivingRoomBalanceSettings,
    RequiredAdjacencyEvaluator,
    RequiredAdjacencySettings,
)
from .registry import EvaluatorRegistry
from .types import CRITICAL_GROUP, FUNCTIONAL_GROUP

DEFAULT_GEOMETRY_TOLERANCE = 1e-6
DEFAULT_MINIMUM_SHARED_BOUNDARY = 10.0
DEFAULT_MAXIMUM_INWARD_RECESS = 20.0
DEFAULT_KITCHEN_DINING_MAXIMUM_DISTANCE = 2000.0


def create_default_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        (
            GeometryIntegrityEvaluator(),
            RequiredAdjacencyEvaluator(),
            EnclosedVoidsEvaluator(),
            InwardRecessEvaluator(),
            LivingRoomBalanceEvaluator(),
            BedroomQualityEvaluator(),
            KitchenDiningEvaluator(),
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
            REQUIRED_ADJACENCY_KEY,
            CRITICAL_GROUP,
            RequiredAdjacencySettings(
                DEFAULT_MINIMUM_SHARED_BOUNDARY,
                DEFAULT_GEOMETRY_TOLERANCE,
            ),
            order=20,
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
            InwardRecessSettings(
                DEFAULT_MAXIMUM_INWARD_RECESS,
                DEFAULT_GEOMETRY_TOLERANCE,
            ),
            order=40,
            minimum_score=100.0,
        ),
        EvaluatorRule(
            LIVING_ROOM_BALANCE_KEY,
            FUNCTIONAL_GROUP,
            LivingRoomBalanceSettings(maximum_excess_ratio=2.0),
            order=10,
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
            order=20,
        ),
        EvaluatorRule(
            KITCHEN_DINING_KEY,
            FUNCTIONAL_GROUP,
            KitchenDiningSettings(
                minimum_shared_boundary=DEFAULT_MINIMUM_SHARED_BOUNDARY,
                maximum_distance=DEFAULT_KITCHEN_DINING_MAXIMUM_DISTANCE,
                tolerance=DEFAULT_GEOMETRY_TOLERANCE,
            ),
            order=30,
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
