from __future__ import annotations

import math
from collections import Counter

from ..domain import RoomType
from .config import (
    ExcessAttachedBathroomPolicy,
    PreprocessingPolicy,
    RoomRelationReference,
    RoomSizeReference,
)
from .context import NormalizedRequest, PreparedReferenceData, PreprocessingContext
from .contracts import (
    FloorLimits,
    PreparedGenerationInput,
    PreprocessingInput,
    PreprocessingRequest,
    RequestedRoom,
)
from .exceptions import (
    ContextValidationError,
    InputValidationError,
    OutputValidationError,
    PreprocessingErrorCode,
    ReferenceDataError,
)


def _finite_number(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise InputValidationError(f"{field} must be numeric")
    if not isinstance(value, (int, float, str)):
        raise InputValidationError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        suffix = " and greater than zero" if positive else ""
        raise InputValidationError(f"{field} must be finite{suffix}")
    return number


def _positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputValidationError(f"{field} must be an integer")
    if value < 1:
        raise InputValidationError(f"{field} must be at least 1")
    return value


def _validate_attached_bathroom_count(
    request: PreprocessingRequest,
    policy: PreprocessingPolicy,
) -> None:
    if policy.excess_attached_bathrooms is not ExcessAttachedBathroomPolicy.REJECT:
        return

    bedroom_count = sum(
        room.room_type is RoomType.BEDROOM for room in request.rooms
    )
    attached_bathroom_count = sum(
        room.room_type is RoomType.ATTACHED_BATHROOM
        for room in request.rooms
    )

    if attached_bathroom_count > bedroom_count:
        raise InputValidationError(
            f"Requested {attached_bathroom_count} attached bathroom(s), "
            f"but only {bedroom_count} bedroom(s) were provided. "
            "Each attached bathroom requires a unique bedroom.",
            code=PreprocessingErrorCode.ATTACHED_BATHROOM_COUNT_EXCEEDS_BEDROOMS,
            details={
                "bedroom_count": bedroom_count,
                "attached_bathroom_count": attached_bathroom_count,
            },
        )


def validate_input(value: PreprocessingInput) -> None:
    if not isinstance(value, PreprocessingInput):
        raise InputValidationError("input must be a PreprocessingInput")
    request = value.request
    if not isinstance(request, PreprocessingRequest):
        raise InputValidationError("request must be a PreprocessingRequest")
    if not isinstance(request.floor_limits, FloorLimits):
        raise InputValidationError("floor_limits must be a FloorLimits")
    _finite_number(request.floor_limits.max_width, "max_width", positive=True)
    _finite_number(request.floor_limits.max_length, "max_length", positive=True)
    if not request.rooms:
        raise InputValidationError("At least one requested room is required")

    for index, room in enumerate(request.rooms):
        if not isinstance(room, RequestedRoom):
            raise InputValidationError(f"rooms[{index}] must be a RequestedRoom")
        if room.id is not None and not isinstance(room.id, str):
            raise InputValidationError(f"rooms[{index}].id must be a string or None")
        if room.room_type not in value.config.allowed_client_room_types:
            raise InputValidationError(
                f"rooms[{index}].room_type cannot be supplied by the client",
                code=PreprocessingErrorCode.FORBIDDEN_ROOM_TYPE,
                details={
                    "field": f"rooms[{index}].room_type",
                    "room_type": room.room_type.value,
                },
            )

    counts = Counter(room.room_type for room in request.rooms)
    invalid_counts = [
        {
            "room_type": requirement.room_type.value,
            "minimum": requirement.minimum,
            "maximum": requirement.maximum,
            "actual": counts[requirement.room_type],
        }
        for requirement in value.config.client_room_count_rules
        if not requirement.minimum
        <= counts[requirement.room_type]
        <= requirement.maximum
    ]
    if invalid_counts:
        raise InputValidationError(
            "One or more room counts are outside the supported range.",
            code=PreprocessingErrorCode.INVALID_ROOM_COUNT,
            details={"room_counts": invalid_counts},
        )

    if not isinstance(value.config, PreprocessingPolicy):
        raise InputValidationError("config must be a PreprocessingConfig")
    for index, size_item in enumerate(value.reference_data.room_sizes):
        if not isinstance(size_item, RoomSizeReference):
            raise InputValidationError(
                f"room_sizes[{index}] must be a RoomSizeReference"
            )
    for index, relation_item in enumerate(value.reference_data.room_relations):
        if not isinstance(relation_item, RoomRelationReference):
            raise InputValidationError(
                f"room_relations[{index}] must be a RoomRelationReference"
            )
        if not isinstance(relation_item.required, bool):
            raise InputValidationError(
                f"room_relations[{index}].required must be a boolean"
            )
    validate_policy(value.policy)
    _validate_attached_bathroom_count(request, value.policy)


def validate_policy(policy: PreprocessingPolicy) -> None:
    if not isinstance(policy, PreprocessingPolicy):
        raise InputValidationError("policy must be a PreprocessingPolicy")
    minimum = _finite_number(
        policy.min_aspect_ratio,
        "min_aspect_ratio",
        positive=True,
    )
    maximum = _finite_number(
        policy.max_aspect_ratio,
        "max_aspect_ratio",
        positive=True,
    )
    if minimum > maximum:
        raise InputValidationError("min_aspect_ratio cannot exceed max_aspect_ratio")
    _finite_number(policy.floor_area_buffer, "floor_area_buffer")
    if policy.floor_area_buffer < 0:
        raise InputValidationError("floor_area_buffer cannot be negative")
    _finite_number(policy.hallway_area_buffer, "hallway_area_buffer", positive=True)
    _positive_integer(
        policy.max_hallway_room_count,
        "max_hallway_room_count",
    )
    _finite_number(policy.hallway_min_width, "hallway_min_width", positive=True)

    spacing = _positive_integer(
        policy.candidate_search_grid_spacing,
        "candidate_search_grid_spacing",
    )
    if spacing % 2 != 0:
        raise InputValidationError(
            "candidate_search_grid_spacing must be an even project-unit value"
        )

    _finite_number(
        policy.max_aspect_residual_units,
        "max_aspect_residual_units",
    )
    if policy.max_aspect_residual_units < 0:
        raise InputValidationError("max_aspect_residual_units cannot be negative")
    if not isinstance(policy.default_room_size, str) or not policy.default_room_size.strip():
        raise InputValidationError("default_room_size cannot be empty")


def validate_normalized_request(
    request: NormalizedRequest,
    policy: PreprocessingPolicy,
) -> None:
    if not policy.min_aspect_ratio <= request.aspect_ratio <= policy.max_aspect_ratio:
        raise InputValidationError(
            "aspect_ratio must be between "
            f"{policy.min_aspect_ratio} and {policy.max_aspect_ratio} inclusive"
        )
    ids = [room.id for room in request.rooms]
    duplicates = sorted({room_id for room_id in ids if ids.count(room_id) > 1})
    if duplicates:
        raise InputValidationError(
            "Duplicate room ID(s): " + ", ".join(duplicates),
            code=PreprocessingErrorCode.DUPLICATE_ROOM_ID,
            details={"room_ids": duplicates},
        )
    if any(not room.id.strip() for room in request.rooms):
        raise InputValidationError("Room IDs cannot be empty")


def validate_reference_data(reference_data: PreparedReferenceData) -> None:
    seen: set[tuple[RoomType, str]] = set()
    for index, item in enumerate(reference_data.room_sizes):
        key = (item.room_type, item.size)
        if not item.size:
            raise ReferenceDataError(f"room_sizes[{index}].size cannot be empty")
        if key in seen:
            raise ReferenceDataError(
                f"Duplicate room-size reference for {key[0].value}/{key[1]}"
            )
        seen.add(key)
        values = (
            item.min_width,
            item.max_width,
            item.min_area,
            item.max_area,
        )
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ReferenceDataError(
                f"Room-size reference {key[0].value}/{key[1]} must be positive and finite"
            )
        if item.min_width > item.max_width:
            raise ReferenceDataError(
                f"Invalid width range for {key[0].value}/{key[1]}"
            )
        if item.min_area > item.max_area:
            raise ReferenceDataError(
                f"Invalid area range for {key[0].value}/{key[1]}"
            )
        if item.max_area < item.min_width * item.min_width:
            raise ReferenceDataError(
                f"Maximum area is below minimum width for {key[0].value}/{key[1]}"
            )
    for index, relation in enumerate(reference_data.room_relations):
        if not relation.target_room_types:
            raise ReferenceDataError(
                f"room_relations[{index}] must contain at least one target type"
            )
        if len(set(relation.target_room_types)) != len(relation.target_room_types):
            raise ReferenceDataError(
                f"room_relations[{index}] contains duplicate target types"
            )


def validate_context(context: PreprocessingContext) -> None:
    if not context.rooms:
        raise ContextValidationError("Prepared context contains no rooms")
    floor_area = context.floor.width * context.floor.length
    if context.minimum_required_area > floor_area:
        raise ContextValidationError("Selected floor does not meet minimum required area")
    if floor_area > context.maximum_target_area + 1e-9:
        raise ContextValidationError("Selected floor exceeds maximum target area")

    floor_width = int(context.floor.width)
    floor_length = int(context.floor.length)
    grid = context.candidate_grid
    spacing = int(grid.grid_spacing)
    expected_width = floor_width - (floor_width % spacing)
    expected_length = floor_length - (floor_length % spacing)
    expected_origin_x = (floor_width - expected_width) / 2
    expected_origin_y = (floor_length - expected_length) / 2

    if int(grid.width) != expected_width or int(grid.length) != expected_length:
        raise ContextValidationError(
            "Candidate grid does not use direct divisible shrinking"
        )
    if not math.isclose(
        float(grid.origin_x),
        expected_origin_x,
        rel_tol=0.0,
        abs_tol=1e-9,
    ) or not math.isclose(
        float(grid.origin_y),
        expected_origin_y,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ContextValidationError(
            "Candidate grid is not centered inside the selected floor"
        )
    if float(grid.origin_x) < 0 or float(grid.origin_y) < 0:
        raise ContextValidationError("Candidate grid origin cannot be negative")
    if float(grid.max_x) > floor_width or float(grid.max_y) > floor_length:
        raise ContextValidationError(
            "Candidate grid extends outside the selected floor"
        )
    if grid.interior_node_count < 1:
        raise ContextValidationError(
            "Candidate grid must contain at least one non-edge hint-point node"
        )
    if grid.interior_node_count < len(context.rooms):
        raise ContextValidationError(
            "Candidate grid does not contain enough non-edge nodes for all "
            "prepared room identities"
        )

    hallway_count = sum(
        room.room_type is RoomType.HALLWAY for room in context.rooms
    )
    if hallway_count != context.hallway_room_count_range.maximum:
        raise ContextValidationError(
            "Prepared hallway room identities do not match the hallway range maximum"
        )


def validate_output(
    prepared: PreparedGenerationInput,
    policy: PreprocessingPolicy,
) -> None:
    if not isinstance(prepared, PreparedGenerationInput):
        raise OutputValidationError("Output must be a PreparedGenerationInput")
    specification = prepared.generation_spec

    if specification.floor.width <= 0 or specification.floor.length <= 0:
        raise OutputValidationError("Final floor dimensions must be positive")
    if not float(specification.floor.width).is_integer() or not float(
        specification.floor.length
    ).is_integer():
        raise OutputValidationError(
            "Final floor dimensions must use whole project units"
        )
    if not specification.rooms:
        raise OutputValidationError("Final specification must contain rooms")

    ids = [str(room.id) for room in specification.rooms]
    if len(ids) != len(set(ids)):
        raise OutputValidationError("Final room IDs must be unique")
    room_types = [room.room_type for room in specification.rooms]
    required_types = set(policy.mandatory_room_types)
    missing = required_types.difference(room_types)
    if missing:
        raise OutputValidationError(
            "Final specification is missing required room types: "
            + ", ".join(sorted(item.value for item in missing))
        )

    hallway_count = room_types.count(RoomType.HALLWAY)
    if hallway_count != policy.max_hallway_room_count:
        raise OutputValidationError(
            "Final specification must contain exactly max_hallway_room_count "
            "potential hallway rooms"
        )
    if prepared.hallway_room_count_range != policy.hallway_room_count_range:
        raise OutputValidationError(
            "Output hallway room-count range does not match preprocessing config"
        )
    if (
        prepared.candidate_grid.grid_spacing
        != policy.candidate_search_grid_spacing
    ):
        raise OutputValidationError(
            "Output Candidate Search spacing does not match preprocessing config"
        )

    known_ids = set(ids)
    for room in specification.rooms:
        size = room.size
        if (
            size.min_width <= 0
            or size.min_width > size.max_width
            or size.min_area <= 0
            or size.min_area > size.max_area
        ):
            raise OutputValidationError(f"Invalid size specification for '{room.id}'")
    for relation in specification.room_relations:
        if str(relation.source_room_id) not in known_ids:
            raise OutputValidationError("Relation has an unknown source room")
        if not relation.target_room_ids or any(
            str(target) not in known_ids for target in relation.target_room_ids
        ):
            raise OutputValidationError("Relation has an unknown or empty target")
