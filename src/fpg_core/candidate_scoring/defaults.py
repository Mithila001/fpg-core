from __future__ import annotations

from ..domain import LandSide, RoomType
from .config import ExteriorClearanceRule, EvaluatorRule, ScoringConfig
from .evaluators import (
    EXTERIOR_CLEARANCE_KEY,
    RELATIONSHIP_QUALITY_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    ExteriorClearanceEvaluator,
    RelationshipQualityEvaluator,
    SpatialDistributionEvaluator,
    ZoneSuitabilityEvaluator,
)
from .registry import EvaluatorRegistry
from .types import EvaluatorCategory


def create_default_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        (
            ZoneSuitabilityEvaluator(),
            ExteriorClearanceEvaluator(),
            RelationshipQualityEvaluator(),
            SpatialDistributionEvaluator(),
        )
    )


def create_default_config() -> ScoringConfig:
    """Baseline configuration; tune categories, thresholds, and weights per use case."""
    return ScoringConfig(
        evaluator_rules=(
            EvaluatorRule(
                key=ZONE_SUITABILITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=20.0,
                order=10,
            ),
            EvaluatorRule(
                key=EXTERIOR_CLEARANCE_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=20.0,
                order=20,
                settings={
                    "rules": (
                        ExteriorClearanceRule(
                            room_types=(RoomType.VERANDA,),
                            required_clear_room_count=1,
                            clearance_width=20.0,
                            direction=LandSide.FRONT,
                        ),
                        ExteriorClearanceRule(
                            room_types=(RoomType.GARAGE,),
                            required_clear_room_count=1,
                            clearance_width=20.0,
                            direction=LandSide.FRONT,
                        ),
                        ExteriorClearanceRule(
                            room_types=(RoomType.KITCHEN, RoomType.HALLWAY),
                            required_clear_room_count=1,
                            clearance_width=20.0,
                            direction=LandSide.BACK,
                        ),
                    )
                },
            ),
            EvaluatorRule(
                key=RELATIONSHIP_QUALITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=35.0,
                order=30,
            ),
            EvaluatorRule(
                key=SPATIAL_DISTRIBUTION_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=25.0,
                order=40,
            ),
        )
    )
