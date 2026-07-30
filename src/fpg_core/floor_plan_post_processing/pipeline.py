from __future__ import annotations

import copy
import time

from ..types import FloorPlan
from .config import GridSnapConfig, HallwayMergeConfig, WallExtensionConfig
from .contracts import (
    PipelineStatus,
    PostProcessingContext,
    PostProcessingRequest,
    PostProcessingResult,
    ProcessingFailure,
    ProcessorExecution,
    ProcessorOutcome,
    ProcessorStatus,
)
from .exceptions import ConfigurationError, PostProcessingError, RollbackError
from .registry import ProcessorRegistry
from .validation import validate_floor_plan, validate_profile


def _restore(target: FloorPlan, snapshot: FloorPlan) -> None:
    try:
        target.boundary = copy.deepcopy(snapshot.boundary)
        target.rooms[:] = copy.deepcopy(snapshot.rooms)
        target.openings[:] = copy.deepcopy(snapshot.openings)
        target.identity_redirects.clear()
        target.identity_redirects.update(copy.deepcopy(snapshot.identity_redirects))
        target.applied_transformations.clear()
        target.applied_transformations.update(snapshot.applied_transformations)
    except Exception as exc:  # noqa: BLE001
        raise RollbackError(f"could not restore floor-plan snapshot: {exc}") from exc


def _preflight(request: PostProcessingRequest, registry: ProcessorRegistry) -> None:
    validate_profile(request.profile)
    seen: set[str] = set()
    for use in request.profile.processors:
        processor = registry.resolve(use.processor_id)
        if not isinstance(use.config, processor.config_type):
            raise ConfigurationError(
                f"processor {use.processor_id} requires {processor.config_type.__name__}"
            )
        missing = [item for item in processor.prerequisites if item not in seen]
        if missing:
            raise ConfigurationError(
                f"processor {use.processor_id} requires earlier processors: {', '.join(missing)}"
            )
        _validate_processor_config(use.config)
        seen.add(use.processor_id)


def _validate_processor_config(config: object) -> None:
    if (
        isinstance(config, GridSnapConfig)
        and config.grid_size is not None
        and config.grid_size <= 0
    ):
        raise ConfigurationError("grid size must be positive")
    if isinstance(config, HallwayMergeConfig) and config.minimum_shared_wall < 0:
        raise ConfigurationError("minimum shared-wall length cannot be negative")
    if isinstance(config, WallExtensionConfig):
        room_types = [rule.room_type for rule in config.rules]
        if len(room_types) != len(set(room_types)):
            raise ConfigurationError("wall-extension room types must be unique")
        for rule in config.rules:
            if (
                rule.min_wall_length <= 0
                or rule.max_wall_length <= 0
                or rule.min_wall_length > rule.max_wall_length
                or rule.max_rooms < 1
                or rule.max_selections < 1
                or rule.expansion_percentage <= 0
                or rule.max_distance <= 0
            ):
                raise ConfigurationError("wall-extension rules contain invalid values")


def run_pipeline(
    request: PostProcessingRequest, registry: ProcessorRegistry
) -> PostProcessingResult:
    plan = request.floor_plan
    executions: list[ProcessorExecution] = []
    try:
        _preflight(request, registry)
        validate_floor_plan(
            plan,
            tolerance=request.profile.numeric.tolerance,
            reject_openings=request.profile.reject_existing_openings,
        )
    except Exception as exc:  # noqa: BLE001
        code = exc.code if isinstance(exc, PostProcessingError) else "invalid_request"
        return PostProcessingResult(
            PipelineStatus.FAILED,
            plan,
            (),
            ProcessingFailure(code, str(exc)),
        )

    context = PostProcessingContext(
        specification=request.specification,
        floor_boundary=plan.boundary,
        numeric=request.profile.numeric,
        profile_name=request.profile.name,
    )
    unsuccessful: set[str] = set()

    for use in request.profile.processors:
        processor = registry.resolve(use.processor_id)
        failed_dependencies = [
            item for item in processor.prerequisites if item in unsuccessful
        ]
        if failed_dependencies:
            failure = ProcessingFailure(
                "prerequisite_failed",
                f"prerequisites did not succeed: {', '.join(failed_dependencies)}",
                use.processor_id,
            )
            executions.append(
                ProcessorExecution(
                    use.processor_id, ProcessorStatus.SKIPPED, 0.0, failure=failure
                )
            )
            unsuccessful.add(use.processor_id)
            continue

        applicable, reason = processor.is_applicable(plan, context, use.config)
        if not applicable:
            outcome = ProcessorOutcome(ProcessorStatus.NOT_APPLICABLE, reason)
            executions.append(
                ProcessorExecution(
                    use.processor_id,
                    ProcessorStatus.NOT_APPLICABLE,
                    0.0,
                    outcome=outcome,
                )
            )
            continue

        snapshot = copy.deepcopy(plan)
        started = time.perf_counter()
        try:
            outcome = processor.process(plan, context, use.config)
            if outcome.status not in {
                ProcessorStatus.CHANGED,
                ProcessorStatus.NO_CHANGE,
                ProcessorStatus.NOT_APPLICABLE,
            }:
                raise ConfigurationError(
                    "processor returned an invalid success outcome"
                )
            if use.validate_after:
                validate_floor_plan(
                    plan,
                    tolerance=context.numeric.tolerance,
                    require_no_placeholders=use.processor_id
                    == "remove_placeholder_rooms",
                )
            duration = (time.perf_counter() - started) * 1000
            executions.append(
                ProcessorExecution(
                    use.processor_id, outcome.status, duration, outcome=outcome
                )
            )
        except Exception as exc:  # noqa: BLE001
            duration = (time.perf_counter() - started) * 1000
            try:
                _restore(plan, snapshot)
            except RollbackError as rollback_exc:
                failure = ProcessingFailure(
                    rollback_exc.code, str(rollback_exc), use.processor_id
                )
                executions.append(
                    ProcessorExecution(
                        use.processor_id,
                        ProcessorStatus.FAILED,
                        duration,
                        failure=failure,
                    )
                )
                return PostProcessingResult(
                    PipelineStatus.FAILED, plan, tuple(executions), failure
                )
            code = (
                exc.code
                if isinstance(exc, PostProcessingError)
                else "unexpected_processor_error"
            )
            failure = ProcessingFailure(code, str(exc), use.processor_id)
            executions.append(
                ProcessorExecution(
                    use.processor_id,
                    ProcessorStatus.FAILED,
                    duration,
                    rolled_back=True,
                    failure=failure,
                )
            )
            unsuccessful.add(use.processor_id)
            if use.required:
                return PostProcessingResult(
                    PipelineStatus.FAILED, plan, tuple(executions), failure
                )

    try:
        validate_floor_plan(
            plan,
            tolerance=context.numeric.tolerance,
            require_no_placeholders=True,
        )
    except PostProcessingError as exc:
        failure = ProcessingFailure(exc.code, str(exc))
        return PostProcessingResult(
            PipelineStatus.FAILED, plan, tuple(executions), failure
        )
    return PostProcessingResult(PipelineStatus.SUCCESS, plan, tuple(executions))
