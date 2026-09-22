from __future__ import annotations

import copy

import pytest

from fpg_core.domain import (
    FloorPlan,
    FloorPlanGenerationSpec,
    FloorPlanRoom,
    FloorSpec,
    Point,
    Polygon,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)


def rectangle(x1: float, y1: float, x2: float, y2: float) -> Polygon:
    return Polygon(
        (
            Point(x1, y1),
            Point(x2, y1),
            Point(x2, y2),
            Point(x1, y2),
        )
    )


@pytest.fixture
def generation_spec() -> FloorPlanGenerationSpec:
    return FloorPlanGenerationSpec(
        floor=FloorSpec(width=40, length=20),
        rooms=(
            RoomSpec(
                id=RoomId("living"),
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                size=RoomSizeSpec(5, 20, 40, 400),
            ),
            RoomSpec(
                id=RoomId("bedroom"),
                room_type=RoomType.BEDROOM,
                name="Bedroom",
                size=RoomSizeSpec(5, 20, 40, 400),
            ),
        ),
        room_relations=(),
    )


@pytest.fixture
def floor_plan() -> FloorPlan:
    return FloorPlan(
        boundary=rectangle(0, 0, 40, 20),
        rooms=[
            FloorPlanRoom(
                id=RoomId("living"),
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                boundary=rectangle(0, 0, 20, 20),
            ),
            FloorPlanRoom(
                id=RoomId("bedroom"),
                room_type=RoomType.BEDROOM,
                name="Bedroom",
                boundary=rectangle(20, 0, 40, 20),
            ),
        ],
    )


@pytest.fixture
def copied_floor_plan(floor_plan: FloorPlan) -> FloorPlan:
    return copy.deepcopy(floor_plan)
