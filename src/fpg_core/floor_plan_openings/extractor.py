from __future__ import annotations

import copy
import hashlib
from typing import Any

from ..types import (
    FloorPlan,
    FloorPlanOpening,
    OpeningId,
    Point,
    RoomId,
)

from .domain import WallOrientation
from .model import BuiltOpeningModel, PlacementVariables


def _coordinates(
    variables: PlacementVariables,
    solver: Any,
    scale: int,
) -> tuple[Point, Point, int, int]:
    local_start = int(solver.Value(variables.start))
    local_end = int(solver.Value(variables.end))
    axis_start = variables.wall.start + local_start
    axis_end = variables.wall.start + local_end
    fixed = variables.wall.fixed_coordinate
    if variables.wall.orientation is WallOrientation.HORIZONTAL:
        start = Point(axis_start / scale, fixed / scale)
        end = Point(axis_end / scale, fixed / scale)
    else:
        start = Point(fixed / scale, axis_start / scale)
        end = Point(fixed / scale, axis_end / scale)
    return start, end, local_start, local_end


def _opening_id(
    variables: PlacementVariables,
    room_ids: tuple[RoomId, ...],
    local_start: int,
    local_end: int,
) -> OpeningId:
    identity = "|".join(
        (
            variables.demand.purpose.value,
            ",".join(sorted(map(str, room_ids))),
            variables.wall.id,
            str(local_start),
            str(local_end),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return OpeningId(f"opening_{digest}")


def extract_floor_plan(
    source: FloorPlan,
    solver: Any,
    built: BuiltOpeningModel,
) -> FloorPlan:
    scale = built.context.prepared.scale
    openings: list[FloorPlanOpening] = []
    for variables in built.context.all_variables:
        if not solver.BooleanValue(variables.selected):
            continue
        room_ids = variables.demand.room_ids or variables.wall.room_ids
        start, end, local_start, local_end = _coordinates(variables, solver, scale)
        openings.append(
            FloorPlanOpening(
                id=_opening_id(variables, room_ids, local_start, local_end),
                opening_type=variables.demand.opening_type,
                purpose=variables.demand.purpose,
                start=start,
                end=end,
                connected_room_ids=room_ids,
            )
        )
    openings.sort(key=lambda item: str(item.id))
    result = copy.deepcopy(source)
    result.openings = openings
    return result
