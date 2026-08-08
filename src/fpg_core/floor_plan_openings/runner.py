from __future__ import annotations

from collections import Counter
from typing import Any

from ortools.sat.python import cp_model

from ..domain import FloorPlan
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


def _map_status(status_code: int) -> OpeningGenerationStatus:
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


def _issues(built: BuiltOpeningModel, solver: Any, solved: bool) -> tuple[OpeningIssue, ...]:
    result: list[OpeningIssue] = []
    for demand in built.context.demands:
        variables = built.context.variables_by_demand.get(demand.id, ())
        if not variables:
            result.append(
                OpeningIssue(
                    "no_candidate",
                    "No valid wall candidate was available for this optional opening",
                    demand.feature_id,
                    demand.id,
                )
            )
            continue
        selected = [item for item in variables if solved and solver.BooleanValue(item.selected)]
        if not selected:
            result.append(
                OpeningIssue(
                    "not_selected",
                    "The shared model omitted this optional opening",
                    demand.feature_id,
                    demand.id,
                )
            )
        for item in selected:
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

    status_code = solver.Solve(built.context.model)
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
