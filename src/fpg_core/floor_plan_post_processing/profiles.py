from __future__ import annotations

from .config import (
    GridSnapConfig,
    HallwayMergeConfig,
    PlaceholderRemovalConfig,
    RectilinearSimplificationConfig,
    VerandaAdjustmentConfig,
    WallExtensionConfig,
)
from .contracts import PostProcessingProfile, ProcessorUse
from .processors import (
    GridSnapProcessor,
    HallwayMergeProcessor,
    RectilinearSimplificationProcessor,
    RemovePlaceholderRoomsProcessor,
    VerandaAdjustmentProcessor,
    WallExtensionProcessor,
)
from .registry import ProcessorRegistry

INITIAL_GENERATION_PROFILE = PostProcessingProfile(
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
