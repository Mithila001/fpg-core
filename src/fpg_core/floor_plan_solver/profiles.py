from __future__ import annotations

from dataclasses import dataclass

from ..domain import RoomType
from .config import (
    FloorPlanSolverConfig,
    HardConstraintUse,
    PreparationConfig,
    SeedPolicy,
    SeedSource,
    SoftConstraintUse,
    SolverConfig,
)
from .exceptions import InvalidProfileError

# Backward-compatible name for callers that previously treated a profile as
# the complete solver configuration. New code should use FloorPlanSolverConfig.
GenerationProfile = FloorPlanSolverConfig


@dataclass(frozen=True, slots=True)
class DefaultProfileSettings:
    """Central tuning values used to construct the built-in profiles.

    These are starter values, not replacements for project calibration. Length
    values use the same unit as the shared generation specification.
    """

    coordinate_scale: int = 1
    minimum_coverage_ratio: float = 0.6
    minimum_adjacency_overlap: float = 10
    attached_bathroom_minimum_shared_wall: float = 10.0
    initial_max_time_seconds: float = 5.0
    refinement_max_time_seconds: float = 2.0
    refinement_position_tolerance: float = 10
    refinement_size_tolerance: float = 10
    hallway_efficiency_weight: int = 1
    hallway_area_penalty_multiplier: int = 1
    hallway_preferred_max_length: float | None = 40.0
    hallway_excess_length_penalty_multiplier: int = 5


@dataclass(frozen=True, slots=True)
class ProfileCatalog:
    initial: GenerationProfile
    refinement_a: GenerationProfile
    refinement_b: GenerationProfile

    def by_name(self, name: str) -> GenerationProfile:
        profiles = {
            self.initial.name: self.initial,
            self.refinement_a.name: self.refinement_a,
            self.refinement_b.name: self.refinement_b,
        }
        try:
            return profiles[name]
        except KeyError as exc:
            available = ", ".join(sorted(profiles))
            raise InvalidProfileError(
                f"Unknown profile '{name}'. Available profiles: {available}"
            ) from exc


def _default_hard_constraints(
    settings: DefaultProfileSettings,
) -> tuple[HardConstraintUse, ...]:
    return (
        HardConstraintUse(
            "aspect_ratio",
            {
                "min_ratio": 0.60,
                "max_ratio": 1.80,
                "hallway_room_types": (RoomType.HALLWAY,),
                "overrides": {
                    RoomType.GARAGE: {
                        "min_ratio": 0.45,
                        "max_ratio": 0.70,
                    },
                    RoomType.VERANDA: {
                        "min_ratio": 1.20,
                        "max_ratio": 3.50,
                    },
                },
            },
        ),
        HardConstraintUse(
            "room_relations",
            {"minimum_overlap": settings.minimum_adjacency_overlap},
        ),
        HardConstraintUse(
            "attached_bathroom_pairing",
            {
                "minimum_shared_wall": (settings.attached_bathroom_minimum_shared_wall),
                "attached_bathroom_room_types": (RoomType.ATTACHED_BATHROOM,),
                "bedroom_room_types": (RoomType.BEDROOM,),
            },
        ),
        HardConstraintUse(
            "minimum_coverage",
            {"ratio": settings.minimum_coverage_ratio},
        ),
        HardConstraintUse(
            "hallway_connectivity",
            {
                "minimum_overlap": settings.minimum_adjacency_overlap,
                "hallway_room_types": (RoomType.HALLWAY,),
                "anchor_room_types": (RoomType.LIVING_ROOM,),
            },
        ),
        HardConstraintUse(
            "hallway_dimensions",
            {
                "hallway_room_types": (RoomType.HALLWAY,),
                "minimum_width": 8,
                "maximum_width": 10,
            },
        ),
        HardConstraintUse(
            "front_anchor",
            {
                "anchor_room_types": (
                    RoomType.VERANDA,
                    RoomType.LIVING_ROOM,
                    RoomType.BEDROOM,
                    RoomType.GARAGE,
                ),
            },
        ),
        HardConstraintUse(
            "back_exposure",
            {
                "room_types": (
                    RoomType.HALLWAY,
                    RoomType.KITCHEN,
                ),
                "minimum_exposure": 10.0,
            },
        ),
        HardConstraintUse(
            "garage_placement",
            {
                "garage_room_types": (RoomType.GARAGE,),
            },
        ),
        HardConstraintUse(
            "boundary_placement",
            {
                "rules": (
                    {
                        "room_types": (RoomType.VERANDA,),
                        "side": "front",
                        "offset": 0.0,
                    },
                )
            },
        ),
    )


