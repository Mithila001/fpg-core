from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from ..types import FloorPlan, Point, RoomId

from .domain import (
    AnalyzedWall,
    PreparedFloorPlan,
    WallKind,
    WallOrientation,
    WallSide,
)
from .exceptions import OpeningInputError
from .profiles import OpeningGenerationProfile


@dataclass(frozen=True, slots=True)
class _RawSegment:
    orientation: WallOrientation
    fixed: int
    start: int
    end: int
    room_id: RoomId | None
    floor_boundary: bool = False


@dataclass(frozen=True, slots=True)
class _AtomicWall:
    orientation: WallOrientation
    fixed: int
    start: int
    end: int
    kind: WallKind
    room_ids: tuple[RoomId, ...]
    side: WallSide | None


def _scaled(value: float, scale: int) -> int:
    return int(round(value * scale))


def _segments(
    points: tuple[Point, ...], scale: int, room_id: RoomId | None
) -> list[_RawSegment]:
    result: list[_RawSegment] = []
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        x1, y1 = _scaled(first.x, scale), _scaled(first.y, scale)
        x2, y2 = _scaled(second.x, scale), _scaled(second.y, scale)
        if y1 == y2:
            result.append(
                _RawSegment(
                    WallOrientation.HORIZONTAL,
                    y1,
                    min(x1, x2),
                    max(x1, x2),
                    room_id,
                    room_id is None,
                )
            )
        elif x1 == x2:
            result.append(
                _RawSegment(
                    WallOrientation.VERTICAL,
                    x1,
                    min(y1, y2),
                    max(y1, y2),
                    room_id,
                    room_id is None,
                )
            )
        else:
            raise OpeningInputError("non-axis-aligned segment reached wall analysis")
    return result


def _exterior_side(
    orientation: WallOrientation,
    fixed: int,
    start: int,
    end: int,
    room_shape: ShapelyPolygon,
    scale: int,
) -> WallSide:
    fixed_value = fixed / scale
    midpoint = (start + end) / (2 * scale)
    epsilon = 1 / (scale * 10)
    if orientation is WallOrientation.HORIZONTAL:
        above = room_shape.contains(ShapelyPoint(midpoint, fixed_value + epsilon))
        below = room_shape.contains(ShapelyPoint(midpoint, fixed_value - epsilon))
        if above and not below:
            return WallSide.SOUTH
        if below and not above:
            return WallSide.NORTH
    else:
        right = room_shape.contains(ShapelyPoint(fixed_value + epsilon, midpoint))
        left = room_shape.contains(ShapelyPoint(fixed_value - epsilon, midpoint))
        if right and not left:
            return WallSide.WEST
        if left and not right:
            return WallSide.EAST
    raise OpeningInputError("could not determine exterior side for a room wall")


def _wall_id(wall: _AtomicWall) -> str:
    room_key = "-".join(sorted(str(room_id) for room_id in wall.room_ids))
    return (
        f"{wall.kind.value}:{wall.orientation.value}:{wall.fixed}:"
        f"{wall.start}:{wall.end}:{room_key}"
    )


def analyze_floor_plan(
    floor_plan: FloorPlan,
    profile: OpeningGenerationProfile,
) -> PreparedFloorPlan:
    scale = profile.geometry.coordinate_scale
    raw: list[_RawSegment] = _segments(floor_plan.boundary.points, scale, None)
    room_shapes: dict[RoomId, ShapelyPolygon] = {}
    for room in floor_plan.rooms:
        raw.extend(_segments(room.boundary.points, scale, room.id))
        room_shapes[room.id] = ShapelyPolygon(
            [(point.x, point.y) for point in room.boundary.points]
        )

    by_line: dict[tuple[WallOrientation, int], list[_RawSegment]] = {}
    for segment in raw:
        by_line.setdefault((segment.orientation, segment.fixed), []).append(segment)

    atomic: list[_AtomicWall] = []
    for (orientation, fixed), segments in sorted(
        by_line.items(), key=lambda item: (item[0][0].value, item[0][1])
    ):
        endpoints = sorted({value for segment in segments for value in (segment.start, segment.end)})
        for start, end in zip(endpoints, endpoints[1:]):
            if start == end:
                continue
            covering = [segment for segment in segments if segment.start <= start and segment.end >= end]
            room_ids = tuple(
                sorted(
                    {segment.room_id for segment in covering if segment.room_id is not None},
                    key=str,
                )
            )
            on_boundary = any(segment.floor_boundary for segment in covering)
            if len(room_ids) > 2:
                raise OpeningInputError("more than two rooms share an atomic wall span")
            if len(room_ids) == 2:
                atomic.append(
                    _AtomicWall(orientation, fixed, start, end, WallKind.SHARED, room_ids, None)
                )
            elif len(room_ids) == 1 and on_boundary:
                side = _exterior_side(
                    orientation,
                    fixed,
                    start,
                    end,
                    room_shapes[room_ids[0]],
                    scale,
                )
                atomic.append(
                    _AtomicWall(
                        orientation,
                        fixed,
                        start,
                        end,
                        WallKind.EXTERIOR,
                        room_ids,
                        side,
                    )
                )

    merged: list[_AtomicWall] = []
    for wall in sorted(
        atomic,
        key=lambda item: (
            item.orientation.value,
            item.fixed,
            item.start,
            item.kind.value,
            tuple(map(str, item.room_ids)),
        ),
    ):
        if merged:
            previous = merged[-1]
            if (
                previous.orientation is wall.orientation
                and previous.fixed == wall.fixed
                and previous.end == wall.start
                and previous.kind is wall.kind
                and previous.room_ids == wall.room_ids
                and previous.side is wall.side
            ):
                merged[-1] = _AtomicWall(
                    previous.orientation,
                    previous.fixed,
                    previous.start,
                    wall.end,
                    previous.kind,
                    previous.room_ids,
                    previous.side,
                )
                continue
        merged.append(wall)

    walls = tuple(
        AnalyzedWall(
            id=_wall_id(wall),
            orientation=wall.orientation,
            fixed_coordinate=wall.fixed,
            start=wall.start,
            end=wall.end,
            kind=wall.kind,
            room_ids=wall.room_ids,
            exterior_side=wall.side,
        )
        for wall in merged
    )
    return PreparedFloorPlan(
        walls=walls,
        rooms_by_id={room.id: room for room in floor_plan.rooms},
        scale=scale,
    )
