from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..types import RoomType
from .config import (
    ExcessAttachedBathroomPolicy,
    PreprocessingPolicy,
    RoomSizeSelectionStrategy,
)
from .context import NormalizedRequest, NormalizedRoom, RuledRequest
from .contracts import RoomDecision
from .exceptions import BusinessRuleError


def _next_available_id(base: str, used_ids: set[str]) -> str:
    index = 1
    while f"{base}_{index}" in used_ids:
        index += 1
    return f"{base}_{index}"


def _select_majority_size(
    rooms: tuple[NormalizedRoom, ...], policy: PreprocessingPolicy
) -> str:
    if policy.room_size_strategy is not RoomSizeSelectionStrategy.MAJORITY:
        raise BusinessRuleError(
            f"Unsupported room-size strategy '{policy.room_size_strategy}'"
        )
    excluded = set(policy.size_normalization_exclusions)
    counts = Counter(
        room.requested_size
        for room in rooms
        if room.room_type not in excluded and room.requested_size
    )
    if not counts:
        return policy.default_room_size.strip().lower()
    maximum = max(counts.values())
    tied = sorted(size for size, count in counts.items() if count == maximum)
    default = policy.default_room_size.strip().lower()
    return default if default in tied else tied[0]


def apply_business_rules(
    request: NormalizedRequest, policy: PreprocessingPolicy
) -> RuledRequest:
    decisions = list(request.room_decisions)
    defaults = list(request.applied_defaults)
    bedrooms = [r for r in request.rooms if r.room_type is RoomType.BEDROOM]
    attached_bathrooms = [
        room
        for room in request.rooms
        if room.room_type is RoomType.ATTACHED_BATHROOM
    ]

    if (
        len(attached_bathrooms) > len(bedrooms)
        and policy.excess_attached_bathrooms
        is ExcessAttachedBathroomPolicy.REJECT
    ):
        raise BusinessRuleError(
            f"Requested {len(attached_bathrooms)} attached bathroom(s), "
            f"but only {len(bedrooms)} bedroom(s) were provided. "
            "Each attached bathroom requires a unique bedroom."
        )

    sanitized = list(request.rooms)

    present_types = {room.room_type for room in sanitized}
    missing = [t for t in policy.mandatory_room_types if t not in present_types]
    if missing:
        raise BusinessRuleError(
            "Missing mandatory room type(s): "
            + ", ".join(room_type.value for room_type in missing)
        )

    used_ids = {room.id for room in sanitized}
    next_index = max((room.request_index for room in sanitized), default=-1) + 1
    for _ in range(policy.hallway_count):
        room_id = _next_available_id("hallway", used_ids)
        hallway = NormalizedRoom(
            room_id,
            RoomType.HALLWAY,
            room_id.replace("_", " ").title(),
            None,
            next_index,
        )
        next_index += 1
        used_ids.add(room_id)
        sanitized.append(hallway)
        decisions.append(
            RoomDecision(room_id, RoomType.HALLWAY, "derived", "hallway policy")
        )
        defaults.append(f"derived hallway '{room_id}'")

    selected_size = _select_majority_size(tuple(sanitized), policy)
    normalized_rooms = tuple(
        room
        if room.room_type in policy.size_normalization_exclusions
        else replace(room, requested_size=selected_size)
        for room in sanitized
    )
    return RuledRequest(
        max_width=request.max_width,
        max_length=request.max_length,
        aspect_ratio=request.aspect_ratio,
        rooms=normalized_rooms,
        selected_room_size=selected_size,
        normalizations=request.normalizations,
        room_decisions=tuple(decisions),
        applied_defaults=tuple(defaults),
    )
