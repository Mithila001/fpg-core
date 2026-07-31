from __future__ import annotations

from shapely.affinity import translate
from shapely.geometry import LineString, MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import substring, unary_union

from ...domain import RoomRole
from ..config import WallExtensionConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus
from ..exceptions import ProcessorError
from ..geometry import from_shapely, line_strings, to_shapely


def _space_components(geometry):
    if geometry.is_empty:
        return []
    if isinstance(geometry, ShapelyPolygon):
        return [geometry]
    return [
        geom
        for geom in getattr(geometry, "geoms", ())
        if isinstance(geom, ShapelyPolygon)
    ]


def _available_spaces(polygons):
    occupied = unary_union(polygons)
    holes = []
    for polygon in _space_components(occupied):
        holes.extend(ShapelyPolygon(ring) for ring in polygon.interiors)
    internal = unary_union(holes) if holes else MultiPolygon([])
    external = occupied.envelope.difference(occupied)
    return internal, external


def _extrude(line: LineString, target, maximum: float, tolerance: float):
    if line.is_empty or line.length <= tolerance or target.is_empty:
        return None
    coords = list(line.coords)
    dx = coords[-1][0] - coords[0][0]
    dy = coords[-1][1] - coords[0][1]
    normals = (
        ((0.0, 1.0), (0.0, -1.0)) if abs(dx) >= abs(dy) else ((1.0, 0.0), (-1.0, 0.0))
    )
    probe_distance = max(tolerance * 10, min(0.01, maximum / 10))
    midpoint = line.interpolate(0.5, normalized=True)
    normal = next(
        (
            (nx, ny)
            for nx, ny in normals
            if target.buffer(tolerance).covers(
                translate(midpoint, xoff=nx * probe_distance, yoff=ny * probe_distance)
            )
        ),
        None,
    )
    if normal is None:
        return None
    nx, ny = normal
    low, high = 0.0, maximum
    for _ in range(20):
        distance = (low + high) / 2
        shifted = translate(line, xoff=nx * distance, yoff=ny * distance)
        if target.buffer(tolerance).covers(shifted):
            low = distance
        else:
            high = distance
    if low <= tolerance:
        return None
    shifted = [(x + nx * low, y + ny * low) for x, y in coords]
    patch = ShapelyPolygon(coords + list(reversed(shifted))).intersection(target)
    return patch if not patch.is_empty and patch.area > tolerance else None


class WallExtensionProcessor(FloorPlanProcessor):
    processor_id = "wall_extension"
    description = (
        "Extend eligible room walls into deterministic void and recess targets."
    )
    config_type = WallExtensionConfig

    def is_applicable(self, floor_plan, context, config):
        assert isinstance(config, WallExtensionConfig)
        if config.transformation_version in floor_plan.applied_transformations:
            return False, "this transformation version was already applied"
        eligible = {rule.room_type for rule in config.rules}
        present = any(
            room.role is RoomRole.STANDARD and room.room_type in eligible
            for room in floor_plan.rooms
        )
        return present, "no eligible rooms exist"

    def process(self, floor_plan, context, config):
        assert isinstance(config, WallExtensionConfig)
        self._validate_config(config)
        tolerance = context.numeric.tolerance
        standard = [room for room in floor_plan.rooms if room.role is RoomRole.STANDARD]
        shapes = {room.id: to_shapely(room.boundary) for room in standard}
        affected = []

        for rule in config.rules:
            eligible = sorted(
                (room for room in standard if room.room_type is rule.room_type),
                key=lambda room: (shapes[room.id].area, str(room.id)),
            )[: rule.max_rooms]
            for room in eligible:
                internal, external = _available_spaces(list(shapes.values()))
                candidates = []
                for priority, target_group in enumerate((internal, external)):
                    for target in _space_components(target_group):
                        shared = shapes[room.id].boundary.intersection(target.boundary)
                        for line in line_strings(shared):
                            work = line
                            if work.length > rule.max_wall_length:
                                work = substring(work, 0, rule.max_wall_length)
                            if work.length + tolerance >= rule.min_wall_length:
                                candidates.append(
                                    (
                                        priority,
                                        -work.length,
                                        tuple(work.coords),
                                        work,
                                        target,
                                    )
                                )
                candidates.sort(key=lambda item: (item[0], item[1], item[2]))
                patches = []
                for _, _, _, line, target in candidates[: rule.max_selections]:
                    maximum = min(
                        line.length * rule.expansion_percentage, rule.max_distance
                    )
                    patch = _extrude(line, target, maximum, tolerance)
                    if patch is not None:
                        patches.append(patch)
                if not patches:
                    continue
                candidate = unary_union([shapes[room.id], *patches])
                if not isinstance(candidate, ShapelyPolygon):
                    raise ProcessorError(
                        f"wall extension disconnected room {room.id!s}"
                    )
                if any(
                    candidate.intersection(other).area > tolerance
                    for other_id, other in shapes.items()
                    if other_id != room.id
                ):
                    raise ProcessorError(
                        f"wall extension overlaps another room for {room.id!s}"
                    )
                room.boundary = from_shapely(candidate, tolerance)
                shapes[room.id] = candidate
                affected.append(room.id)

        floor_plan.applied_transformations.add(config.transformation_version)
        if not affected:
            return ProcessorOutcome(
                ProcessorStatus.NO_CHANGE, "no eligible wall could be extended"
            )
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "extended eligible room walls",
            tuple(affected),
            metrics={"rooms_modified": len(affected)},
        )

    @staticmethod
    def _validate_config(config: WallExtensionConfig) -> None:
        seen = set()
        for rule in config.rules:
            if rule.room_type in seen:
                raise ProcessorError("wall-extension room types must be unique")
            seen.add(rule.room_type)
            values = (
                rule.min_wall_length,
                rule.max_wall_length,
                rule.expansion_percentage,
                rule.max_distance,
            )
            if (
                any(value <= 0 for value in values)
                or rule.min_wall_length > rule.max_wall_length
            ):
                raise ProcessorError(
                    "wall-extension distances and lengths must be valid"
                )
            if rule.max_rooms < 1 or rule.max_selections < 1:
                raise ProcessorError("wall-extension selection limits must be positive")
