from __future__ import annotations

import copy

import pytest

from fpg_core.domain import (
    ExecutionMode,
    FloorPlan,
    FloorPlanOpening,
    OpeningId,
    OpeningPurpose,
    OpeningType,
    Point,
    RoomId,
)
from fpg_core.floor_plan_openings import DEFAULT_OPENING_PROFILE
from fpg_core.floor_plan_openings.api import (
    OpeningDiagnostics,
    OpeningGenerationRequest,
    OpeningGenerationStatus,
    generate_openings,
)


def test_production_and_debug_execution(floor_plan: FloorPlan) -> None:
    source = copy.deepcopy(floor_plan)

    production = generate_openings(
        OpeningGenerationRequest(floor_plan, DEFAULT_OPENING_PROFILE)
    )
    explicit_production = generate_openings(
        OpeningGenerationRequest(floor_plan, DEFAULT_OPENING_PROFILE),
        mode=ExecutionMode.PRODUCTION,
    )
    debug = generate_openings(
        OpeningGenerationRequest(floor_plan, DEFAULT_OPENING_PROFILE),
        mode=ExecutionMode.DEBUG,
    )

    assert production.result.solved
    assert production.details is None
    assert explicit_production.result.status is production.result.status
    assert explicit_production.details is None
    assert floor_plan == source
    assert debug.result.status is production.result.status
    assert isinstance(debug.details, OpeningDiagnostics)
    assert debug.details.analyzed_wall_count > 0
    assert floor_plan == source


def test_invalid_input_is_structured_by_mode(floor_plan: FloorPlan) -> None:
    invalid = copy.deepcopy(floor_plan)
    invalid.openings.append(
        FloorPlanOpening(
            id=OpeningId("existing"),
            opening_type=OpeningType.DOOR,
            purpose=OpeningPurpose.ROOM_CONNECTION,
            start=Point(20, 5),
            end=Point(20, 10),
            connected_room_ids=(RoomId("living"), RoomId("bedroom")),
        )
    )

    production = generate_openings(
        OpeningGenerationRequest(invalid, DEFAULT_OPENING_PROFILE)
    )
    debug = generate_openings(
        OpeningGenerationRequest(invalid, DEFAULT_OPENING_PROFILE),
        mode=ExecutionMode.DEBUG,
    )

    assert production.result.status is OpeningGenerationStatus.INVALID_INPUT
    assert production.details is None
    assert debug.result.status is OpeningGenerationStatus.INVALID_INPUT
    assert debug.details is not None
    assert debug.details.issues[0].code == "invalid_input"


def test_invalid_mode_is_rejected(floor_plan: FloorPlan) -> None:
    with pytest.raises(TypeError, match="ExecutionMode"):
        generate_openings(  # type: ignore[arg-type]
            OpeningGenerationRequest(floor_plan, DEFAULT_OPENING_PROFILE),
            mode="debug",
        )
