from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..domain import (
    FloorPlan,
    Polygon,
    RoomId,
    RoomRelationSpec,
    RoomSpec,
    RoomType,
    RoomWidthAxis,
)
from .config import SeedSource
from .contracts import FloorPlanSolveRequest, RoomPlacementHint
from .exceptions import InvalidSpecificationError, MissingSeedError


def enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw).strip()


def normalize_enum(value: object) -> str:
    return enum_value(value).strip().lower()


def room_id_key(room_id: object) -> str:
    return str(room_id)


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_")
    return cleaned or "room"


@dataclass(frozen=True, slots=True)
class CoordinateScale:
    factor: int

    def nearest_length(self, value: float) -> int:
        return int(round(float(value) * self.factor))

    def minimum_length(self, value: float) -> int:
        return int(math.ceil(float(value) * self.factor - 1e-9))

    def maximum_length(self, value: float) -> int:
        return int(math.floor(float(value) * self.factor + 1e-9))

    def minimum_area(self, value: float) -> int:
        return int(math.ceil(float(value) * self.factor * self.factor - 1e-9))

    def maximum_area(self, value: float) -> int:
        return int(math.floor(float(value) * self.factor * self.factor + 1e-9))

    def to_domain(self, value: int) -> float:
        return float(value) / self.factor


@dataclass(frozen=True, slots=True)
class PreparedFloor:
    width: int
    length: int

    @property
    def area(self) -> int:
        return self.width * self.length


@dataclass(frozen=True, slots=True)
class PreparedRoom:
    id: RoomId
    id_key: str
    variable_name: str
    room_type: RoomType
    name: str
    min_width: int
    max_width: int
    min_length: int
    max_length: int
    max_short_side: int
    width_axis: RoomWidthAxis
    min_area: int
    max_area: int


@dataclass(frozen=True, slots=True)
class PreparedRelation:
    source_room_id: RoomId
    source_id_key: str
    target_room_ids: tuple[RoomId, ...]
    target_id_keys: tuple[str, ...]
    match_policy: str
    strength: str


@dataclass(frozen=True, slots=True)
class PreparedRoomSeed:
    room_id: RoomId
    room_id_key: str
    x: int
    y: int
    width: int | None
    length: int | None


@dataclass(frozen=True, slots=True)
class PreparedSeed:
    source: SeedSource
    rooms: dict[str, PreparedRoomSeed]


@dataclass(frozen=True, slots=True)
class PreparedProblem:
    floor: PreparedFloor
    rooms: tuple[PreparedRoom, ...]
    relations: tuple[PreparedRelation, ...]
    scale: CoordinateScale
    seed: PreparedSeed | None

    @property
    def rooms_by_id(self) -> dict[str, PreparedRoom]:
        return {room.id_key: room for room in self.rooms}


def _positive_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidSpecificationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise InvalidSpecificationError(f"{field_name} must be greater than zero")
    return number


def _non_negative_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidSpecificationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise InvalidSpecificationError(f"{field_name} cannot be negative")
    return number


