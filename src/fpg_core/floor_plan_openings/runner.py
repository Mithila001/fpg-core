from __future__ import annotations

from collections import Counter
from time import perf_counter
from typing import Any

from ortools.sat.python import cp_model

from ..domain import FloorPlan, OpeningPurpose, OpeningType, RoomId
from .config import FloorPlanOpeningsConfig
from .contracts import (
    OpeningDiagnostics,
    OpeningGenerationResult,
    OpeningGenerationStatus,
    OpeningIssue,
)
from .extractor import extract_floor_plan
from .model import BuiltOpeningModel
from .validation import validate_generated_floor_plan


def _map_status(status_code: object) -> OpeningGenerationStatus:
    if status_code == cp_model.OPTIMAL:
        return OpeningGenerationStatus.OPTIMAL
    if status_code == cp_model.FEASIBLE:
        return OpeningGenerationStatus.FEASIBLE
    if status_code == cp_model.INFEASIBLE:
        return OpeningGenerationStatus.INFEASIBLE
    if status_code == cp_model.MODEL_INVALID:
        return OpeningGenerationStatus.MODEL_INVALID
    return OpeningGenerationStatus.UNKNOWN


def _message(status: OpeningGenerationStatus) -> str:
    return {
        OpeningGenerationStatus.OPTIMAL: "CP-SAT found an optimal opening layout",
        OpeningGenerationStatus.FEASIBLE: "CP-SAT found a feasible opening layout",
        OpeningGenerationStatus.INFEASIBLE: "The opening configuration produced an infeasible model",
        OpeningGenerationStatus.MODEL_INVALID: "OR-Tools rejected the opening model",
        OpeningGenerationStatus.UNKNOWN: "The solver stopped without an opening solution",
        OpeningGenerationStatus.INVALID_INPUT: "The floor plan is invalid for opening generation",
    }[status]


