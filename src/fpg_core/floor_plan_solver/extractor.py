from __future__ import annotations

from typing import Any

from .domain import FloorPlan, FloorPlanRoom, Point, Polygon
from .model import BuiltModel


def _rectangle_polygon(
    x: float,
    y: float,
    width: float,
    length: float,
) -> Polygon:
    return Polygon(
        points=(
            Point(x=x, y=y),
            Point(x=x + width, y=y),
            Point(x=x + width, y=y + length),
            Point(x=x, y=y + length),
        )
    )


def extract_floor_plan(solver: Any, built: BuiltModel) -> FloorPlan:
    context = built.context
    scale = context.problem.scale
    floor = context.problem.floor
    rooms: list[FloorPlanRoom] = []

    for prepared_room in context.problem.rooms:
        variables = context.variables_for(prepared_room.id_key)
        x = scale.to_domain(int(solver.Value(variables.x)))
        y = scale.to_domain(int(solver.Value(variables.y)))
        width = scale.to_domain(int(solver.Value(variables.width)))
        length = scale.to_domain(int(solver.Value(variables.length)))
        rooms.append(
            FloorPlanRoom(
                id=prepared_room.id,
                room_type=prepared_room.room_type,
                name=prepared_room.name,
                boundary=_rectangle_polygon(x, y, width, length),
            )
        )

    floor_width = scale.to_domain(floor.width)
    floor_length = scale.to_domain(floor.length)
    return FloorPlan(
        boundary=_rectangle_polygon(0.0, 0.0, floor_width, floor_length),
        rooms=rooms,
        openings=[],
    )
