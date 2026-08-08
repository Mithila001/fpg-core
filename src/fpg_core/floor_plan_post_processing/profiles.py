from __future__ import annotations

from .config import (
    FloorPlanPostProcessingConfig,
    GridSnapConfig,
    HallwayMergeConfig,
    PlaceholderRemovalConfig,
    ProcessorUse,
    RectilinearSimplificationConfig,
    VerandaAdjustmentConfig,
    WallExtensionConfig,
)
from .processors import (
    GridSnapProcessor,
    HallwayMergeProcessor,
    RectilinearSimplificationProcessor,
    RemovePlaceholderRoomsProcessor,
    VerandaAdjustmentProcessor,
    WallExtensionProcessor,
)
from .registry import ProcessorRegistry

# A named, reusable configuration preset. The "PROFILE" name is retained because
# profiles are useful presets; the request itself exposes this value as ``config``.
INITIAL_GENERATION_PROFILE = FloorPlanPostProcessingConfig(
    name="initial_generation",
    processors=(
        ProcessorUse("veranda_adjustment", VerandaAdjustmentConfig()),
        ProcessorUse("wall_extension", WallExtensionConfig()),
        ProcessorUse(
            "remove_placeholder_rooms",
            PlaceholderRemovalConfig(),
            required=True,
            validate_after=True,
        ),
        ProcessorUse("hallway_merge", HallwayMergeConfig()),
        ProcessorUse("grid_snap", GridSnapConfig(), required=True, validate_after=True),
        ProcessorUse("rectilinear_simplification", RectilinearSimplificationConfig()),
    ),
)


def create_default_registry() -> ProcessorRegistry:
    return ProcessorRegistry(
        (
            VerandaAdjustmentProcessor(),
            WallExtensionProcessor(),
            RemovePlaceholderRoomsProcessor(),
            HallwayMergeProcessor(),
            GridSnapProcessor(),
            RectilinearSimplificationProcessor(),
        )
    )