def _issues(
    built: BuiltOpeningModel, solver: Any, solved: bool
) -> tuple[OpeningIssue, ...]:
    result: list[OpeningIssue] = []

    main_candidates = [
        item
        for item in built.context.all_variables
        if item.demand.opening_type is OpeningType.DOOR
        and item.demand.purpose is OpeningPurpose.MAIN_ENTRANCE
    ]
    if built.context.prepared.rooms_by_id and not main_candidates:
        result.append(
            OpeningIssue(
                "no_main_entrance_candidate",
                "No valid main-entrance candidate is available, so required room access cannot be satisfied",
            )
        )

    secondary_candidates = [
        item
        for item in built.context.all_variables
        if item.demand.purpose is OpeningPurpose.SECONDARY_ENTRANCE
    ]
    if built.context.prepared.rooms_by_id and not secondary_candidates:
        result.append(
            OpeningIssue(
                "no_secondary_entrance_candidate",
                "No kitchen or hallway exterior wall can fit a full-width secondary entrance with the configured clearance.",
            )
        )

    if not solved and main_candidates:
        reachable = {
            room_id for item in main_candidates for room_id in item.wall.room_ids
        }
        edges = [
            item.wall.room_ids
            for item in built.context.all_variables
            if item.demand.opening_type is OpeningType.DOOR
            and len(item.wall.room_ids) == 2
        ]
        while True:
            expanded = reachable | {
                room_id
                for edge in edges
                if reachable.intersection(edge)
                for room_id in edge
            }
            if expanded == reachable:
                break
            reachable = expanded
        for room_id, room in built.context.prepared.rooms_by_id.items():
            if (
                room.room_type in built.context.config.policy.required_access_room_types
                and room_id not in reachable
            ):
                result.append(
                    OpeningIssue(
                        "required_room_unreachable",
                        f"{room.name} ({room_id!s}) has no possible door route to a main entrance.",
                    )
                )
        if secondary_candidates and not any(
            item.wall.room_ids[0] in reachable for item in secondary_candidates
        ):
            result.append(
                OpeningIssue(
                    "secondary_entrance_unreachable",
                    "No secondary entrance candidate can connect to a main entrance through available interior doors.",
                )
            )

    required_types = set(built.context.config.policy.required_access_room_types)
    incident_candidate_rooms: set[RoomId] = set()
    for item in built.context.all_variables:
        if item.demand.opening_type is not OpeningType.DOOR:
            continue
        incident_candidate_rooms.update(item.wall.room_ids)
        incident_candidate_rooms.update(item.demand.room_ids)
    for room_id, room in built.context.prepared.rooms_by_id.items():
        if room.room_type in required_types and room_id not in incident_candidate_rooms:
            result.append(
                OpeningIssue(
                    "required_room_has_no_door_candidate",
                    f"Required-access room {room_id!s} has no valid door candidate",
                )
            )

    for demand in built.context.demands:
        variables = built.context.variables_by_demand.get(demand.id, ())
        if not variables:
            if demand.feature_id == "windows":
                room = built.context.prepared.rooms_by_id[demand.room_ids[0]]
                exterior = [
                    wall
                    for wall in built.context.prepared.walls
                    if wall.kind.value == "exterior" and room.id in wall.room_ids
                ]
                reason = (
                    "no exterior exposure"
                    if not exterior
                    else "insufficient exterior wall length for the configured window and minimum clearance"
                )
                result.append(
                    OpeningIssue(
                        "missing_window",
                        f"{room.name} ({room.id!s}): {reason}.",
                        demand.feature_id,
                        demand.id,
                    )
                )
                continue
            required = demand.purpose in {
                OpeningPurpose.MAIN_ENTRANCE,
                OpeningPurpose.SECONDARY_ENTRANCE,
            }
            result.append(
                OpeningIssue(
                    "no_required_candidate" if required else "no_candidate",
                    (
                        "No valid wall candidate was available for this required opening"
                        if required
                        else "No valid wall candidate was available for this optional opening"
                    ),
                    demand.feature_id,
                    demand.id,
                )
            )
            continue
        if solved:
            selected = [
                item for item in variables if solver.BooleanValue(item.selected)
            ]
            if not selected:
                result.append(
                    OpeningIssue(
                        "missing_window"
                        if demand.feature_id == "windows"
                        else "not_selected",
                        (
                            f"{built.context.prepared.rooms_by_id[demand.room_ids[0]].name} ({demand.room_ids[0]!s}): no window was selected because of competing placement constraints."
                            if demand.feature_id == "windows"
                            else "The shared model did not select this optional opening candidate"
                        ),
                        demand.feature_id,
                        demand.id,
                    )
                )
            for item in selected:
                if item.demand.feature_id == "windows":
                    room = built.context.prepared.rooms_by_id[item.wall.room_ids[0]]
                    policy = built.context.config.window_policy(room.room_type)
                    scale = built.context.prepared.scale
                    start = solver.Value(item.start) / scale
                    end = (item.wall.length - solver.Value(item.end)) / scale
                    if (
                        start < policy.preferred_clearance
                        or end < policy.preferred_clearance
                    ):
                        result.append(
                            OpeningIssue(
                                "reduced_preferred_clearance",
                                f"{room.name} ({room.id!s}): window preferred clearance {policy.preferred_clearance:g}; actual {start:g} and {end:g} project units.",
                                demand.feature_id,
                                demand.id,
                                item.wall.id,
                            )
                        )
                if item.demand.feature_id == "interior_doors":
                    door_policy = built.context.config.interior_doors.resolve(
                        tuple(
                            built.context.prepared.rooms_by_id[room_id].room_type
                            for room_id in item.wall.room_ids
                        )
                    )
                    scale = built.context.prepared.scale
                    start = solver.Value(item.start) / scale
                    end = (item.wall.length - solver.Value(item.end)) / scale
                    if (
                        start < door_policy.preferred_clearance
                        or end < door_policy.preferred_clearance
                    ):
                        names = ", ".join(
                            f"{built.context.prepared.rooms_by_id[room_id].name} ({room_id!s})"
                            for room_id in item.wall.room_ids
                        )
                        result.append(
                            OpeningIssue(
                                "reduced_preferred_clearance",
                                f"{names}: preferred door clearance {door_policy.preferred_clearance:g}; actual {start:g} and {end:g} project units.",
                                demand.feature_id,
                                demand.id,
                                item.wall.id,
                            )
                        )
                if item.option.undersized:
                    result.append(
                        OpeningIssue(
                            "undersized_exterior_door",
                            "Exterior door was reduced to fit the available legacy wall span",
                            demand.feature_id,
                            demand.id,
                            item.wall.id,
                        )
                    )
    return tuple(result)


