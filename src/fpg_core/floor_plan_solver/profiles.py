from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

from .config import PreparationConfig, SeedPolicy, SeedSource, SolverConfig
from .domain import RoomType
from .exceptions import InvalidProfileError


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class HardConstraintUse:
    key: str
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidProfileError("Hard constraint key cannot be empty")
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True, slots=True)
class SoftConstraintUse:
    key: str
    weight: int
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidProfileError("Soft constraint key cannot be empty")
        if self.weight <= 0:
            raise InvalidProfileError(
                f"Soft constraint '{self.key}' must have a positive weight"
            )
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    """Complete behavior configuration for one CP-SAT generation stage."""

    name: str
    hard_constraints: tuple[HardConstraintUse, ...]
    soft_constraints: tuple[SoftConstraintUse, ...]
    solver: SolverConfig = field(default_factory=SolverConfig)
    preparation: PreparationConfig = field(default_factory=PreparationConfig)
    seed: SeedPolicy = field(default_factory=SeedPolicy)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidProfileError("Profile name cannot be empty")
        self._validate_unique_keys(self.hard_constraints, "hard")
        self._validate_unique_keys(self.soft_constraints, "soft")

    @staticmethod
    def _validate_unique_keys(items: tuple[object, ...], category: str) -> None:
        keys = [getattr(item, "key") for item in items]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            joined = ", ".join(duplicates)
            raise InvalidProfileError(
                f"Profile contains duplicate {category} constraints: {joined}"
            )

    def without_constraints(self, *keys: str) -> GenerationProfile:
        removed = set(keys)
        return replace(
            self,
            hard_constraints=tuple(
                use for use in self.hard_constraints if use.key not in removed
            ),
            soft_constraints=tuple(
                use for use in self.soft_constraints if use.key not in removed
            ),
        )

    def with_hard_constraints(self, *uses: HardConstraintUse) -> GenerationProfile:
        remove_keys = {use.key for use in uses}
        current = tuple(
            use for use in self.hard_constraints if use.key not in remove_keys
        )
        return replace(self, hard_constraints=current + tuple(uses))

    def with_soft_constraints(self, *uses: SoftConstraintUse) -> GenerationProfile:
        remove_keys = {use.key for use in uses}
        current = tuple(
            use for use in self.soft_constraints if use.key not in remove_keys
        )
        return replace(self, soft_constraints=current + tuple(uses))


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
