from __future__ import annotations

import copy
import math
from dataclasses import replace
from time import perf_counter

from ..domain import ExecutionMode, FloorPlan, RoomType
from .config import GridSnapConfig, HallwayMergeConfig, WallExtensionConfig
from .contracts import (
    PipelineStatus,
    PostProcessingContext,
    PostProcessingDetails,
    PostProcessingRequest,
    PostProcessingResult,
    ProcessingFailure,
    ProcessorExecution,
    ProcessorOutcome,
    ProcessorStatus,
)
from .exceptions import ConfigurationError, PostProcessingError, RollbackError
from .registry import ProcessorRegistry
from .validation import validate_config, validate_floor_plan


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
    validate_config(request.config)
    seen: set[str] = set()
    for use in request.config.processors:
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
        and (not math.isfinite(config.grid_size) or config.grid_size <= 0)
    ):
        raise ConfigurationError("grid size must be positive")
    if isinstance(config, HallwayMergeConfig) and (
        not math.isfinite(config.minimum_shared_wall) or config.minimum_shared_wall < 0
    ):
        raise ConfigurationError("minimum shared-wall length cannot be negative")
    if isinstance(config, WallExtensionConfig):
        room_types = [rule.room_type for rule in config.rules]
        if any(not isinstance(room_type, RoomType) for room_type in room_types):
            raise ConfigurationError(
                "wall-extension room types must be RoomType members"
            )
        if len(room_types) != len(set(room_types)):
            raise ConfigurationError("wall-extension room types must be unique")
        if any(
            not math.isfinite(rule.max_distance) or rule.max_distance <= 0
            for rule in config.rules
        ):
            raise ConfigurationError(
                "wall-extension distances must be finite and positive"
            )
        directions = [policy.direction for policy in config.exterior_steps]
        if len(set(directions)) != 4 or set(directions) != {
            "front",
            "back",
            "left",
            "right",
        }:
            raise ConfigurationError(
                "exterior step policies must cover each direction once"
            )
        for policy in config.exterior_steps:
            if (
                not math.isfinite(policy.minimum_depth)
                or policy.minimum_depth < 0
                or not math.isfinite(policy.minimum_segment_length)
                or policy.minimum_segment_length < 0
                or type(policy.preferred_max_steps) is not int
                or policy.preferred_max_steps < 0
            ):
                raise ConfigurationError("invalid exterior step policy")
        positive = (
            config.max_recess_ratio,
            config.min_contact_length,
            config.min_residual_edge,
            config.min_extension_width,
            config.min_extension_depth,
            config.hallway_min_extension_width,
            config.hallway_min_extension_depth,
        )
        nonnegative = (
            config.min_pocket_area,
            config.max_area_excess,
            config.max_width_excess,
        )
        if (
            any(not math.isfinite(value) or value <= 0 for value in positive)
            or any(not math.isfinite(value) or value < 0 for value in nonnegative)
            or any(
                type(value) is not int or value < 1
                for value in (
                    config.max_recess_levels,
                    config.max_iterations,
                    config.max_candidate_evaluations,
                )
            )
        ):
            raise ConfigurationError("invalid wall-extension settings")
        if (
            not isinstance(config.transformation_version, str)
            or not config.transformation_version.strip()
        ):
            raise ConfigurationError(
                "wall-extension transformation version cannot be empty"
            )


def run_pipeline(
    request: PostProcessingRequest,
    registry: ProcessorRegistry,
    *,
    mode: ExecutionMode,
) -> tuple[PostProcessingResult, PostProcessingDetails | None]:
    plan = request.floor_plan
    collect_details = mode is ExecutionMode.DEBUG
    executions: list[ProcessorExecution] = []
    try:
        _preflight(request, registry)
        validate_floor_plan(
            plan,
            tolerance=request.config.numeric.tolerance,
            reject_openings=request.config.reject_existing_openings,
        )
    except Exception as exc:  # noqa: BLE001
        code = exc.code if isinstance(exc, PostProcessingError) else "invalid_request"
        failure = ProcessingFailure(code, str(exc))
        return (
            PostProcessingResult(PipelineStatus.FAILED, plan, failure),
            PostProcessingDetails(()) if collect_details else None,
        )

    context = PostProcessingContext(
        mode=mode,
        specification=request.specification,
        floor_boundary=plan.boundary,
        numeric=request.config.numeric,
        profile_name=request.config.name,
        solver_config=request.solver_config,
    )
    unsuccessful: set[str] = set()

    for use in request.config.processors:
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
            if collect_details:
                executions.append(
                    ProcessorExecution(
                        use.processor_id,
                        ProcessorStatus.SKIPPED,
                        0.0,
                        failure=failure,
                    )
                )
            unsuccessful.add(use.processor_id)
            continue

        applicable, reason = processor.is_applicable(plan, context, use.config)
        if not applicable:
            outcome = ProcessorOutcome(ProcessorStatus.NOT_APPLICABLE, reason)
            if collect_details:
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
        started = perf_counter() if collect_details else None
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
            if (
                isinstance(use.config, GridSnapConfig)
                and use.config.grid_size is not None
            ):
                context = replace(
                    context,
                    numeric=replace(context.numeric, grid_size=use.config.grid_size),
                )
            if collect_details:
                assert started is not None
                duration = (perf_counter() - started) * 1000
                executions.append(
                    ProcessorExecution(
                        use.processor_id, outcome.status, duration, outcome=outcome
                    )
                )
        except Exception as exc:  # noqa: BLE001
            duration = 0.0
            if collect_details:
                assert started is not None
                duration = (perf_counter() - started) * 1000
            try:
                _restore(plan, snapshot)
            except RollbackError as rollback_exc:
                failure = ProcessingFailure(
                    rollback_exc.code, str(rollback_exc), use.processor_id
                )
                if collect_details:
                    executions.append(
                        ProcessorExecution(
                            use.processor_id,
                            ProcessorStatus.FAILED,
                            duration,
                            failure=failure,
                        )
                    )
                return (
                    PostProcessingResult(PipelineStatus.FAILED, plan, failure),
                    PostProcessingDetails(tuple(executions))
                    if collect_details
                    else None,
                )
            code = (
                exc.code
                if isinstance(exc, PostProcessingError)
                else "unexpected_processor_error"
            )
            failure = ProcessingFailure(code, str(exc), use.processor_id)
            if collect_details:
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
                return (
                    PostProcessingResult(PipelineStatus.FAILED, plan, failure),
                    PostProcessingDetails(tuple(executions))
                    if collect_details
                    else None,
                )

    try:
        validate_floor_plan(
            plan,
            tolerance=context.numeric.tolerance,
            require_no_placeholders=True,
        )
    except PostProcessingError as exc:
        failure = ProcessingFailure(exc.code, str(exc))
        return (
            PostProcessingResult(PipelineStatus.FAILED, plan, failure),
            PostProcessingDetails(tuple(executions)) if collect_details else None,
        )
    return (
        PostProcessingResult(PipelineStatus.SUCCESS, plan),
        PostProcessingDetails(tuple(executions)) if collect_details else None,
    )