def _hallway_efficiency_use(settings: DefaultProfileSettings) -> SoftConstraintUse:
    return SoftConstraintUse(
        "hallway_efficiency",
        weight=settings.hallway_efficiency_weight,
        settings={
            "hallway_room_types": (RoomType.HALLWAY,),
            "area_penalty_multiplier": settings.hallway_area_penalty_multiplier,
            "preferred_max_length": settings.hallway_preferred_max_length,
            "excess_length_penalty_multiplier": (
                settings.hallway_excess_length_penalty_multiplier
            ),
        },
    )


def build_default_profiles(
    settings: DefaultProfileSettings | None = None,
) -> ProfileCatalog:
    cfg = settings or DefaultProfileSettings()
    preparation = PreparationConfig(coordinate_scale=cfg.coordinate_scale)
    hard = _default_hard_constraints(cfg)

    initial = GenerationProfile(
        name="initial_generation",
        hard_constraints=hard,
        soft_constraints=(
            SoftConstraintUse(
                "room_relations",
                weight=40,
                settings={"minimum_overlap": cfg.minimum_adjacency_overlap},
            ),
            SoftConstraintUse(
                "floor_cluster_position",
                weight=1,
                settings={
                    "horizontal_multiplier": 1,
                    "front_multiplier": 2,
                },
            ),
            SoftConstraintUse("dead_space", weight=3),
            _hallway_efficiency_use(cfg),
            SoftConstraintUse("bathroom_depth", weight=2),
            SoftConstraintUse(
                "kitchen_back_exposure",
                weight=10,
                settings={"minimum_exposure": 10.0},
            ),
        ),
        solver=SolverConfig(max_time_seconds=cfg.initial_max_time_seconds),
        preparation=preparation,
        seed=SeedPolicy(
            source=SeedSource.CANDIDATE_HINTS,
            require_source=False,
            apply_hints=True,
        ),
    )

    refinement_a = GenerationProfile(
        name="refinement_a",
        hard_constraints=hard,
        soft_constraints=(
            SoftConstraintUse(
                "room_relations",
                weight=50,
                settings={"minimum_overlap": cfg.minimum_adjacency_overlap},
            ),
            SoftConstraintUse(
                "seed_stability",
                weight=20,
                settings={"position_multiplier": 2, "size_multiplier": 1},
            ),
            SoftConstraintUse(
                "floor_cluster_position",
                weight=1,
                settings={
                    "horizontal_multiplier": 1,
                    "front_multiplier": 2,
                },
            ),
            SoftConstraintUse("dead_space", weight=4),
            _hallway_efficiency_use(cfg),
            SoftConstraintUse("bathroom_depth", weight=3),
            SoftConstraintUse(
                "kitchen_back_exposure",
                weight=10,
                settings={"minimum_exposure": 10.0},
            ),
        ),
        solver=SolverConfig(max_time_seconds=cfg.refinement_max_time_seconds),
        preparation=preparation,
        seed=SeedPolicy(
            source=SeedSource.EXISTING_FLOOR_PLAN,
            require_source=True,
            apply_hints=True,
            position_tolerance=cfg.refinement_position_tolerance,
            size_tolerance=cfg.refinement_size_tolerance,
        ),
    )

    refinement_b = GenerationProfile(
        name="refinement_b",
        hard_constraints=hard,
        soft_constraints=(
            SoftConstraintUse(
                "room_relations",
                weight=60,
                settings={"minimum_overlap": cfg.minimum_adjacency_overlap},
            ),
            SoftConstraintUse(
                "seed_stability",
                weight=35,
                settings={"position_multiplier": 2, "size_multiplier": 2},
            ),
            SoftConstraintUse("dead_space", weight=6),
            _hallway_efficiency_use(cfg),
            SoftConstraintUse("bathroom_depth", weight=4),
            SoftConstraintUse(
                "kitchen_back_exposure",
                weight=10,
                settings={"minimum_exposure": 10.0},
            ),
        ),
        solver=SolverConfig(max_time_seconds=cfg.refinement_max_time_seconds),
        preparation=preparation,
        seed=SeedPolicy(
            source=SeedSource.EXISTING_FLOOR_PLAN,
            require_source=True,
            apply_hints=True,
            position_tolerance=cfg.refinement_position_tolerance / 2,
            size_tolerance=cfg.refinement_size_tolerance / 2,
        ),
    )

    return ProfileCatalog(
        initial=initial,
        refinement_a=refinement_a,
        refinement_b=refinement_b,
    )


DEFAULT_PROFILES = build_default_profiles()
INITIAL_GENERATION_PROFILE = DEFAULT_PROFILES.initial
REFINEMENT_A_PROFILE = DEFAULT_PROFILES.refinement_a
REFINEMENT_B_PROFILE = DEFAULT_PROFILES.refinement_b
