from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from shapely.errors import ShapelyError
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from ..domain import ExecutionMode, FloorPlan, FloorPlanGenerationSpec, RoomType
from .exceptions import ScoringInputError


@dataclass(frozen=True, slots=True)
class NormalizedRoomSize:
    min_width: float
    max_width: float
    min_area: float
    max_area: float


@dataclass(frozen=True, slots=True)
class NormalizedRoomSpec:
    room_id: str
    room_type: RoomType
    name: str
    size: NormalizedRoomSize


@dataclass(frozen=True, slots=True)
class NormalizedRelation:
    source_room_id: str
    target_room_ids: tuple[str, ...]
    match_policy: str
    strength: str


@dataclass(frozen=True, slots=True)
class NormalizedRoom:
    room_id: str
    room_type: RoomType
    name: str
    points: tuple[tuple[float, float], ...]
    polygon: Polygon
    area: float
    centroid: tuple[float, float]


@dataclass(frozen=True, slots=True)
class ScoringContext:
    mode: ExecutionMode
    floor_width: float
    floor_length: float
    floor_points: tuple[tuple[float, float], ...]
    floor_polygon: Polygon
    rooms: tuple[NormalizedRoom, ...]
    room_specs: tuple[NormalizedRoomSpec, ...]
    relations: tuple[NormalizedRelation, ...]
    rooms_by_id: Mapping[str, NormalizedRoom]
    specs_by_id: Mapping[str, NormalizedRoomSpec]
    identity_redirects: Mapping[str, str]
    room_union: BaseGeometry | None
    geometry_build_error: str | None
    shared_boundary_lengths: Mapping[tuple[str, str], float]


class ScoringContextFactory:
    """Validate shared structures and build one immutable evaluator context."""

    def build(
        self,
        floor_plan: FloorPlan,
        specification: FloorPlanGenerationSpec,
        *,
        mode: ExecutionMode,
    ) -> ScoringContext:
        if floor_plan is None:
            raise ScoringInputError("floor_plan cannot be None.")
        if specification is None:
            raise ScoringInputError("specification cannot be None.")

        floor_spec = _required_attr(specification, "floor", "specification")
        floor_width = _positive_number(
            _required_attr(floor_spec, "width", "floor"), "floor.width"
        )
        floor_length = _positive_number(
            _required_attr(floor_spec, "length", "floor"), "floor.length"
        )

        room_specs = _normalize_specs(
            _required_attr(specification, "rooms", "specification")
        )
        specs_by_id = _unique_by_id(room_specs, "specification room")
        relations = _normalize_relations(
            _required_attr(specification, "room_relations", "specification"),
            specs_by_id,
        )

        floor_boundary = _required_attr(floor_plan, "boundary", "floor_plan")
        floor_points = _normalize_points(
            _required_attr(floor_boundary, "points", "floor_plan.boundary"),
            "floor_plan.boundary",
        )
        floor_polygon = Polygon(floor_points)

        rooms = _normalize_rooms(
            _required_attr(floor_plan, "rooms", "floor_plan"),
            specs_by_id,
        )
        physical_rooms_by_id = _unique_by_id(rooms, "floor-plan room")
        identity_redirects = _normalize_identity_redirects(
            getattr(floor_plan, "identity_redirects", {}),
            specs_by_id,
            physical_rooms_by_id,
        )
        rooms_by_id = dict(physical_rooms_by_id)
        rooms_by_id.update(
            {
                source_id: physical_rooms_by_id[target_id]
                for source_id, target_id in identity_redirects.items()
            }
        )

        missing_rooms = [
            spec.room_id
            for spec in room_specs
            if spec.room_id not in rooms_by_id
        ]
        if missing_rooms:
            raise ScoringInputError(
                "Rooms are missing from the floor plan: "
                + ", ".join(sorted(missing_rooms))
            )

        geometry_error: str | None = None
        room_union: BaseGeometry | None = None
        shared_lengths: dict[tuple[str, str], float] = {}
        try:
            room_union = unary_union([room.polygon for room in rooms])
            for index, room_a in enumerate(rooms):
                for room_b in rooms[index + 1 :]:
                    shared = room_a.polygon.boundary.intersection(
                        room_b.polygon.boundary
                    )
                    key = _pair_key(room_a.room_id, room_b.room_id)
                    shared_lengths[key] = float(shared.length)
        except ShapelyError as exc:
            geometry_error = str(exc)

        return ScoringContext(
            mode=mode,
            floor_width=floor_width,
            floor_length=floor_length,
            floor_points=floor_points,
            floor_polygon=floor_polygon,
            rooms=rooms,
            room_specs=room_specs,
            relations=relations,
            rooms_by_id=MappingProxyType(dict(rooms_by_id)),
            specs_by_id=MappingProxyType(dict(specs_by_id)),
            identity_redirects=MappingProxyType(dict(identity_redirects)),
            room_union=room_union,
            geometry_build_error=geometry_error,
            shared_boundary_lengths=MappingProxyType(shared_lengths),
        )


