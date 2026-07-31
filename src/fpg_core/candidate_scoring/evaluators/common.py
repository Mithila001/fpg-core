from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from ...domain import RoomType
from ..context import ScoringContext
from ..exceptions import ScoringInputError

MappingKey = TypeVar("MappingKey")


@dataclass(frozen=True, slots=True)
class EvaluationPoint:
    """One evaluator-facing point with a unique scoring identity.

    Candidate Search may emit several hallway hints for one source room ID. In
    that case ``room_id`` is expanded to an evaluator-only ID such as
    ``hallway_1::hint:2``. This keeps graph nodes, metrics, and visualization
    records distinct without modifying the Candidate Search or pipeline data.
    """

    room_id: str
    room_type: RoomType
    name: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class EvaluationData:
    floor_width: float
    floor_length: float
    points: tuple[EvaluationPoint, ...]


@dataclass(frozen=True, slots=True)
class _ParsedCandidatePoint:
    """Candidate point before evaluator-only IDs are assigned."""

    source_room_id: str
    room_type: RoomType
    name: str
    x: float
    y: float
    explicit_hint_index: int | None


def build_evaluation_data(context: ScoringContext) -> EvaluationData:
    """Convert supported project/domain shapes into evaluator-friendly data.

    The adapter supports the planned typed structures as well as mapping-based
    fixtures. It intentionally lives outside individual evaluators so each
    evaluator sees one stable internal representation.

    Multiple points for one room ID are accepted only for hallway points. They
    receive unique evaluator-only IDs; the original candidate remains untouched.
    """

    specification = context.scoring_input.specification
    candidate = context.scoring_input.candidate
    floor_width, floor_length = _extract_floor_size(specification)
    room_metadata = _extract_room_metadata(specification)
    points = _extract_candidate_points(candidate, room_metadata)

    return EvaluationData(
        floor_width=floor_width,
        floor_length=floor_length,
        points=tuple(points),
    )


def setting_float(settings: Mapping[str, Any], key: str, default: float) -> float:
    value = settings.get(key, default)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Setting '{key}' must be finite.")
    return result


def setting_int(settings: Mapping[str, Any], key: str, default: int) -> int:
    value = int(settings.get(key, default))
    return value


def setting_mapping(
    settings: Mapping[str, Any], key: str, default: Mapping[MappingKey, Any]
) -> Mapping[MappingKey, Any]:
    value = settings.get(key, default)
    if not isinstance(value, Mapping):
        raise ValueError(f"Setting '{key}' must be a mapping.")
    return cast(Mapping[MappingKey, Any], value)


def require_room_type(value: Any, label: str) -> RoomType:
    if not isinstance(value, RoomType):
        raise ScoringInputError(f"{label} must be a RoomType enum member.")
    return value


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def distance(a: EvaluationPoint, b: EvaluationPoint) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _extract_floor_size(specification: Any) -> tuple[float, float]:
    floor = _get(specification, "floor")
    config = _get(specification, "config")

    width = _first_not_none(
        _get(floor, "width"),
        _get(specification, "floor_width"),
        _get(specification, "width"),
        _get(config, "floor_plan_width"),
    )
    length = _first_not_none(
        _get(floor, "length"),
        _get(specification, "floor_length"),
        _get(specification, "length"),
        _get(config, "floor_plan_length"),
    )

    if width is None or length is None:
        raise ValueError("Could not determine floor width and length from specification.")

    floor_width = float(width)
    floor_length = float(length)
    if not math.isfinite(floor_width) or floor_width <= 0:
        raise ValueError("Floor width must be a finite positive value.")
    if not math.isfinite(floor_length) or floor_length <= 0:
        raise ValueError("Floor length must be a finite positive value.")
    return floor_width, floor_length


def _extract_room_metadata(specification: Any) -> dict[str, tuple[RoomType, str]]:
    rooms = _get(specification, "rooms") or ()
    metadata: dict[str, tuple[RoomType, str]] = {}
    for index, room in enumerate(_iterable(rooms)):
        room_id = str(_first_not_none(_get(room, "id"), _get(room, "name"), index))
        name = str(_first_not_none(_get(room, "name"), room_id))
        raw_type = _first_not_none(_get(room, "room_type"), _get(room, "type"))
        if raw_type is None:
            continue
        room_type = require_room_type(raw_type, f"Room '{room_id}' room_type")
        metadata[room_id] = (room_type, name)
        metadata.setdefault(name, (room_type, name))
    return metadata


