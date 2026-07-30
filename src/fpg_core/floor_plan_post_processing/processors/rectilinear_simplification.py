from __future__ import annotations

from ...types import Polygon
from ..config import RectilinearSimplificationConfig
from ..contracts import FloorPlanProcessor, ProcessorOutcome, ProcessorStatus
from ..geometry import normalize_polygon, to_shapely


def _rectilinear(points, tolerance):
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        if abs(point.x - nxt.x) > tolerance and abs(point.y - nxt.y) > tolerance:
            return False
    return True


def _simplify(points, tolerance):
    result = list(points)
    changed = True
    while changed and len(result) > 3:
        changed = False
        retained = []
        for index, point in enumerate(result):
            previous = result[index - 1]
            nxt = result[(index + 1) % len(result)]
            cross = (point.x - previous.x) * (nxt.y - point.y) - (
                point.y - previous.y
            ) * (nxt.x - point.x)
            if abs(cross) <= tolerance:
                changed = True
            else:
                retained.append(point)
        if len(retained) < 3:
            break
        result = retained
    return tuple(result)


class RectilinearSimplificationProcessor(FloorPlanProcessor):
    processor_id = "rectilinear_simplification"
    description = "Remove redundant vertices from rectilinear room polygons."
    config_type = RectilinearSimplificationConfig
    prerequisites = ("grid_snap",)

    def process(self, floor_plan, context, config):
        tolerance = context.numeric.tolerance
        affected = []
        ignored = 0
        for room in floor_plan.rooms:
            points = room.boundary.points
            if not _rectilinear(points, tolerance):
                ignored += 1
                continue
            simplified = _simplify(points, tolerance)
            if simplified == points:
                continue
            before = to_shapely(room.boundary)
            candidate = normalize_polygon(Polygon(simplified), tolerance)
            after = to_shapely(candidate)
            if before.symmetric_difference(after).area > tolerance:
                continue
            room.boundary = candidate
            affected.append(room.id)
        if not affected:
            return ProcessorOutcome(
                ProcessorStatus.NO_CHANGE,
                "no redundant rectilinear vertices were found",
                metrics={"non_rectilinear_rooms": ignored},
            )
        return ProcessorOutcome(
            ProcessorStatus.CHANGED,
            "simplified rectilinear room boundaries",
            tuple(affected),
            metrics={"rooms_modified": len(affected), "non_rectilinear_rooms": ignored},
        )
