from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import RoomType


@dataclass(frozen=True)
class NumericPolicy:
    """Numerical tolerances and grid settings used by the pipeline."""

    tolerance: float = 1e-6
    grid_size: float = 1.0


@dataclass(frozen=True)
class WallExtensionRule:
    room_type: RoomType
    max_distance: float


@dataclass(frozen=True)
class ExteriorStepPolicy:
    direction: str
    minimum_depth: float
    minimum_segment_length: float
    preferred_max_steps: int


@dataclass(frozen=True)
class WallExtensionConfig:
    rules: tuple[WallExtensionRule, ...] = (
        WallExtensionRule(RoomType.VERANDA, 40),
        WallExtensionRule(RoomType.LIVING_ROOM, 20),
        WallExtensionRule(RoomType.KITCHEN, 10),
        WallExtensionRule(RoomType.HALLWAY, 2),
        WallExtensionRule(RoomType.BEDROOM, 10),
    )
    exterior_steps: tuple[ExteriorStepPolicy, ...] = (
        ExteriorStepPolicy("left", 10, 10, 2),
        ExteriorStepPolicy("right", 10, 10, 2),
        ExteriorStepPolicy("back", 8, 8, 3),
        ExteriorStepPolicy("front", 5, 5, 4),
    )
    max_recess_ratio: float = 1.0
    max_recess_levels: int = 1
    min_pocket_area: float = 1.0
    min_contact_length: float = 5.0
    min_residual_edge: float = 5.0
    min_extension_width: float = 5.0
    min_extension_depth: float = 5.0
    hallway_min_extension_width: float = 2.0
    hallway_min_extension_depth: float = 1.0
    max_area_excess: float = 0.05
    max_width_excess: float = 0.05
    max_iterations: int = 20
    max_candidate_evaluations: int = 1000
    transformation_version: str = "wall_extension:v2"


@dataclass(frozen=True)
class PlaceholderRemovalConfig:
    pass


@dataclass(frozen=True)
class HallwayMergeConfig:
    minimum_shared_wall: float = 10.0


@dataclass(frozen=True)
class GridSnapConfig:
    grid_size: float | None = None


@dataclass(frozen=True)
class RectilinearSimplificationConfig:
    pass


@dataclass(frozen=True)
class ProcessorUse:
    """Configuration for one processor in the ordered pipeline."""

    processor_id: str
    config: object
    required: bool = False
    validate_after: bool = False


@dataclass(frozen=True)
class FloorPlanPostProcessingConfig:
    """Complete reusable configuration for floor-plan post-processing."""

    name: str
    processors: tuple[ProcessorUse, ...]
    numeric: NumericPolicy = field(default_factory=NumericPolicy)
    reject_existing_openings: bool = True


# Backward-compatible type name. New code should prefer
# ``FloorPlanPostProcessingConfig`` because this object is configuration, while
# named profiles are presets built from this configuration type.
PostProcessingProfile = FloorPlanPostProcessingConfig
