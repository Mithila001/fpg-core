from __future__ import annotations

from ..domain import LandSide, RoomType
from .config import (
    EvaluatorRule,
    ExteriorClearanceRule,
    ScoringConfig,
    ZoneSuitabilityConfig,
)
from .evaluators import (
    CIRCULATION_QUALITY_KEY,
    EXTERIOR_CLEARANCE_KEY,
    FUNCTIONAL_GROUP_PURITY_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    CirculationQualityEvaluator,
    ExteriorClearanceEvaluator,
    FunctionalGroupPurityEvaluator,
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
            CirculationQualityEvaluator(),
            FunctionalGroupPurityEvaluator(),
            SpatialDistributionEvaluator(),
        )
    )


def create_default_config(
    *,
    zone_suitability_config: ZoneSuitabilityConfig | None = None,
) -> ScoringConfig:
    """Create baseline scoring rules with optional caller-defined zone rules."""
    zone_config = zone_suitability_config or ZoneSuitabilityConfig()
    return ScoringConfig(
        evaluator_rules=(
            EvaluatorRule(
                key=ZONE_SUITABILITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=1.0,
                order=10,
                settings={"zone_config": zone_config},
            ),
            EvaluatorRule(
                key=EXTERIOR_CLEARANCE_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=1.0,
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
                key=CIRCULATION_QUALITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=1.0,
                order=30,
            ),
            EvaluatorRule(
                key=FUNCTIONAL_GROUP_PURITY_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=1.0,
                order=50,
            ),
            EvaluatorRule(
                key=SPATIAL_DISTRIBUTION_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=1.0,
                order=40,
            ),
        )
    )