def solve_opening_model(
    source: FloorPlan,
    built: BuiltOpeningModel,
    config: FloorPlanOpeningsConfig,
    *,
    collect_details: bool,
) -> tuple[OpeningGenerationResult, OpeningDiagnostics | None]:
    solver: Any = cp_model.CpSolver()
    solver_config = config.solver
    solver.parameters.max_time_in_seconds = float(solver_config.max_time_seconds)
    solver.parameters.num_search_workers = int(solver_config.num_search_workers)
    solver.parameters.random_seed = int(solver_config.random_seed)
    solver.parameters.cp_model_presolve = bool(solver_config.cp_model_presolve)
    solver.parameters.log_search_progress = bool(solver_config.log_search_progress)

    started = perf_counter()
    status_code = solver.Solve(built.context.model)
    if status_code == cp_model.OPTIMAL and built.has_objective:
        deficit = sum(
            solver.Value(value) if not isinstance(value, int) else value
            for value in built.clearance_deficits
        )
        remaining = float(solver_config.max_time_seconds) - (perf_counter() - started)
        if remaining > 0:
            built.context.model.Add(sum(built.clearance_deficits) == deficit)
            built.context.model.Maximize(built.secondary_objective)
            second = cp_model.CpSolver()
            second.parameters.num_search_workers = int(solver_config.num_search_workers)
            second.parameters.random_seed = int(solver_config.random_seed)
            second.parameters.cp_model_presolve = bool(solver_config.cp_model_presolve)
            second.parameters.log_search_progress = bool(
                solver_config.log_search_progress
            )
            second.parameters.max_time_in_seconds = remaining
            second_status = second.Solve(built.context.model)
            if second_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                solver, status_code = second, second_status
            else:
                status_code = cp_model.FEASIBLE
        else:
            status_code = cp_model.FEASIBLE
    elif status_code == cp_model.FEASIBLE:
        # The best clearance was not proven, so do not prioritize optional openings.
        pass
    status = _map_status(status_code)
    solved = status.has_solution
    floor_plan = None
    extraction_issue: OpeningIssue | None
    if solved:
        try:
            floor_plan = extract_floor_plan(source, solver, built)
            validate_generated_floor_plan(
                source, floor_plan, built.context.prepared, config
            )
        except Exception as exc:  # noqa: BLE001
            status = OpeningGenerationStatus.MODEL_INVALID
            solved = False
            floor_plan = None
            extraction_issue = OpeningIssue("extraction_failed", str(exc))
        else:
            extraction_issue = None
    else:
        extraction_issue = None

    result = OpeningGenerationResult(
        status=status,
        floor_plan=floor_plan,
        profile_name=config.name,
        message=_message(status),
    )
    if not collect_details:
        return result, None

    try:
        raw_status = solver.StatusName(status_code)
    except TypeError:
        raw_status = solver.StatusName()
    demand_counts = Counter(demand.feature_id for demand in built.context.demands)
    candidate_counts = Counter(
        demand.feature_id for demand in built.context.demands for _ in demand.options
    )
    selected_counts = Counter(
        item.demand.feature_id
        for item in built.context.all_variables
        if solved and solver.BooleanValue(item.selected)
    )
    issues = list(_issues(built, solver, solved))
    if extraction_issue is not None:
        issues.append(extraction_issue)
    diagnostics = OpeningDiagnostics(
        raw_status=str(raw_status),
        wall_time_seconds=float(solver.WallTime()),
        objective_value=(
            float(solver.ObjectiveValue())
            if status.has_solution and built.has_objective
            else None
        ),
        best_objective_bound=(
            float(solver.BestObjectiveBound())
            if status.has_solution and built.has_objective
            else None
        ),
        conflicts=int(solver.NumConflicts()),
        branches=int(solver.NumBranches()),
        analyzed_wall_count=len(built.context.prepared.walls),
        demand_counts=dict(demand_counts),
        candidate_counts=dict(candidate_counts),
        selected_counts=dict(selected_counts),
        applied_constraints=tuple(built.context.applied_constraints),
        objective_terms=tuple(built.context.objective_terms),
        issues=tuple(issues),
    )
    return result, diagnostics
