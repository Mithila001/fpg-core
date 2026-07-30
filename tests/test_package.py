from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import fpg_core
from fpg_core.types import Point, Polygon
from fpg_core.types_new import Point as CompatibilityPoint


def test_root_package_is_lightweight_and_versioned() -> None:
    assert fpg_core.__version__
    assert fpg_core.FpgCoreConfig


def test_shared_geometry_contracts_are_available() -> None:
    point = Point(x=10, y=20)
    polygon = Polygon(points=(point, Point(20, 20), Point(20, 30)))

    assert polygon.points[0] == point
    assert CompatibilityPoint is Point

    with pytest.raises(FrozenInstanceError):
        point.x = 30  # type: ignore[misc]


def test_configuration_contract_import_is_lightweight() -> None:
    import sys

    import fpg_core.config  # noqa: F401

    assert "ortools" not in sys.modules


def test_setback_profile_freezes_nested_mappings() -> None:
    from fpg_core.types import (
        LandSide,
        RoadType,
        SetbackCalculationMode,
        SetbackProfile,
    )

    profile = SetbackProfile(
        name="default",
        status="active",
        description="test",
        calculation_mode=SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT,
        base_setbacks={LandSide.FRONT: 10},
        road_adjustments={
            RoadType.MAIN_ROAD: {LandSide.FRONT: 5},
        },
    )

    with pytest.raises(TypeError):
        profile.base_setbacks[LandSide.FRONT] = 20  # type: ignore[index]

    with pytest.raises(TypeError):
        profile.road_adjustments[RoadType.MAIN_ROAD][LandSide.FRONT] = 10  # type: ignore[index]