def _extract_candidate_points(
    candidate: Any,
    room_metadata: Mapping[str, tuple[RoomType, str]],
) -> list[EvaluationPoint]:
    raw_points = _first_not_none(
        _get(candidate, "candidate_points"),
        _get(candidate, "points"),
        _get(candidate, "positions"),
        candidate,
    )

    if isinstance(raw_points, Mapping):
        items: Iterable[tuple[Any, Any]] = raw_points.items()
    else:
        items = enumerate(_iterable(raw_points))

    parsed_points: list[_ParsedCandidatePoint] = []
    for fallback_key, value in items:
        source_room_id = str(
            _first_not_none(
                _get(value, "room_id"),
                _get(value, "id"),
                fallback_key,
            )
        )
        metadata = room_metadata.get(source_room_id)
        name = str(
            _first_not_none(
                _get(value, "name"),
                metadata[1] if metadata else None,
                source_room_id,
            )
        )
        raw_type = _first_not_none(
            _get(value, "room_type"),
            _get(value, "type"),
            metadata[0] if metadata else None,
        )
        if raw_type is None:
            raise ValueError(
                f"Candidate point '{source_room_id}' has no room type."
            )

        room_type = require_room_type(
            raw_type,
            f"Candidate point '{source_room_id}' room_type",
        )
        x, y = _extract_xy(value)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(
                f"Candidate point '{source_room_id}' has non-finite coordinates."
            )

        parsed_points.append(
            _ParsedCandidatePoint(
                source_room_id=source_room_id,
                room_type=room_type,
                name=name,
                x=x,
                y=y,
                explicit_hint_index=_extract_hint_index(value, source_room_id),
            )
        )

    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, point in enumerate(parsed_points):
        grouped_indices[point.source_room_id].append(index)

    evaluator_ids: list[str | None] = [None] * len(parsed_points)
    evaluator_names: list[str | None] = [None] * len(parsed_points)

    # Preserve existing IDs for every non-duplicated point. These IDs are also
    # reserved so generated hallway IDs cannot collide with an actual room ID.
    used_ids: set[str] = {
        room_id
        for room_id, indices in grouped_indices.items()
        if len(indices) == 1
    }

    for source_room_id, indices in grouped_indices.items():
        if len(indices) == 1:
            index = indices[0]
            evaluator_ids[index] = source_room_id
            evaluator_names[index] = parsed_points[index].name
            continue

        duplicate_points = [parsed_points[index] for index in indices]
        if any(point.room_type is not RoomType.HALLWAY for point in duplicate_points):
            raise ValueError(f"Candidate point '{source_room_id}' is duplicated.")

        hint_indices = _resolve_hallway_hint_indices(
            source_room_id,
            duplicate_points,
        )
        for point_index, hint_index in zip(indices, hint_indices, strict=True):
            point = parsed_points[point_index]
            evaluator_id = _unique_hallway_evaluator_id(
                source_room_id=source_room_id,
                hint_index=hint_index,
                used_ids=used_ids,
            )
            used_ids.add(evaluator_id)
            evaluator_ids[point_index] = evaluator_id
            evaluator_names[point_index] = f"{point.name} (hint {hint_index})"

    return [
        EvaluationPoint(
            room_id=_required_value(evaluator_ids[index]),
            room_type=point.room_type,
            name=_required_value(evaluator_names[index]),
            x=point.x,
            y=point.y,
        )
        for index, point in enumerate(parsed_points)
    ]


def _extract_hint_index(value: Any, room_id: str) -> int | None:
    raw_hint_index = _get(value, "hint_index")
    if raw_hint_index is None:
        return None
    if isinstance(raw_hint_index, bool) or not isinstance(raw_hint_index, int):
        raise ValueError(
            f"Candidate point '{room_id}' hint_index must be a positive integer."
        )
    if raw_hint_index <= 0:
        raise ValueError(
            f"Candidate point '{room_id}' hint_index must be a positive integer."
        )
    return raw_hint_index


def _resolve_hallway_hint_indices(
    room_id: str,
    points: Sequence[_ParsedCandidatePoint],
) -> tuple[int, ...]:
    explicit_indices = [
        point.explicit_hint_index
        for point in points
        if point.explicit_hint_index is not None
    ]
    if len(set(explicit_indices)) != len(explicit_indices):
        raise ValueError(
            f"Hallway candidate point '{room_id}' has duplicated hint_index values."
        )

    used_indices = set(explicit_indices)
    next_generated_index = 1
    resolved: list[int] = []

    for point in points:
        if point.explicit_hint_index is not None:
            resolved.append(point.explicit_hint_index)
            continue

        while next_generated_index in used_indices:
            next_generated_index += 1
        resolved.append(next_generated_index)
        used_indices.add(next_generated_index)
        next_generated_index += 1

    return tuple(resolved)


def _unique_hallway_evaluator_id(
    *,
    source_room_id: str,
    hint_index: int,
    used_ids: set[str],
) -> str:
    base_id = f"{source_room_id}::hint:{hint_index}"
    if base_id not in used_ids:
        return base_id

    collision_index = 2
    while True:
        candidate_id = f"{base_id}:{collision_index}"
        if candidate_id not in used_ids:
            return candidate_id
        collision_index += 1


def _required_value(value: str | None) -> str:
    if value is None:
        raise RuntimeError("Candidate scoring point identity was not assigned.")
    return value


def _extract_xy(value: Any) -> tuple[float, float]:
    position = _get(value, "position")
    if position is not None:
        return _extract_xy(position)

    x = _get(value, "x")
    y = _get(value, "y")
    if x is not None and y is not None:
        return float(x), float(y)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) >= 2:
            return float(value[0]), float(value[1])

    raise ValueError(
        f"Could not extract x/y coordinates from candidate value: {value!r}"
    )


def _get(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return value.values()
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return value
    raise ValueError(f"Expected an iterable value, received {type(value).__name__}.")
