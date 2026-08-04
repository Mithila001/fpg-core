from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import replace

from ..domain import (
    CandidateSearchSpace,
    FloorSpec,
    RoomId,
    RoomRelationSpec,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
    RoomWidthAxis,
)
from .config import PreprocessingPolicy
from .context import (
    PreparedReferenceData,
    PreparedRoomSizeReference,
    PreprocessingContext,
    RuledRequest,
)
from .contracts import RelationDecision
from .exceptions import (
    FloorPreparationError,
    RelationPreparationError,
    RoomPreparationError,
)

_WIDTH_AXIS_BY_ROOM_TYPE: dict[RoomType, RoomWidthAxis] = {
    RoomType.GARAGE: RoomWidthAxis.X,
    RoomType.VERANDA: RoomWidthAxis.X,
}


def _room_size_spec(reference: PreparedRoomSizeReference) -> RoomSizeSpec:
    return RoomSizeSpec(
        min_width=reference.min_width,
        max_width=reference.max_width,
        min_area=reference.min_area,
        max_area=reference.max_area,
        width_axis=_WIDTH_AXIS_BY_ROOM_TYPE.get(
            reference.room_type,
            RoomWidthAxis.ANY,
        ),
    )


def _prepare_non_hallway_rooms(
    request: RuledRequest,
    reference_data: PreparedReferenceData,
    policy: PreprocessingPolicy,
) -> tuple[tuple[RoomSpec, ...], RuledRequest]:
    by_type_size = {
        (item.room_type, item.size): item for item in reference_data.room_sizes
    }
    prepared: list[RoomSpec] = []
    decisions = list(request.room_decisions)
    retained_ids: set[str] = set()
    for room in request.rooms:
        if room.room_type is RoomType.HALLWAY:
            retained_ids.add(room.id)
            continue
        size_label = room.requested_size or request.selected_room_size
        reference = by_type_size.get((room.room_type, size_label))
        if reference is None:
            raise RoomPreparationError(
                f"Room '{room.id}' ({room.room_type.value}) has no size "
                f"reference for '{size_label}'"
            )
        retained_ids.add(room.id)
        prepared.append(
            RoomSpec(
                id=RoomId(room.id),
                room_type=room.room_type,
                name=room.name,
                size=_room_size_spec(reference),
            )
        )
    retained_rooms = tuple(room for room in request.rooms if room.id in retained_ids)
    return tuple(prepared), replace(
        request, rooms=retained_rooms, room_decisions=tuple(decisions)
    )


def _select_floor(
    request: RuledRequest,
    rooms: tuple[RoomSpec, ...],
    policy: PreprocessingPolicy,
) -> tuple[FloorSpec, float, float]:
    hallway_count = sum(r.room_type is RoomType.HALLWAY for r in request.rooms)
    hallway_area = policy.hallway_area_buffer
    minimum = (
        sum(room.size.min_area for room in rooms)
        + hallway_count * hallway_area
        + policy.floor_area_buffer
    )
    maximum = (
        sum(room.size.max_area for room in rooms)
        + hallway_count * hallway_area
        + policy.floor_area_buffer
    )

    minimum_axis = max(
        [room.size.min_width for room in rooms]
        + ([policy.hallway_min_width] if hallway_count else [])
        + [float(policy.candidate_search_grid_spacing * 2), 1.0]
    )
    minimum_axis_units = math.ceil(minimum_axis)
    ratio = request.aspect_ratio
    tolerance = policy.max_aspect_residual_units

    best: tuple[tuple[float, float, float, int, int], int, int] | None = None
    for width in range(minimum_axis_units, request.max_width + 1):
        max_length_by_area = math.floor((maximum + 1e-9) / width)
        maximum_length = min(
            request.max_length,
            max_length_by_area,
            math.floor(width * ratio + tolerance + 1e-9),
        )
        minimum_length = max(
            minimum_axis_units,
            math.ceil(width * ratio - tolerance - 1e-9),
            math.ceil((minimum - 1e-9) / width),
        )
        if minimum_length > maximum_length:
            continue

        length = maximum_length
        area = width * length
        residual = abs(length - width * ratio)
        reduction = (request.max_width - width) + (request.max_length - length)
        ranking = (area, -residual, -reduction, width, length)
        if best is None or ranking > best[0]:
            best = (ranking, width, length)

    if best is None:
        raise FloorPreparationError(
            "No whole-project-unit floor satisfies the area, room-width, floor-limit, "
            "and aspect-ratio residual requirements."
        )

    _, width, length = best
    return FloorSpec(width=width, length=length), minimum, maximum



