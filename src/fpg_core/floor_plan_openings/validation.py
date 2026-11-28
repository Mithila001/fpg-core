from __future__ import annotations

from math import isclose

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.polygon import orient

from ..domain import (
    FloorPlan,
    FloorPlanOpening,
    OpeningPurpose,
    OpeningType,
    Point,
    Polygon,
    RoomId,
    RoomRole,
    RoomType,
)
from .config import FloorPlanOpeningsConfig
from .domain import AnalyzedWall, PreparedFloorPlan, WallKind, WallOrientation
from .exceptions import OpeningExtractionError, OpeningInputError


def _shape(points: tuple[Point, ...]) -> ShapelyPolygon:
    return ShapelyPolygon([(point.x, point.y) for point in points])


def _normalize_polygon(polygon: Polygon, tolerance: float) -> Polygon:
    points = list(polygon.points)
    if (
        len(points) > 1
        and isclose(points[0].x, points[-1].x, abs_tol=tolerance)
        and isclose(points[0].y, points[-1].y, abs_tol=tolerance)
    ):
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
    if (
        shape.is_empty
        or not shape.is_valid
        or shape.area <= tolerance
        or shape.interiors
    ):
        raise OpeningInputError("polygon must be simple, hole-free, and positive-area")
    canonical = orient(shape, sign=1.0)
    return Polygon(
        tuple(
            Point(float(x), float(y)) for x, y in list(canonical.exterior.coords)[:-1]
        )
    )


