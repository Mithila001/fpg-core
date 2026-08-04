"""Package-wide configuration aggregation and cross-feature validation.

Feature-only settings remain in each feature's own ``config.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .candidate_scoring.config import ScoringConfig as CandidateScoringConfig
from .candidate_search.config import CandidateSearchConfig
from .domain import SetbackProfile, UsableLandConstraints, ValidationLimits
from .floor_plan_openings.profiles import OpeningGenerationProfile
from .floor_plan_post_processing.contracts import PostProcessingProfile
from .floor_plan_preprocessing.config import PreprocessingConfig
from .floor_plan_scoring.config import ScoringProfile as FloorPlanScoringConfig
from .floor_plan_solver.profiles import ProfileCatalog

__all__ = [
    "BuildableSpaceConfig",
    "CandidateSearchConfig",
    "FpgCoreConfig",
    "FpgCoreConfigError",
    "PreprocessingConfig",
    "validate_fpg_core_config",
]


class FpgCoreConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BuildableSpaceConfig:
    active_profile: SetbackProfile
    usable_land_constraints: UsableLandConstraints
    validation_limits: ValidationLimits


@dataclass(frozen=True, slots=True)
class FpgCoreConfig:
    schema_version: int
    project_units_per_meter: int
    buildable_space: BuildableSpaceConfig
    preprocessing: PreprocessingConfig
    candidate_search: CandidateSearchConfig
    candidate_scoring: CandidateScoringConfig
    floor_plan_solver: ProfileCatalog
    post_processing: PostProcessingProfile
    openings: OpeningGenerationProfile
    floor_plan_scoring: FloorPlanScoringConfig


def _finite_positive(label: str, value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
        raise FpgCoreConfigError(f"{label} must be positive and finite")


def _validate_preprocessing(config: PreprocessingConfig) -> None:
    rules = config.room_count_rules
    room_types = [rule.room_type for rule in rules]
    if len(room_types) != len(set(room_types)):
        raise FpgCoreConfigError("preprocessing room-count rules must be unique")
    for rule in rules:
        if rule.minimum < 0 or rule.maximum < rule.minimum:
            raise FpgCoreConfigError(
                f"invalid room-count rule for {rule.room_type.value}"
            )
    if not config.allowed_client_room_types:
        raise FpgCoreConfigError("at least one client room type must be configured")
    if not set(config.mandatory_room_types).issubset(set(room_types)):
        raise FpgCoreConfigError("mandatory room types require room-count rules")
    ratios = [rule.canonical_value for rule in config.supported_aspect_ratios]
    if not ratios or any(value <= 0 or not math.isfinite(value) for value in ratios):
        raise FpgCoreConfigError("aspect ratios must be positive and finite")
    if len(ratios) != len(set(ratios)):
        raise FpgCoreConfigError("aspect-ratio rules must be unambiguous")
    _finite_positive("hallway_area_buffer", config.hallway_area_buffer)
    _finite_positive("hallway_min_width", config.hallway_min_width)
    if (
        isinstance(config.max_aspect_residual_units, bool)
        or not math.isfinite(float(config.max_aspect_residual_units))
        or config.max_aspect_residual_units < 0
    ):
        raise FpgCoreConfigError(
            "max_aspect_residual_units must be finite and non-negative"
        )
    if config.floor_area_buffer < 0 or config.hallway_count < 0:
        raise FpgCoreConfigError("preprocessing buffers/counts are invalid")
    configured_sizes = {(item.room_type, item.size) for item in config.room_sizes}
    for item in config.room_sizes:
        values = (item.min_width, item.max_width, item.min_area, item.max_area)
        if any(value <= 0 or not math.isfinite(value) for value in values):
            raise FpgCoreConfigError("room-size values must be positive and finite")
        if item.min_width > item.max_width or item.min_area > item.max_area:
            raise FpgCoreConfigError("room-size ranges are invalid")
    for room_type in config.allowed_client_room_types:
        if (room_type, config.default_room_size) not in configured_sizes:
            raise FpgCoreConfigError(
                f"default room size missing for {room_type.value}"
            )


def validate_fpg_core_config(config: FpgCoreConfig) -> None:
    # Validation registries are imported only when validation runs. This keeps
    # configuration and geometry imports lightweight while preserving full
    # cross-feature validation at the application boundary.
    from .candidate_scoring.defaults import (
        create_default_registry as candidate_registry,
    )
    from .candidate_scoring.validation import validate_scoring_config
    from .floor_plan_openings.registry import (
        create_default_registry as opening_registry,
    )
    from .floor_plan_post_processing.profiles import (
        create_default_registry as post_processing_registry,
    )
    from .floor_plan_post_processing.validation import validate_profile
    from .floor_plan_scoring.defaults import (
        create_default_registry as scoring_registry,
    )
    from .floor_plan_solver.constraints.defaults import (
        build_default_registry as solver_registry,
    )

    if not isinstance(config, FpgCoreConfig):
        raise FpgCoreConfigError("config must be an FpgCoreConfig")
    if config.schema_version != 2:
        raise FpgCoreConfigError("unsupported schema_version")
    if config.project_units_per_meter <= 0:
        raise FpgCoreConfigError("project_units_per_meter must be positive")
    _validate_preprocessing(config.preprocessing)
    candidate_search = config.candidate_search
    if candidate_search.long_axis_node_count < 2:
        raise FpgCoreConfigError("candidate_search.long_axis_node_count must be at least 2")
    if candidate_search.max_grid_node_count < 4:
        raise FpgCoreConfigError("candidate_search.max_grid_node_count must be at least 4")
    if candidate_search.max_internal_sampling_attempts <= 0:
        raise FpgCoreConfigError(
            "candidate_search.max_internal_sampling_attempts must be positive"
        )
    buildable = config.buildable_space
    if (
        buildable.usable_land_constraints.minimum_width <= 0
        or buildable.usable_land_constraints.minimum_length <= 0
        or buildable.usable_land_constraints.search_resolution <= 0
        or buildable.usable_land_constraints.maximum_sweep_lines <= 0
    ):
        raise FpgCoreConfigError("usable-land constraints must be positive")
    limits = buildable.validation_limits
    if (
        limits.minimum_vertex_count < 4
        or limits.maximum_vertex_count < limits.minimum_vertex_count
        or limits.maximum_absolute_coordinate <= 0
    ):
        raise FpgCoreConfigError("buildable-space validation limits are inconsistent")
    validate_scoring_config(config.candidate_scoring, candidate_registry())
    solver = solver_registry()
    for profile in (
        config.floor_plan_solver.initial,
        config.floor_plan_solver.refinement_a,
        config.floor_plan_solver.refinement_b,
    ):
        solver.validate_profile(profile)
    validate_profile(config.post_processing)
    processor_registry = post_processing_registry()
    seen: set[str] = set()
    for use in config.post_processing.processors:
        processor = processor_registry.resolve(use.processor_id)
        if not isinstance(use.config, processor.config_type):
            raise FpgCoreConfigError(
                f"processor {use.processor_id} has invalid configuration"
            )
        if any(key not in seen for key in processor.prerequisites):
            raise FpgCoreConfigError(
                f"processor {use.processor_id} has unsatisfied prerequisites"
            )
        seen.add(use.processor_id)
    openings = opening_registry()
    for feature_id in config.openings.enabled_features:
        openings.resolve(feature_id)
    known_opening_constraints = {"shared_placement", "room_door_limits"}
    if not set(config.openings.enabled_constraints).issubset(
        known_opening_constraints
    ):
        raise FpgCoreConfigError("unknown opening constraint ID")
    scoring = scoring_registry()
    group_keys = {group.key for group in config.floor_plan_scoring.groups}
    evaluator_keys: set[object] = set()
    for rule in config.floor_plan_scoring.evaluators:
        if rule.group_key not in group_keys:
            raise FpgCoreConfigError("floor-plan evaluator references unknown group")
        if rule.key in evaluator_keys:
            raise FpgCoreConfigError("duplicate floor-plan evaluator")
        evaluator_keys.add(rule.key)
        scoring.get(rule.key)
