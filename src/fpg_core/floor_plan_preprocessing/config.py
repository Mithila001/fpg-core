from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..domain import ConstraintStrength, MatchPolicy, RoomType


class RoomSizeSelectionStrategy(str, Enum):
    MAJORITY = "majority"


class ExcessAttachedBathroomPolicy(str, Enum):
    REMOVE = "remove"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class RoomCountRule:
    room_type: RoomType
    minimum: int
    maximum: int
    client_selectable: bool = True


@dataclass(frozen=True, slots=True)
class AspectRatioRule:
    label: str
    canonical_value: float


@dataclass(frozen=True, slots=True)
class RoomSizeReference:
    room_type: RoomType
    size: str
    min_width: float
    max_width: float
    min_area: float
    max_area: float


@dataclass(frozen=True, slots=True)
class RoomRelationReference:
    source_room_type: RoomType
    target_room_types: tuple[RoomType, ...]
    match_policy: MatchPolicy | str
    strength: ConstraintStrength | str
    required: bool = True


@dataclass(frozen=True, slots=True)
class PreprocessingConfig:
    room_count_rules: tuple[RoomCountRule, ...]
    supported_aspect_ratios: tuple[AspectRatioRule, ...]
    room_sizes: tuple[RoomSizeReference, ...]
    room_relations: tuple[RoomRelationReference, ...]
    mandatory_room_types: tuple[RoomType, ...]
    floor_area_buffer: float
    hallway_area_buffer: float
    hallway_count: int
    hallway_min_width: float
    default_room_size: str
    min_aspect_ratio: float = 0.5
    max_aspect_ratio: float = 2.0
    room_size_strategy: RoomSizeSelectionStrategy = RoomSizeSelectionStrategy.MAJORITY
    size_normalization_exclusions: tuple[RoomType, ...] = (RoomType.HALLWAY,)
    excess_attached_bathrooms: ExcessAttachedBathroomPolicy = (
        ExcessAttachedBathroomPolicy.REJECT
    )

    @property
    def client_room_count_rules(self) -> tuple[RoomCountRule, ...]:
        return tuple(rule for rule in self.room_count_rules if rule.client_selectable)

    @property
    def allowed_client_room_types(self) -> frozenset[RoomType]:
        return frozenset(rule.room_type for rule in self.client_room_count_rules)


# Temporary source-compatibility name for callers while they move to the complete
# configuration contract.
PreprocessingPolicy = PreprocessingConfig


def canonical_aspect_ratio(
    value: float,
    rules: tuple[AspectRatioRule, ...],
    *,
    tolerance: float = 1e-6,
) -> float | None:
    for rule in rules:
        if abs(value - rule.canonical_value) <= tolerance:
            return rule.canonical_value
    return None