def _validate_rectilinear(
    label: str, points: tuple[Point, ...], tolerance: float
) -> None:
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        horizontal = isclose(start.y, end.y, abs_tol=tolerance)
        vertical = isclose(start.x, end.x, abs_tol=tolerance)
        if horizontal == vertical:
            raise OpeningInputError(
                f"{label} must contain only non-zero axis-aligned edges"
            )


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
    config: FloorPlanOpeningsConfig,
) -> None:
    tolerance = config.geometry.tolerance
    scale = config.geometry.coordinate_scale
    if floor_plan.openings:
        raise OpeningInputError(
            "opening generation requires a plan without existing openings"
        )
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
            raise OpeningInputError(
                f"room {room.id!s} is not in canonical polygon form"
            )
        _validate_rectilinear(f"room {room.id!s}", room.boundary.points, tolerance)
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
    config: FloorPlanOpeningsConfig,
) -> None:
    if (
        source.boundary != generated.boundary
        or source.rooms != generated.rooms
        or source.identity_redirects != generated.identity_redirects
        or source.applied_transformations != generated.applied_transformations
    ):
        raise OpeningExtractionError(
            "opening generation changed floor-plan geometry or metadata"
        )

    opening_ids = [opening.id for opening in generated.openings]
    if len(opening_ids) != len(set(opening_ids)):
        raise OpeningExtractionError("generated opening IDs are not unique")

    if prepared.rooms_by_id:
        for purpose in (
            OpeningPurpose.MAIN_ENTRANCE,
            OpeningPurpose.SECONDARY_ENTRANCE,
        ):
            if sum(opening.purpose is purpose for opening in generated.openings) != 1:
                raise OpeningExtractionError(f"expected exactly one {purpose.value}")

    pairs: set[frozenset[RoomId]] = set()
    adjacency: dict[RoomId, set[RoomId]] = {
        room_id: set() for room_id in prepared.rooms_by_id
    }
    normal_counts = {room_id: 0 for room_id in adjacency}
    special_counts = {room_id: 0 for room_id in adjacency}
    total_counts = {room_id: 0 for room_id in adjacency}
    for opening in generated.openings:
        if (
            opening.opening_type is not OpeningType.DOOR
            or len(opening.connected_room_ids) != 2
        ):
            continue
        left, right = opening.connected_room_ids
        if left not in adjacency or right not in adjacency or left == right:
            raise OpeningExtractionError("door has invalid connected rooms")
        pair = frozenset((left, right))
        room_types = frozenset(
            prepared.rooms_by_id[room_id].room_type for room_id in pair
        )
        if not any(
            room_types == frozenset(allowed)
            for allowed in config.policy.allowed_room_pairs
        ):
            raise OpeningExtractionError("door connects disallowed room types")
        if RoomType.ATTACHED_BATHROOM in room_types and room_types != {
            RoomType.BEDROOM,
            RoomType.ATTACHED_BATHROOM,
        }:
            raise OpeningExtractionError("attached bathroom must connect to a bedroom")
        if config.policy.prevent_duplicate_connections and pair in pairs:
            raise OpeningExtractionError("duplicate connection between rooms")
        pairs.add(pair)
        adjacency[left].add(right)
        adjacency[right].add(left)
        for room_id, other_id in ((left, right), (right, left)):
            room_type = prepared.rooms_by_id[room_id].room_type
            other_type = prepared.rooms_by_id[other_id].room_type
            special = (room_type, other_type) in {
                (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
                (RoomType.KITCHEN, RoomType.DINING_ROOM),
            }
            total_counts[room_id] += 1
            (special_counts if special else normal_counts)[room_id] += 1
    if "room_door_limits" in config.enabled_constraints:
        for room_id, room in prepared.rooms_by_id.items():
            cap = dict(config.policy.normal_connection_caps).get(room.room_type)
            if (
                special_counts[room_id] > 1
                or (cap is not None and normal_counts[room_id] > cap)
                or total_counts[room_id]
                > config.policy.cap_by_room_type.get(room.room_type, 10)
                + special_counts[room_id]
            ):
                raise OpeningExtractionError(
                    f"room {room_id!s} exceeds its connection limit"
                )
    if prepared.rooms_by_id:
        main = next(
            opening
            for opening in generated.openings
            if opening.purpose is OpeningPurpose.MAIN_ENTRANCE
        )
        reachable = set(main.connected_room_ids)
        pending = list(reachable)
        while pending:
            for room_id in adjacency.get(pending.pop(), ()):
                if room_id not in reachable:
                    reachable.add(room_id)
                    pending.append(room_id)
        required = {
            room_id
            for room_id, room in prepared.rooms_by_id.items()
            if room.room_type in config.policy.required_access_room_types
        }
        secondary = next(
            opening
            for opening in generated.openings
            if opening.purpose is OpeningPurpose.SECONDARY_ENTRANCE
        )
        if not required.issubset(reachable) or not set(
            secondary.connected_room_ids
        ).issubset(reachable):
            raise OpeningExtractionError(
                "required rooms or secondary entrance are not accessible from the main entrance"
            )

    walls = prepared.walls
    placements: list[tuple[FloorPlanOpening, AnalyzedWall, tuple[int, int]]] = []
    for opening in generated.openings:
        expected_type = (
            OpeningType.WINDOW
            if opening.purpose is OpeningPurpose.DAYLIGHT
            else OpeningType.DOOR
        )
        if opening.opening_type is not expected_type:
            raise OpeningExtractionError(
                f"opening {opening.id!s} has inconsistent type and purpose"
            )
        expected_cardinality = (
            2
            if opening.purpose
            in {
                OpeningPurpose.ROOM_CONNECTION,
            }
            else 1
        )
        if (
            opening.purpose is OpeningPurpose.MAIN_ENTRANCE
            and len(opening.connected_room_ids) == 2
        ):
            expected_cardinality = 2
        if len(opening.connected_room_ids) != expected_cardinality:
            raise OpeningExtractionError(
                f"opening {opening.id!s} has invalid room cardinality"
            )
        if len(set(opening.connected_room_ids)) != len(opening.connected_room_ids):
            raise OpeningExtractionError(
                f"opening {opening.id!s} repeats a connected room"
            )

        match = None
        for wall in walls:
            if tuple(sorted(wall.room_ids)) != tuple(
                sorted(opening.connected_room_ids)
            ):
                continue
            if (
                len(opening.connected_room_ids) == 1
                and wall.kind is not WallKind.EXTERIOR
            ):
                continue
            interval = _opening_interval(opening, wall, prepared.scale)
            if interval is not None:
                match = (wall, interval)
                break
        if match is None:
            raise OpeningExtractionError(
                f"opening {opening.id!s} does not lie on its connected wall"
            )
        length = match[1][1] - match[1][0]
        door_width = round(config.dimensions.door_width * prepared.scale)
        window_width = (
            round(
                config.window_policy(
                    prepared.rooms_by_id[match[0].room_ids[0]].room_type
                ).width
                * prepared.scale
            )
            if opening.opening_type is OpeningType.WINDOW
            else 0
        )
        if opening.opening_type is OpeningType.WINDOW and length != window_width:
            raise OpeningExtractionError(
                f"opening {opening.id!s} has an invalid window width"
            )
        if opening.opening_type is OpeningType.WINDOW:
            minimum = round(
                config.window_policy(
                    prepared.rooms_by_id[match[0].room_ids[0]].room_type
                ).minimum_clearance
                * prepared.scale
            )
            if match[1][0] < minimum or match[0].length - match[1][1] < minimum:
                raise OpeningExtractionError(
                    f"opening {opening.id!s} violates minimum window clearance"
                )
        if opening.opening_type is OpeningType.DOOR:
            if match[0].kind is WallKind.SHARED:
                policy = config.interior_doors.resolve(
                    tuple(
                        prepared.rooms_by_id[room_id].room_type
                        for room_id in match[0].room_ids
                    )
                )
                minimum = round(policy.minimum_clearance * prepared.scale)
                if length != round(policy.door_width * prepared.scale):
                    raise OpeningExtractionError(
                        f"opening {opening.id!s} has an invalid interior door width"
                    )
                if match[1][0] < minimum or match[0].length - match[1][1] < minimum:
                    raise OpeningExtractionError(
                        f"opening {opening.id!s} violates minimum interior clearance"
                    )
            if match[0].kind is WallKind.EXTERIOR and not (0 < length <= door_width):
                raise OpeningExtractionError(
                    f"opening {opening.id!s} has an invalid exterior door width"
                )
            if (
                opening.purpose is OpeningPurpose.SECONDARY_ENTRANCE
                and length != door_width
            ):
                raise OpeningExtractionError(
                    f"opening {opening.id!s} has an invalid secondary entrance width"
                )
            if opening.purpose is OpeningPurpose.SECONDARY_ENTRANCE and (
                prepared.rooms_by_id[match[0].room_ids[0]].room_type
                not in config.policy.secondary_room_priority
                or prepared.rooms_by_id[match[0].room_ids[0]].room_type
                not in {RoomType.KITCHEN, RoomType.HALLWAY}
            ):
                raise OpeningExtractionError(
                    f"opening {opening.id!s} has an ineligible secondary entrance room"
                )
        placements.append((opening, match[0], match[1]))

    spacing = round(config.geometry.window_spacing * prepared.scale)
    for index, (left_opening, left_wall, left_interval) in enumerate(placements):
        for right_opening, right_wall, right_interval in placements[index + 1 :]:
            if (
                left_wall.orientation is not right_wall.orientation
                or left_wall.fixed_coordinate != right_wall.fixed_coordinate
            ):
                continue
            required_gap = (
                spacing
                if OpeningType.WINDOW
                in {left_opening.opening_type, right_opening.opening_type}
                else 0
            )
            left_start, left_end = (left_wall.start + value for value in left_interval)
            right_start, right_end = (
                right_wall.start + value for value in right_interval
            )
            if not (
                left_end + required_gap <= right_start
                or right_end + required_gap <= left_start
            ):
                raise OpeningExtractionError(
                    "generated openings overlap or violate spacing"
                )
