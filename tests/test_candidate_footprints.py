import pytest

from fpg_core.candidate_scoring.exceptions import ScoringInputError
from fpg_core.candidate_scoring.footprints import (
    allocated_areas,
    proximity_score,
)
from fpg_core.domain import (
    FloorPlanGenerationSpec,
    FloorSpec,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)


def test_allocation_reserves_full_hallway_capacity():
    rooms = (
        RoomSpec(RoomId("bed"), RoomType.BEDROOM, "Bed", RoomSizeSpec(1, 10, 100, 300)),
        RoomSpec(
            RoomId("hall"), RoomType.HALLWAY, "Hall", RoomSizeSpec(1, 10, 50, 1000)
        ),
    )
    spec = FloorPlanGenerationSpec(FloorSpec(20, 10), rooms, ())
    assert allocated_areas(spec)["bed"] == 150
    assert proximity_score(10, 5, 30) == 80
    with pytest.raises(ScoringInputError):
        allocated_areas(FloorPlanGenerationSpec(FloorSpec(10, 10), rooms, ()))


def test_fixed_area_and_linear_proximity_endpoints():
    rooms = (
        RoomSpec(RoomId("fixed"), RoomType.BEDROOM, "Fixed", RoomSizeSpec(1, 10, 100, 100)),
        RoomSpec(RoomId("expand"), RoomType.KITCHEN, "Expand", RoomSizeSpec(1, 10, 100, 300)),
    )
    spec = FloorPlanGenerationSpec(FloorSpec(20, 20), rooms, ())
    assert allocated_areas(spec) == {"fixed": 100, "expand": 300}
    assert proximity_score(5, 5, 30) == 100
    assert proximity_score(30, 5, 30) == 0
