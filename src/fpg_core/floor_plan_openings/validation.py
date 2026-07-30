from __future__ import annotations

from math import isclose

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.polygon import orient

from ..types import (
    FloorPlan,
    FloorPlanOpening,
    OpeningPurpose,
    OpeningType,
    Point,
    Polygon,
    RoomRole,
    RoomId,
    RoomType,
)

from .domain import AnalyzedWall, PreparedFloorPlan, WallKind, WallOrientation
from .exceptions import OpeningExtractionError, OpeningInputError
from .profiles import OpeningGenerationProfile


def _shape(points: tuple[Point, ...]) -> ShapelyPolygon:
    return ShapelyPolygon([(point.x, point.y) for point in points])


def _normalize_polygon(polygon: Polygon, tolerance: float) -> Polygon:
    points = list(polygon.points)
    if len(points) > 1 and isclose(
        points[0].x, points[-1].x, abs_tol=tolerance
    ) and isclose(points[0].y, points[-1].y, abs_tol=tolerance):
        points.pop()
    deduplicated: list[Point] = []
    for point in points:
        if not deduplicated or not (
            isclose(point.x, deduplicated[-1].x, abs_tol=tolerance)
            and isclose(point.y, deduplicated[-1].y, abs_tol=tolerance)
        ):
            deduplicated.append(point)
    if len(deduplicated) < 3:
        raise OpeningInputError("polygon requires at least three distinct points")
    shape = ShapelyPolygon([(point.x, point.y) for point in deduplicated])
    if shape.is_empty or not shape.is_valid or shape.area <= tolerance or shape.interiors:
        raise OpeningInputError("polygon must be simple, hole-free, and positive-area")
    canonical = orient(shape, sign=1.0)
    return Polygon(
        tuple(Point(float(x), float(y)) for x, y in list(canonical.exterior.coords)[:-1])
    )


def _validate_rectilinear(
    label: str, points: tuple[Point, ...], tolerance: float
) -> None:
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        horizontal = isclose(start.y, end.y, abs_tol=tolerance)
        vertical = isclose(start.x, end.x, abs_tol=tolerance)
        if horizontal == vertical:
            raise OpeningInputError(f"{label} must contain only non-zero axis-aligned edges")


def _validate_scaled(
    label: str, points: tuple[Point, ...], scale: int, tolerance: float
) -> None:
    for point in points:
        for coordinate in (point.x, point.y):
            scaled = round(coordinate * scale) / scale
            if not isclose(coordinate, scaled, abs_tol=tolerance):
                raise OpeningInputError(
                    f"{label} coordinates must align to the configured 1/{scale} grid"
                )


def validate_request_floor_plan(
    floor_plan: FloorPlan,
    profile: OpeningGenerationProfile,
) -> None:
    tolerance = profile.geometry.tolerance
    scale = profile.geometry.coordinate_scale
    if floor_plan.openings:
        raise OpeningInputError("opening generation requires a plan without existing openings")
    try:
        normalized_floor = _normalize_polygon(floor_plan.boundary, tolerance)
    except Exception as exc:  # noqa: BLE001
        raise OpeningInputError(f"invalid floor boundary: {exc}") from exc
    if normalized_floor != floor_plan.boundary:
        raise OpeningInputError("floor boundary is not in canonical polygon form")
    _validate_rectilinear("floor boundary", floor_plan.boundary.points, tolerance)
    _validate_scaled("floor boundary", floor_plan.boundary.points, scale, tolerance)

    room_ids = [room.id for room in floor_plan.rooms]
    if len(room_ids) != len(set(room_ids)):
        raise OpeningInputError("room IDs must be unique")
    if any(room.role is not RoomRole.STANDARD for room in floor_plan.rooms):
        raise OpeningInputError("opening generation requires finalized standard rooms")

    floor_shape = _shape(floor_plan.boundary.points)
    room_shapes: list[tuple[RoomId, ShapelyPolygon]] = []
    for room in floor_plan.rooms:
        if not isinstance(room.room_type, RoomType):
            raise OpeningInputError(f"room {room.id!s} has an invalid RoomType")
        try:
            normalized = _normalize_polygon(room.boundary, tolerance)
        except Exception as exc:  # noqa: BLE001
            raise OpeningInputError(f"invalid room {room.id!s}: {exc}") from exc
        if normalized != room.boundary:
            raise OpeningInputError(f"room {room.id!s} is not in canonical polygon form")
        _validate_rectilinear(
            f"room {room.id!s}", room.boundary.points, tolerance
        )
        _validate_scaled(f"room {room.id!s}", room.boundary.points, scale, tolerance)
        shape = _shape(room.boundary.points)
        if not floor_shape.buffer(tolerance).covers(shape):
            raise OpeningInputError(f"room {room.id!s} lies outside the floor boundary")
        room_shapes.append((room.id, shape))

    for index, (left_id, left) in enumerate(room_shapes):
        for right_id, right in room_shapes[index + 1 :]:
            if left.intersection(right).area > tolerance:
                raise OpeningInputError(f"rooms {left_id!s} and {right_id!s} overlap")


