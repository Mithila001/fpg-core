from __future__ import annotations

from custom_test.full_flow.scenario import (
    build_buildable_land_config,
    build_land_request,
    build_usable_land_config,
)

from fpg_core.buildable_land import BuildableLandInput, calculate_buildable_land
from fpg_core.domain import ExecutionMode
from fpg_core.usable_land import UsableLandInput, find_usable_land


def test_land_flow_public_contracts_connect() -> None:
    buildable = calculate_buildable_land(
        BuildableLandInput(
            request=build_land_request(),
            config=build_buildable_land_config(),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert buildable.details is not None
    assert buildable.result.buildable_land.area > 0

    usable = find_usable_land(
        UsableLandInput(
            buildable_land=buildable.result.buildable_land,
            land=buildable.result.normalized_land,
            config=build_usable_land_config(),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert usable.details is not None
    assert usable.result.area > 0
    assert usable.result.area <= buildable.result.buildable_land.area