def _build_candidate_search_space(
    floor: FloorSpec,
    policy: PreprocessingPolicy,
) -> CandidateSearchSpace:
    floor_width = int(floor.width)
    floor_length = int(floor.length)
    spacing = policy.candidate_search_grid_spacing

    search_width = floor_width - (floor_width % spacing)
    search_length = floor_length - (floor_length % spacing)
    origin_x = (floor_width - search_width) / 2
    origin_y = (floor_length - search_length) / 2

    try:
        return CandidateSearchSpace(
            origin_x=origin_x,
            origin_y=origin_y,
            width=search_width,
            length=search_length,
            grid_spacing=spacing,
        )
    except (TypeError, ValueError) as exc:
        raise FloorPreparationError(
            "The selected floor cannot produce a valid centered Candidate Search "
            "space with the configured grid spacing."
        ) from exc

def _add_hallways(
    request: RuledRequest,
    non_hallways: tuple[RoomSpec, ...],
    floor: FloorSpec,
    policy: PreprocessingPolicy,
) -> tuple[RoomSpec, ...]:
    by_id = {str(room.id): room for room in non_hallways}
    hallway_min_area = policy.hallway_area_buffer
    result: list[RoomSpec] = []
    for room in request.rooms:
        if room.room_type is not RoomType.HALLWAY:
            result.append(by_id[room.id])
            continue
        result.append(
            RoomSpec(
                id=RoomId(room.id),
                room_type=RoomType.HALLWAY,
                name=room.name,
                size=RoomSizeSpec(
                    min_width=min(
                        policy.hallway_min_width,
                        hallway_min_area / policy.hallway_min_width,
                    ),
                    max_width=max(
                        policy.hallway_min_width,
                        hallway_min_area / policy.hallway_min_width,
                    ),
                    min_area=hallway_min_area,
                    max_area=floor.width * floor.length,
                    width_axis=RoomWidthAxis.ANY,
                ),
            )
        )
    return tuple(result)


def _prepare_relations(
    rooms: tuple[RoomSpec, ...],
    reference_data: PreparedReferenceData,
    *,
    collect_details: bool,
) -> tuple[tuple[RoomRelationSpec, ...], tuple[RelationDecision, ...]]:
    by_type: dict[RoomType, list[RoomSpec]] = defaultdict(list)
    for room in rooms:
        by_type[room.room_type].append(room)
    prepared: list[RoomRelationSpec] = []
    decisions: list[RelationDecision] = []

    for reference in reference_data.room_relations:
        source_type = reference.source_room_type
        sources = by_type.get(source_type, [])
        if not sources:
            if collect_details:
                decisions.append(
                    RelationDecision(
                        source_type,
                        "removed",
                        "source type is not present",
                    )
                )
            continue
        for source_index, source in enumerate(sources):
            targets: list[RoomSpec] = []
            missing_types: list[RoomType] = []
            for target_type in reference.target_room_types:
                matches = [r for r in by_type.get(target_type, []) if r.id != source.id]
                if (
                    source_type is RoomType.ATTACHED_BATHROOM
                    and target_type is RoomType.BEDROOM
                    and matches
                ):
                    matches = (
                        [matches[source_index]] if source_index < len(matches) else []
                    )
                if not matches:
                    missing_types.append(target_type)
                targets.extend(matches)
            if missing_types and reference.required:
                raise RelationPreparationError(
                    f"Relation for '{source.id}' has missing target type(s): "
                    + ", ".join(item.value for item in missing_types)
                )
            unique_targets: list[RoomSpec] = []
            seen: set[str] = set()
            for target in targets:
                if str(target.id) not in seen:
                    seen.add(str(target.id))
                    unique_targets.append(target)
            if not unique_targets:
                if collect_details:
                    decisions.append(
                        RelationDecision(
                            source_type,
                            "removed",
                            f"no targets remained for '{source.id}'",
                        )
                    )
                continue
            prepared.append(
                RoomRelationSpec(
                    source_room_id=source.id,
                    target_room_ids=tuple(target.id for target in unique_targets),
                    match_policy=reference.match_policy,
                    strength=reference.strength,
                )
            )
            if collect_details:
                decisions.append(
                    RelationDecision(
                        source_type,
                        "expanded",
                        f"{source.id} -> {', '.join(str(t.id) for t in unique_targets)}",
                    )
                )
    return tuple(prepared), tuple(decisions)


def build_preprocessing_context(
    request: RuledRequest,
    reference_data: PreparedReferenceData,
    policy: PreprocessingPolicy,
    *,
    collect_details: bool,
) -> PreprocessingContext:
    non_hallways, final_request = _prepare_non_hallway_rooms(
        request, reference_data, policy
    )
    floor, minimum, maximum = _select_floor(final_request, non_hallways, policy)
    rooms = _add_hallways(final_request, non_hallways, floor, policy)
    candidate_search_space = _build_candidate_search_space(floor, policy)
    relations, relation_decisions = _prepare_relations(
        rooms,
        reference_data,
        collect_details=collect_details,
    )
    return PreprocessingContext(
        request=final_request,
        reference_data=reference_data,
        rooms=rooms,
        floor=floor,
        relations=relations,
        relation_decisions=relation_decisions,
        minimum_required_area=minimum,
        maximum_target_area=maximum,
        candidate_search_space=candidate_search_space,
        hallway_room_count_range=policy.hallway_room_count_range,
    )
