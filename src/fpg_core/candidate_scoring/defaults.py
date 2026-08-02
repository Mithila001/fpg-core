from __future__ import annotations

from ..domain import LandSide, RoomType
from .config import (
    EvaluatorRule,
    ExteriorClearanceRule,
    ScoringConfig,
    ZoneSuitabilityConfig,
)
from .evaluators import (
    EXTERIOR_CLEARANCE_KEY,
    SPATIAL_DISTRIBUTION_KEY,
    ZONE_SUITABILITY_KEY,
    ExteriorClearanceEvaluator,
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
                weight=20.0,
                order=10,
                settings={"zone_config": zone_config},
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
                key=SPATIAL_DISTRIBUTION_KEY,
                category=EvaluatorCategory.QUALITY,
                weight=25.0,
                order=40,
            ),
        )
    )