def shared_boundary_length(
    context: ScoringContext, first_id: str, second_id: str
) -> float:
    resolved_first = context.identity_redirects.get(first_id, first_id)
    resolved_second = context.identity_redirects.get(second_id, second_id)
    if resolved_first == resolved_second:
        return 0.0
    return context.shared_boundary_lengths.get(
        _pair_key(resolved_first, resolved_second), 0.0
    )


def _normalize_identity_redirects(
    raw_redirects: Any,
    specs_by_id: Mapping[str, NormalizedRoomSpec],
    physical_rooms_by_id: Mapping[str, NormalizedRoom],
) -> dict[str, str]:
    if not isinstance(raw_redirects, Mapping):
        raise ScoringInputError("floor_plan.identity_redirects must be a mapping.")

    redirects: dict[str, str] = {}
    for raw_source, raw_target in raw_redirects.items():
        source = _nonempty_text(raw_source, "identity redirect source")
        target = _nonempty_text(raw_target, f"identity redirect '{source}' target")
        unknown = [item for item in (source, target) if item not in specs_by_id]
        if unknown:
            raise ScoringInputError(
                "Identity redirect references unknown specification room ID(s): "
                + ", ".join(sorted(set(unknown)))
            )
        if source in physical_rooms_by_id:
            raise ScoringInputError(
                f"Identity redirect source '{source}' still exists in the floor plan."
            )
        redirects[source] = target

    flattened: dict[str, str] = {}
    for source in redirects:
        visited = {source}
        target = redirects[source]
        while target in redirects:
            if target in visited:
                raise ScoringInputError(
                    f"Identity redirects contain a cycle involving '{target}'."
                )
            visited.add(target)
            target = redirects[target]
        if target not in physical_rooms_by_id:
            raise ScoringInputError(
                f"Identity redirect '{source}' does not resolve to a surviving room."
            )
        if specs_by_id[source].room_type != specs_by_id[target].room_type:
            raise ScoringInputError(
                f"Identity redirect '{source}' changes room type when resolving to '{target}'."
            )
        flattened[source] = target
    return flattened


def _normalize_specs(raw_specs: Any) -> tuple[NormalizedRoomSpec, ...]:
    specs: list[NormalizedRoomSpec] = []
    for index, raw in enumerate(_as_sequence(raw_specs, "specification.rooms")):
        label = f"specification.rooms[{index}]"
        room_id = _nonempty_text(_required_attr(raw, "id", label), f"{label}.id")
        room_type = _required_room_type(
            _required_attr(raw, "room_type", label), f"{label}.room_type"
        )
        name = _nonempty_text(_required_attr(raw, "name", label), f"{label}.name")
        raw_size = _required_attr(raw, "size", label)
        size = NormalizedRoomSize(
            min_width=_positive_number(
                _required_attr(raw_size, "min_width", f"{label}.size"),
                f"{label}.size.min_width",
            ),
            max_width=_positive_number(
                _required_attr(raw_size, "max_width", f"{label}.size"),
                f"{label}.size.max_width",
            ),
            min_area=_positive_number(
                _required_attr(raw_size, "min_area", f"{label}.size"),
                f"{label}.size.min_area",
            ),
            max_area=_positive_number(
                _required_attr(raw_size, "max_area", f"{label}.size"),
                f"{label}.size.max_area",
            ),
        )
        if (
            size.min_width > size.max_width
            or size.min_area > size.max_area
        ):
            raise ScoringInputError(
                f"{label}.size has a minimum greater than its maximum."
            )
        specs.append(NormalizedRoomSpec(room_id, room_type, name, size))
    if not specs:
        raise ScoringInputError("specification.rooms must contain at least one room.")
    _unique_by_id(tuple(specs), "specification room")
    return tuple(specs)


