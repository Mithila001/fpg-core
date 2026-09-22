from __future__ import annotations

import copy

import pytest

from fpg_core.domain import ExecutionMode, FloorPlan, FloorPlanGenerationSpec
from fpg_core.floor_plan_scoring.api import (
    FloorPlanScoringDetails,
    FloorPlanScoringInput,
    create_default_profile,
    score_floor_plan,
)


def test_production_and_debug_execution(
    floor_plan: FloorPlan,
    generation_spec: FloorPlanGenerationSpec,
) -> None:
    scoring_input = FloorPlanScoringInput(
        floor_plan,
        generation_spec,
        create_default_profile(),
    )

    production = score_floor_plan(scoring_input)
    explicit_production = score_floor_plan(
        scoring_input,
        mode=ExecutionMode.PRODUCTION,
    )
    debug = score_floor_plan(scoring_input, mode=ExecutionMode.DEBUG)

    assert production.details is None
    assert production.metadata.mode is ExecutionMode.PRODUCTION
    assert explicit_production.result == production.result
    assert explicit_production.details is None
    assert debug.result == production.result
    assert isinstance(debug.details, FloorPlanScoringDetails)
    assert debug.details.group_results
    assert debug.details.evaluator_results
    assert any(item.metrics for item in debug.details.evaluator_results)


def test_critical_failure_short_circuits_later_groups(
    floor_plan: FloorPlan,
    generation_spec: FloorPlanGenerationSpec,
) -> None:
    invalid_plan = copy.deepcopy(floor_plan)
    invalid_plan.rooms[1].boundary = invalid_plan.rooms[0].boundary

    scoring_input = FloorPlanScoringInput(
        invalid_plan,
        generation_spec,
        create_default_profile(),
    )
    production = score_floor_plan(scoring_input)
    execution = score_floor_plan(
        scoring_input,
        mode=ExecutionMode.DEBUG,
    )

    assert execution.result == production.result
    assert not execution.result.passed_critical
    assert execution.result.critical_failure is not None
    assert execution.details is not None
    assert any(item.status.value == "skipped" for item in execution.details.group_results)


def test_invalid_mode_is_rejected(
    floor_plan: FloorPlan,
    generation_spec: FloorPlanGenerationSpec,
) -> None:
    with pytest.raises(TypeError, match="ExecutionMode"):
        score_floor_plan(  # type: ignore[arg-type]
            FloorPlanScoringInput(
                floor_plan,
                generation_spec,
                create_default_profile(),
            ),
            mode="debug",
        )
