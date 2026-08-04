from __future__ import annotations

import math
import re
from collections import Counter

from ..domain import ConstraintStrength, MatchPolicy, RoomType
from .config import PreprocessingConfig, canonical_aspect_ratio
from .context import (
    NormalizedRequest,
    NormalizedRoom,
    PreparedReferenceData,
    PreparedRoomRelationReference,
    PreparedRoomSizeReference,
)
from .contracts import (
    NormalizationRecord,
    PreprocessingReferenceData,
    PreprocessingRequest,
    RoomDecision,
)
from .exceptions import (
    NormalizationError,
    PreprocessingErrorCode,
    ReferenceDataError,
)


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value)).strip()


def _normalize_size(value: object) -> str:
    return re.sub(r"[-\s]+", "_", str(value).strip().lower())


def _reference_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ReferenceDataError(f"{field} must be numeric")
    if not isinstance(value, (int, float, str)):
        raise ReferenceDataError(f"{field} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ReferenceDataError(f"{field} must be numeric") from exc


def _parse_aspect_ratio(value: float | str, config: PreprocessingConfig) -> float:
    def invalid(message: str) -> NormalizationError:
        return NormalizationError(
            message,
            code=PreprocessingErrorCode.INVALID_ASPECT_RATIO,
            details={
                "field": "aspect_ratio",
                "supported": [rule.label for rule in config.supported_aspect_ratios],
            },
        )

    if isinstance(value, bool):
        raise invalid("aspect_ratio must be numeric or an H:W string")
    if isinstance(value, (int, float)):
        ratio = float(value)
    elif isinstance(value, str):
        parts = value.strip().split(":")
        if len(parts) != 2:
            raise invalid("aspect_ratio must use the H:W form")
        try:
            length, width = (float(part.strip()) for part in parts)
        except ValueError as exc:
            raise invalid("aspect_ratio H:W parts must be numeric") from exc
        if width == 0:
            raise invalid("aspect_ratio width part cannot be zero")
        ratio = length / width
    else:
        raise invalid("aspect_ratio must be numeric or an H:W string")
    if not math.isfinite(ratio) or ratio <= 0:
        raise invalid("aspect_ratio must be finite and greater than zero")
    canonical = canonical_aspect_ratio(ratio, config.supported_aspect_ratios)
    if canonical is None:
        raise NormalizationError(
            "aspect_ratio is not supported",
            code=PreprocessingErrorCode.INVALID_ASPECT_RATIO,
            details={
                "field": "aspect_ratio",
                "supported": [rule.label for rule in config.supported_aspect_ratios],
            },
        )
    return canonical


def _floor_project_unit_limit(
    field_name: str,
    value: object,
    *,
    collect_details: bool,
    records: list[NormalizationRecord],
) -> tuple[float, int]:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise NormalizationError(f"{field_name} must be numeric, not boolean")
    try:
        raw = float(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(raw) or raw <= 0:
        raise NormalizationError(f"{field_name} must be positive and finite")
    normalized = math.floor(raw)
    if normalized <= 0:
        raise NormalizationError(
            f"{field_name} becomes non-positive after whole-unit normalization"
        )
    if collect_details and not math.isclose(
        raw, normalized, rel_tol=0.0, abs_tol=1e-12
    ):
        records.append(
            NormalizationRecord(
                field=field_name,
                original=str(raw),
                normalized=str(normalized),
            )
        )
    return raw, normalized


def normalize_request(
    request: PreprocessingRequest,
    policy: PreprocessingConfig,
    *,
    collect_details: bool,
) -> NormalizedRequest:
    ratio = _parse_aspect_ratio(request.aspect_ratio, policy)
    records: list[NormalizationRecord] = []
    decisions: list[RoomDecision] = []
    defaults: list[str] = []
    raw_max_width, max_width = _floor_project_unit_limit(
        "floor_limits.max_width",
        request.floor_limits.max_width,
        collect_details=collect_details,
        records=records,
    )
    raw_max_length, max_length = _floor_project_unit_limit(
        "floor_limits.max_length",
        request.floor_limits.max_length,
        collect_details=collect_details,
        records=records,
    )

    supplied_ids = {
        room.id.strip()
        for room in request.rooms
        if isinstance(room.id, str) and room.id.strip()
    }
    generated_counts: Counter[RoomType] = Counter()
    used_ids: set[str] = set()
    rooms: list[NormalizedRoom] = []

    for index, room in enumerate(request.rooms):
        if not isinstance(room.room_type, RoomType):
            raise NormalizationError(
                f"rooms[{index}].room_type must be a RoomType enum member"
            )
        room_type = room.room_type

        room_id = room.id.strip() if isinstance(room.id, str) else ""
        if not room_id:
            while True:
                generated_counts[room_type] += 1
                room_id = f"{room_type.value}_{generated_counts[room_type]}"
                if room_id not in supplied_ids and room_id not in used_ids:
                    break
            if collect_details:
                defaults.append(f"generated room id '{room_id}'")

        name = room.name.strip() if isinstance(room.name, str) else ""
        if not name:
            name = room_id.replace("_", " ").title()
            if collect_details:
                defaults.append(f"generated room name '{name}' for '{room_id}'")

        requested_size = None
        if room.requested_size is not None:
            requested_size = _normalize_size(room.requested_size)
            if not requested_size:
                requested_size = None
            elif collect_details and str(room.requested_size).strip() != requested_size:
                records.append(
                    NormalizationRecord(
                        "requested_size", str(room.requested_size), requested_size
                    )
                )

        rooms.append(
            NormalizedRoom(
                id=room_id,
                room_type=room_type,
                name=name,
                requested_size=requested_size,
                request_index=index,
            )
        )
        used_ids.add(room_id)

    return NormalizedRequest(
        raw_max_width=raw_max_width,
        raw_max_length=raw_max_length,
        max_width=max_width,
        max_length=max_length,
        aspect_ratio=ratio,
        rooms=tuple(rooms),
        normalizations=tuple(records),
        room_decisions=tuple(decisions),
        applied_defaults=tuple(defaults),
    )


def _normalize_match_policy(value: MatchPolicy | str) -> MatchPolicy:
    raw = _enum_text(value).lower()
    try:
        return MatchPolicy(raw)
    except ValueError as exc:
        raise ReferenceDataError(f"Unsupported relation match policy '{raw}'") from exc


def _normalize_strength(value: ConstraintStrength | str) -> ConstraintStrength:
    raw = _enum_text(value).lower()
    try:
        return ConstraintStrength(raw)
    except ValueError as exc:
        raise ReferenceDataError(f"Unsupported relation strength '{raw}'") from exc


def prepare_reference_data(
    reference_data: PreprocessingReferenceData,
) -> PreparedReferenceData:
    sizes = tuple(
        PreparedRoomSizeReference(
            room_type=item.room_type,
            size=_normalize_size(item.size),
            min_width=_reference_float(item.min_width, "min_width"),
            max_width=_reference_float(item.max_width, "max_width"),
            min_area=_reference_float(item.min_area, "min_area"),
            max_area=_reference_float(item.max_area, "max_area"),
        )
        for item in reference_data.room_sizes
    )
    relations = tuple(
        PreparedRoomRelationReference(
            source_room_type=item.source_room_type,
            target_room_types=item.target_room_types,
            match_policy=_normalize_match_policy(item.match_policy),
            strength=_normalize_strength(item.strength),
            required=item.required,
        )
        for item in reference_data.room_relations
    )
    return PreparedReferenceData(room_sizes=sizes, room_relations=relations)