def _normalize_relations(
    raw_relations: Any,
    specs_by_id: Mapping[str, NormalizedRoomSpec],
) -> tuple[NormalizedRelation, ...]:
    relations: list[NormalizedRelation] = []
    for index, raw in enumerate(
        _as_sequence(raw_relations, "specification.room_relations")
    ):
        label = f"specification.room_relations[{index}]"
        source = _nonempty_text(
            _required_attr(raw, "source_room_id", label), f"{label}.source_room_id"
        )
        targets = tuple(
            _nonempty_text(value, f"{label}.target_room_ids")
            for value in _as_sequence(
                _required_attr(raw, "target_room_ids", label),
                f"{label}.target_room_ids",
            )
        )
        if not targets:
            raise ScoringInputError(f"{label}.target_room_ids cannot be empty.")
        if len(set(targets)) != len(targets):
            raise ScoringInputError(f"{label}.target_room_ids contains duplicates.")
        unknown = [
            room_id for room_id in (source, *targets) if room_id not in specs_by_id
        ]
        if unknown:
            raise ScoringInputError(
                f"{label} references unknown room IDs: {', '.join(sorted(set(unknown)))}"
            )
        match_policy = _enum_text(
            _required_attr(raw, "match_policy", label), f"{label}.match_policy"
        )
        strength = _enum_text(
            _required_attr(raw, "strength", label), f"{label}.strength"
        )
        if match_policy not in {"and", "or"}:
            raise ScoringInputError(f"{label}.match_policy must be 'and' or 'or'.")
        if strength not in {"hard", "soft"}:
            raise ScoringInputError(f"{label}.strength must be 'hard' or 'soft'.")
        relations.append(NormalizedRelation(source, targets, match_policy, strength))
    return tuple(relations)


def _normalize_rooms(
    raw_rooms: Any,
    specs_by_id: Mapping[str, NormalizedRoomSpec],
) -> tuple[NormalizedRoom, ...]:
    rooms: list[NormalizedRoom] = []
    for index, raw in enumerate(_as_sequence(raw_rooms, "floor_plan.rooms")):
        label = f"floor_plan.rooms[{index}]"
        room_id = _nonempty_text(_required_attr(raw, "id", label), f"{label}.id")
        if room_id not in specs_by_id:
            raise ScoringInputError(f"{label} has unknown room ID '{room_id}'.")
        room_type = _required_room_type(
            _required_attr(raw, "room_type", label), f"{label}.room_type"
        )
        expected_type = specs_by_id[room_id].room_type
        if room_type != expected_type:
            raise ScoringInputError(
                f"{label} type '{room_type.value}' does not match specification "
                f"type '{expected_type.value}'."
            )
        name = _nonempty_text(_required_attr(raw, "name", label), f"{label}.name")
        boundary = _required_attr(raw, "boundary", label)
        points = _normalize_points(
            _required_attr(boundary, "points", f"{label}.boundary"), f"{label}.boundary"
        )
        polygon = Polygon(points)
        centroid = polygon.centroid
        rooms.append(
            NormalizedRoom(
                room_id=room_id,
                room_type=room_type,
                name=name,
                points=points,
                polygon=polygon,
                area=float(polygon.area),
                centroid=(float(centroid.x), float(centroid.y)),
            )
        )
    if not rooms:
        raise ScoringInputError("floor_plan.rooms must contain at least one room.")
    _unique_by_id(tuple(rooms), "floor-plan room")
    return tuple(rooms)


def _normalize_points(raw_points: Any, label: str) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for index, raw in enumerate(_as_sequence(raw_points, f"{label}.points")):
        x = _finite_number(
            _required_attr(raw, "x", f"{label}.points[{index}]"),
            f"{label}.points[{index}].x",
        )
        y = _finite_number(
            _required_attr(raw, "y", f"{label}.points[{index}]"),
            f"{label}.points[{index}].y",
        )
        points.append((x, y))
    if len(points) >= 2 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3 or len(set(points)) < 3:
        raise ScoringInputError(f"{label} must contain at least three distinct points.")
    return tuple(points)


def _unique_by_id(values: Sequence[Any], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        item_id = value.room_id
        if item_id in result:
            raise ScoringInputError(f"Duplicate {label} ID '{item_id}'.")
        result[item_id] = value
    return result


def _required_attr(value: Any, name: str, label: str) -> Any:
    if not hasattr(value, name):
        raise ScoringInputError(f"{label} must define '{name}'.")
    return getattr(value, name)


def _as_sequence(value: Any, label: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)):
        raise ScoringInputError(f"{label} must be a sequence.")
    try:
        return tuple(value)
    except TypeError as exc:
        raise ScoringInputError(f"{label} must be a sequence.") from exc


def _enum_text(value: Any, label: str) -> str:
    raw = value.value if isinstance(value, Enum) else value
    return _nonempty_text(raw, label).strip().lower()


def _required_room_type(value: Any, label: str) -> RoomType:
    if not isinstance(value, RoomType):
        raise ScoringInputError(f"{label} must be a RoomType enum member.")
    return value


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScoringInputError(f"{label} must be a non-empty string.")
    return value.strip()


def _positive_number(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if number <= 0:
        raise ScoringInputError(f"{label} must be greater than zero.")
    return number


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ScoringInputError(f"{label} must be numeric, not boolean.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ScoringInputError(f"{label} must be numeric.") from exc
    if not math.isfinite(number):
        raise ScoringInputError(f"{label} must be finite.")
    return number


def _pair_key(first_id: str, second_id: str) -> tuple[str, str]:
    return tuple(sorted((first_id, second_id)))  # type: ignore[return-value]