def _prepare_rooms(
    room_specs: Iterable[RoomSpec],
    floor: PreparedFloor,
    scale: CoordinateScale,
) -> tuple[PreparedRoom, ...]:
    prepared: list[PreparedRoom] = []
    seen_ids: set[str] = set()

    for index, room in enumerate(room_specs):
        room_id = room.id
        id_key = room_id_key(room_id)
        if not id_key:
            raise InvalidSpecificationError("Room identifiers cannot be empty")
        if id_key in seen_ids:
            raise InvalidSpecificationError(f"Duplicate room id: {id_key}")
        seen_ids.add(id_key)

        size = room.size
        min_width_value = _positive_float(
            size.min_width, f"rooms[{id_key}].size.min_width"
        )
        max_short_side_value = _positive_float(
            size.max_width, f"rooms[{id_key}].size.max_width"
        )
        width_axis = getattr(
            size,
            "width_axis",
            RoomWidthAxis.ANY,
        )

        if not isinstance(width_axis, RoomWidthAxis):
            raise InvalidSpecificationError(
                f"rooms[{id_key}].size.width_axis must be a RoomWidthAxis enum member"
            )
        min_width = scale.minimum_length(min_width_value)
        min_length = min_width
        max_width = floor.width
        max_length = floor.length
        max_short_side = scale.maximum_length(max_short_side_value)

        if min_width > max_short_side:
            raise InvalidSpecificationError(
                f"Room '{id_key}' has an invalid width range"
            )
        if min_width > floor.width or min_length > floor.length:
            raise InvalidSpecificationError(
                f"Room '{id_key}' minimum width does not fit inside the floor"
            )

        min_area_value = _non_negative_float(
            size.min_area, f"rooms[{id_key}].size.min_area"
        )
        max_area_value = _non_negative_float(
            size.max_area, f"rooms[{id_key}].size.max_area"
        )

        dimension_min_area = min_width * min_length

        if width_axis is RoomWidthAxis.X:
            dimension_max_area = min(max_width, max_short_side) * max_length
        elif width_axis is RoomWidthAxis.Y:
            dimension_max_area = max_width * min(max_length, max_short_side)
        else:
            dimension_max_area = max(
                min(max_width, max_short_side) * max_length,
                max_width * min(max_length, max_short_side),
            )
        requested_min_area = (
            scale.minimum_area(min_area_value)
            if min_area_value > 0
            else dimension_min_area
        )
        requested_max_area = (
            scale.maximum_area(max_area_value)
            if max_area_value > 0
            else dimension_max_area
        )
        min_area = max(dimension_min_area, requested_min_area)
        max_area = min(dimension_max_area, requested_max_area, floor.area)

        if min_area > max_area:
            raise InvalidSpecificationError(
                f"Room '{id_key}' has incompatible dimension and area ranges"
            )

        room_type = room.room_type
        if not isinstance(room_type, RoomType):
            raise InvalidSpecificationError(
                f"rooms[{id_key}].room_type must be a RoomType enum member"
            )
        prepared.append(
            PreparedRoom(
                id=room_id,
                id_key=id_key,
                variable_name=f"r{index}_{_safe_name(id_key)}",
                room_type=room_type,
                name=str(room.name),
                min_width=min_width,
                max_width=max_width,
                min_length=min_length,
                max_length=max_length,
                max_short_side=max_short_side,
                width_axis=width_axis,
                min_area=min_area,
                max_area=max_area,
            )
        )

    if not prepared:
        raise InvalidSpecificationError("At least one room must be specified")
    return tuple(prepared)


def _prepare_relations(
    relation_specs: Iterable[RoomRelationSpec],
    rooms_by_id: dict[str, PreparedRoom],
) -> tuple[PreparedRelation, ...]:
    prepared: list[PreparedRelation] = []

    for index, relation in enumerate(relation_specs):
        source_room_id = relation.source_room_id
        source_key = room_id_key(source_room_id)
        if source_key not in rooms_by_id:
            raise InvalidSpecificationError(
                f"Relation {index} references unknown source room '{source_key}'"
            )

        targets: list[RoomId] = []
        target_keys: list[str] = []
        seen_targets: set[str] = set()
        for target_id in tuple(relation.target_room_ids):
            target_key = room_id_key(target_id)
            if target_key == source_key:
                raise InvalidSpecificationError(
                    f"Relation {index} cannot relate room '{source_key}' to itself"
                )
            if target_key not in rooms_by_id:
                raise InvalidSpecificationError(
                    f"Relation {index} references unknown target room '{target_key}'"
                )
            if target_key in seen_targets:
                continue
            seen_targets.add(target_key)
            targets.append(target_id)
            target_keys.append(target_key)

        if not target_keys:
            raise InvalidSpecificationError(
                f"Relation {index} must contain at least one target room"
            )

        match_policy = normalize_enum(relation.match_policy)
        strength = normalize_enum(relation.strength)
        if match_policy not in {"and", "or"}:
            raise InvalidSpecificationError(
                f"Relation {index} has unsupported match policy '{match_policy}'"
            )
        if strength not in {"hard", "soft"}:
            raise InvalidSpecificationError(
                f"Relation {index} has unsupported strength '{strength}'"
            )

        prepared.append(
            PreparedRelation(
                source_room_id=source_room_id,
                source_id_key=source_key,
                target_room_ids=tuple(targets),
                target_id_keys=tuple(target_keys),
                match_policy=match_policy,
                strength=strength,
            )
        )

    return tuple(prepared)


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _prepare_candidate_seed(
    hints: tuple[RoomPlacementHint, ...],
    rooms_by_id: dict[str, PreparedRoom],
    floor: PreparedFloor,
    scale: CoordinateScale,
) -> PreparedSeed | None:
    seeds: dict[str, PreparedRoomSeed] = {}

    for hint in hints:
        key = room_id_key(hint.room_id)
        room = rooms_by_id.get(key)
        if room is None:
            raise InvalidSpecificationError(
                f"Candidate hint references unknown room '{key}'"
            )
        if key in seeds:
            raise InvalidSpecificationError(
                f"Multiple candidate hints were supplied for room '{key}'"
            )

        width = (
            _clamp(scale.nearest_length(hint.width), room.min_width, room.max_width)
            if hint.width is not None
            else None
        )
        length = (
            _clamp(scale.nearest_length(hint.length), room.min_length, room.max_length)
            if hint.length is not None
            else None
        )
        bound_width = width if width is not None else room.min_width
        bound_length = length if length is not None else room.min_length
        x = _clamp(scale.nearest_length(hint.x), 0, floor.width - bound_width)
        y = _clamp(scale.nearest_length(hint.y), 0, floor.length - bound_length)

        seeds[key] = PreparedRoomSeed(
            room_id=room.id,
            room_id_key=key,
            x=x,
            y=y,
            width=width,
            length=length,
        )

    if not seeds:
        return None
    return PreparedSeed(source=SeedSource.CANDIDATE_HINTS, rooms=seeds)