def _opening_interval(
    opening: FloorPlanOpening, wall: AnalyzedWall, scale: int
) -> tuple[int, int] | None:
    start_x = round(opening.start.x * scale)
    start_y = round(opening.start.y * scale)
    end_x = round(opening.end.x * scale)
    end_y = round(opening.end.y * scale)
    if wall.orientation is WallOrientation.HORIZONTAL:
        if start_y != wall.fixed_coordinate or end_y != wall.fixed_coordinate:
            return None
        low, high = sorted((start_x, end_x))
    else:
        if start_x != wall.fixed_coordinate or end_x != wall.fixed_coordinate:
            return None
        low, high = sorted((start_y, end_y))
    if low < wall.start or high > wall.end or low >= high:
        return None
    return low - wall.start, high - wall.start


def validate_generated_floor_plan(
    source: FloorPlan,
    generated: FloorPlan,
    prepared: PreparedFloorPlan,
    profile: OpeningGenerationProfile,
) -> None:
    if (
        source.boundary != generated.boundary
        or source.rooms != generated.rooms
        or source.identity_redirects != generated.identity_redirects
        or source.applied_transformations != generated.applied_transformations
    ):
        raise OpeningExtractionError("opening generation changed floor-plan geometry or metadata")

    opening_ids = [opening.id for opening in generated.openings]
    if len(opening_ids) != len(set(opening_ids)):
        raise OpeningExtractionError("generated opening IDs are not unique")

    walls = prepared.walls
    placements: list[tuple[FloorPlanOpening, AnalyzedWall, tuple[int, int]]] = []
    for opening in generated.openings:
        expected_type = (
            OpeningType.WINDOW
            if opening.purpose is OpeningPurpose.DAYLIGHT
            else OpeningType.DOOR
        )
        if opening.opening_type is not expected_type:
            raise OpeningExtractionError(f"opening {opening.id!s} has inconsistent type and purpose")
        expected_cardinality = (
            2
            if opening.purpose in {
                OpeningPurpose.ROOM_CONNECTION,
            }
            else 1
        )
        if opening.purpose is OpeningPurpose.MAIN_ENTRANCE and len(opening.connected_room_ids) == 2:
            expected_cardinality = 2
        if len(opening.connected_room_ids) != expected_cardinality:
            raise OpeningExtractionError(f"opening {opening.id!s} has invalid room cardinality")
        if len(set(opening.connected_room_ids)) != len(opening.connected_room_ids):
            raise OpeningExtractionError(f"opening {opening.id!s} repeats a connected room")

        match = None
        for wall in walls:
            if tuple(sorted(wall.room_ids)) != tuple(sorted(opening.connected_room_ids)):
                continue
            if len(opening.connected_room_ids) == 1 and wall.kind is not WallKind.EXTERIOR:
                continue
            interval = _opening_interval(opening, wall, prepared.scale)
            if interval is not None:
                match = (wall, interval)
                break
        if match is None:
            raise OpeningExtractionError(f"opening {opening.id!s} does not lie on its connected wall")
        length = match[1][1] - match[1][0]
        door_width = round(profile.dimensions.door_width * prepared.scale)
        window_width = round(profile.dimensions.window_width * prepared.scale)
        if opening.opening_type is OpeningType.WINDOW and length != window_width:
            raise OpeningExtractionError(f"opening {opening.id!s} has an invalid window width")
        if opening.opening_type is OpeningType.DOOR:
            if match[0].kind is WallKind.SHARED and length != door_width:
                raise OpeningExtractionError(f"opening {opening.id!s} has an invalid interior door width")
            if match[0].kind is WallKind.EXTERIOR and not (0 < length <= door_width):
                raise OpeningExtractionError(f"opening {opening.id!s} has an invalid exterior door width")
        placements.append((opening, match[0], match[1]))

    spacing = round(profile.geometry.window_spacing * prepared.scale)
    for index, (left, left_wall, left_interval) in enumerate(placements):
        for right, right_wall, right_interval in placements[index + 1 :]:
            if left_wall.id != right_wall.id:
                continue
            required_gap = (
                spacing
                if OpeningType.WINDOW in {left.opening_type, right.opening_type}
                else 0
            )
            left_start, left_end = left_interval
            right_start, right_end = right_interval
            if not (
                left_end + required_gap <= right_start
                or right_end + required_gap <= left_start
            ):
                raise OpeningExtractionError("generated openings overlap or violate spacing")
