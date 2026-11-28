import pytest

from fpg_core.floor_plan_solver.constraints.room_specific.s_hallway_efficiency import (
    HallwayEfficiencyConstraint,
)
from fpg_core.floor_plan_solver.exceptions import InvalidProfileError


@pytest.mark.parametrize("value", [True, None, "invalid", -1])
def test_invalid_area_penalty_multiplier(value):
    with pytest.raises(InvalidProfileError, match="area_penalty_multiplier"):
        HallwayEfficiencyConstraint._non_negative_int(value, "area_penalty_multiplier")