def _polygon_bounds(boundary: Polygon) -> tuple[float, float, float, float]:
    points = tuple(boundary.points)
    if len(points) < 4:
        raise InvalidSpecificationError(
            "Existing floor-plan room boundaries must contain at least four points"
        )
    xs = [float(point.x) for point in points]
    ys = [float(point.y) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _prepare_existing_floor_plan_seed(
    floor_plan: FloorPlan,
    rooms_by_id: dict[str, PreparedRoom],
    floor: PreparedFloor,
    scale: CoordinateScale,
) -> PreparedSeed | None:
    seeds: dict[str, PreparedRoomSeed] = {}

    for floor_plan_room in tuple(floor_plan.rooms):
        key = room_id_key(floor_plan_room.id)
        room = rooms_by_id.get(key)
        if room is None:
            continue

        min_x, min_y, max_x, max_y = _polygon_bounds(floor_plan_room.boundary)
        width_value = max_x - min_x
        length_value = max_y - min_y
        if width_value <= 0 or length_value <= 0:
            raise InvalidSpecificationError(
                f"Existing room '{key}' has an empty boundary"
            )

        width = _clamp(
            scale.nearest_length(width_value), room.min_width, room.max_width
        )
        length = _clamp(
            scale.nearest_length(length_value), room.min_length, room.max_length
        )
        x = _clamp(scale.nearest_length(min_x), 0, floor.width - width)
        y = _clamp(scale.nearest_length(min_y), 0, floor.length - length)

        seeds[key] = PreparedRoomSeed(
            room_id=room.id,
            room_id_key=key,
            x=x,
            y=y,
            width=width,
            length=length,
        )

    if not seeds:
        return None
    return PreparedSeed(source=SeedSource.EXISTING_FLOOR_PLAN, rooms=seeds)


def _prepare_seed(
    request: FloorPlanSolveRequest,
    rooms_by_id: dict[str, PreparedRoom],
    floor: PreparedFloor,
    scale: CoordinateScale,
) -> PreparedSeed | None:
    policy = request.profile.seed

    if policy.source is SeedSource.NONE:
        return None

    if policy.source is SeedSource.CANDIDATE_HINTS:
        seed = _prepare_candidate_seed(
            request.candidate_hints, rooms_by_id, floor, scale
        )
    elif policy.source is SeedSource.EXISTING_FLOOR_PLAN:
        if request.existing_floor_plan is None:
            seed = None
        else:
            seed = _prepare_existing_floor_plan_seed(
                request.existing_floor_plan, rooms_by_id, floor, scale
            )
    else:  # pragma: no cover - protected by the enum
        raise InvalidSpecificationError(f"Unsupported seed source: {policy.source}")

    if seed is None and policy.require_source:
        raise MissingSeedError(
            f"Profile '{request.profile.name}' requires {policy.source.value} seed data"
        )
    return seed


def prepare_problem(request: FloorPlanSolveRequest) -> PreparedProblem:
    spec = request.specification
    scale = CoordinateScale(request.profile.preparation.coordinate_scale)

    floor_spec = spec.floor
    floor_width = _positive_float(floor_spec.width, "floor.width")
    floor_length = _positive_float(floor_spec.length, "floor.length")
    floor = PreparedFloor(
        width=scale.nearest_length(floor_width),
        length=scale.nearest_length(floor_length),
    )
    if floor.width < 1 or floor.length < 1:
        raise InvalidSpecificationError(
            "Scaled floor dimensions must both be at least one solver unit"
        )

    rooms = _prepare_rooms(tuple(spec.rooms), floor, scale)
    rooms_by_id = {room.id_key: room for room in rooms}
    relations = _prepare_relations(tuple(spec.room_relations), rooms_by_id)
    seed = _prepare_seed(request, rooms_by_id, floor, scale)

    return PreparedProblem(
        floor=floor,
        rooms=rooms,
        relations=relations,
        scale=scale,
        seed=seed,
    )
