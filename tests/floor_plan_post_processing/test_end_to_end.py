from __future__ import annotations

from dataclasses import dataclass

import pytest

from fpg_core.domain import ExecutionMode, FloorPlan
from fpg_core.floor_plan_post_processing import (
    FloorPlanProcessor,
    PipelineStatus,
    PostProcessingContext,
    PostProcessingDetails,
    PostProcessingProfile,
    PostProcessingRequest,
    ProcessorOutcome,
    ProcessorRegistry,
    ProcessorStatus,
    ProcessorUse,
)
from fpg_core.floor_plan_post_processing.api import post_process_floor_plan


@dataclass(frozen=True)
class _Config:
    pass


class _OptionalFailure(FloorPlanProcessor):
    processor_id = "optional_failure"
    description = "test failure"
    config_type = _Config

    def process(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> ProcessorOutcome:
        floor_plan.applied_transformations.add("must_roll_back")
        raise RuntimeError("expected failure")


class _Dependent(FloorPlanProcessor):
    processor_id = "dependent"
    description = "test dependency"
    config_type = _Config
    prerequisites = ("optional_failure",)

    def process(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> ProcessorOutcome:
        raise AssertionError("a failed prerequisite must skip this processor")


class _NotApplicable(FloorPlanProcessor):
    processor_id = "not_applicable"
    description = "test applicability"
    config_type = _Config

    def is_applicable(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> tuple[bool, str]:
        return False, "not needed"

    def process(
        self, floor_plan: FloorPlan, context: PostProcessingContext, config: object
    ) -> ProcessorOutcome:
        raise AssertionError("non-applicable processor must not run")


def _registry() -> ProcessorRegistry:
    return ProcessorRegistry((_OptionalFailure(), _Dependent(), _NotApplicable()))


def _profile(*, required_failure: bool = False) -> PostProcessingProfile:
    return PostProcessingProfile(
        name="test",
        processors=(
            ProcessorUse("optional_failure", _Config(), required=required_failure),
            ProcessorUse("dependent", _Config()),
            ProcessorUse("not_applicable", _Config()),
        ),
    )


def test_production_and_debug_execution(floor_plan: FloorPlan) -> None:
    production = post_process_floor_plan(
        PostProcessingRequest(floor_plan, _profile()),
        registry=_registry(),
    )
    assert production.result.status is PipelineStatus.SUCCESS
    assert production.details is None
    assert "must_roll_back" not in floor_plan.applied_transformations

    explicit_production = post_process_floor_plan(
        PostProcessingRequest(floor_plan, _profile()),
        registry=_registry(),
        mode=ExecutionMode.PRODUCTION,
    )
    assert explicit_production.result.status is PipelineStatus.SUCCESS
    assert explicit_production.details is None

    debug = post_process_floor_plan(
        PostProcessingRequest(floor_plan, _profile()),
        registry=_registry(),
        mode=ExecutionMode.DEBUG,
    )
    assert isinstance(debug.details, PostProcessingDetails)
    assert [item.status for item in debug.details.executions] == [
        ProcessorStatus.FAILED,
        ProcessorStatus.SKIPPED,
        ProcessorStatus.NOT_APPLICABLE,
    ]
    assert debug.details.executions[0].rolled_back


def test_required_failure_stops_after_rollback(floor_plan: FloorPlan) -> None:
    execution = post_process_floor_plan(
        PostProcessingRequest(floor_plan, _profile(required_failure=True)),
        registry=_registry(),
        mode=ExecutionMode.DEBUG,
    )

    assert execution.result.status is PipelineStatus.FAILED
    assert execution.result.failure is not None
    assert "must_roll_back" not in floor_plan.applied_transformations
    assert execution.details is not None
    assert len(execution.details.executions) == 1


def test_invalid_mode_is_rejected(floor_plan: FloorPlan) -> None:
    with pytest.raises(TypeError, match="ExecutionMode"):
        post_process_floor_plan(  # type: ignore[arg-type]
            PostProcessingRequest(floor_plan, _profile()),
            registry=_registry(),
            mode="debug",
        )
