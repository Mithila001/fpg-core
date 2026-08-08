from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any

from .exceptions import InvalidProfileError


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class HardConstraintUse:
    """Configuration for one enabled hard constraint."""

    key: str
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidProfileError("Hard constraint key cannot be empty")
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True, slots=True)
class SoftConstraintUse:
    """Configuration for one enabled soft constraint and its objective weight."""

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
class SolverConfig:
    """OR-Tools runtime settings for one solve."""

    max_time_seconds: float = 30.0
    num_search_workers: int = 0
    random_seed: int | None = None
    log_search_progress: bool = False
    relative_gap_limit: float | None = None
    cp_model_presolve: bool = True

    def __post_init__(self) -> None:
        if self.max_time_seconds <= 0:
            raise InvalidProfileError("max_time_seconds must be greater than zero")
        if self.num_search_workers < 0:
            raise InvalidProfileError("num_search_workers cannot be negative")
        if self.random_seed is not None and self.random_seed < 0:
            raise InvalidProfileError("random_seed cannot be negative")
        if self.relative_gap_limit is not None and self.relative_gap_limit < 0:
            raise InvalidProfileError("relative_gap_limit cannot be negative")


@dataclass(frozen=True, slots=True)
class PreparationConfig:
    """Conversion settings between project units and CP-SAT integer units."""

    coordinate_scale: int = 10

    def __post_init__(self) -> None:
        if self.coordinate_scale < 1:
            raise InvalidProfileError("coordinate_scale must be at least 1")


class SeedSource(str, Enum):
    NONE = "none"
    CANDIDATE_HINTS = "candidate_hints"
    EXISTING_FLOOR_PLAN = "existing_floor_plan"


@dataclass(frozen=True, slots=True)
class SeedPolicy:
    """Controls how candidate or existing-layout geometry is used as a seed.

    Tolerances are expressed in the same units used by FloorPlanGenerationSpec.
    A ``None`` tolerance leaves that dimension unbounded and uses only AddHint.
    A zero tolerance fixes the seeded value.
    """

    source: SeedSource = SeedSource.NONE
    require_source: bool = False
    apply_hints: bool = True
    position_tolerance: float | None = None
    size_tolerance: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("position_tolerance", self.position_tolerance),
            ("size_tolerance", self.size_tolerance),
        ):
            if value is not None and value < 0:
                raise InvalidProfileError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class FloorPlanSolverConfig:
    """Complete reusable configuration for one CP-SAT generation stage."""

    name: str
    hard_constraints: tuple[HardConstraintUse, ...]
    soft_constraints: tuple[SoftConstraintUse, ...]
    solver: SolverConfig = field(default_factory=SolverConfig)
    preparation: PreparationConfig = field(default_factory=PreparationConfig)
    seed: SeedPolicy = field(default_factory=SeedPolicy)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidProfileError("Configuration name cannot be empty")
        self._validate_unique_keys(self.hard_constraints, "hard")
        self._validate_unique_keys(self.soft_constraints, "soft")

    @staticmethod
    def _validate_unique_keys(
        items: tuple[HardConstraintUse | SoftConstraintUse, ...],
        category: str,
    ) -> None:
        keys = [item.key for item in items]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            joined = ", ".join(duplicates)
            raise InvalidProfileError(
                f"Configuration contains duplicate {category} constraints: {joined}"
            )

    def without_constraints(self, *keys: str) -> FloorPlanSolverConfig:
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

    def with_hard_constraints(
        self, *uses: HardConstraintUse
    ) -> FloorPlanSolverConfig:
        remove_keys = {use.key for use in uses}
        current = tuple(
            use for use in self.hard_constraints if use.key not in remove_keys
        )
        return replace(self, hard_constraints=current + tuple(uses))

    def with_soft_constraints(
        self, *uses: SoftConstraintUse
    ) -> FloorPlanSolverConfig:
        remove_keys = {use.key for use in uses}
        current = tuple(
            use for use in self.soft_constraints if use.key not in remove_keys
        )
        return replace(self, soft_constraints=current + tuple(uses))
