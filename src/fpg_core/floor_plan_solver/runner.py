from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from .config import FloorPlanSolverConfig
from .contracts import (
    FloorPlanSolveResult,
    SolverDiagnostics,
    SolverStatus,
)
from .extractor import extract_floor_plan
from .model import BuiltModel


def _map_status(status_code: int) -> SolverStatus:
    if status_code == cp_model.OPTIMAL:
        return SolverStatus.OPTIMAL
    if status_code == cp_model.FEASIBLE:
        return SolverStatus.FEASIBLE
    if status_code == cp_model.INFEASIBLE:
        return SolverStatus.INFEASIBLE
    if status_code == cp_model.MODEL_INVALID:
        return SolverStatus.MODEL_INVALID
    return SolverStatus.UNKNOWN


def _status_message(status: SolverStatus) -> str:
    messages = {
        SolverStatus.OPTIMAL: "CP-SAT found an optimal floor plan",
        SolverStatus.FEASIBLE: "CP-SAT found a feasible floor plan",
        SolverStatus.INFEASIBLE: "The selected configuration produced an infeasible model",
        SolverStatus.MODEL_INVALID: "OR-Tools rejected the generated CP-SAT model",
        SolverStatus.UNKNOWN: "The solver stopped without finding a feasible solution",
    }
    return messages[status]


def solve_built_model(
    built: BuiltModel,
    config: FloorPlanSolverConfig,
    *,
    collect_details: bool,
) -> tuple[FloorPlanSolveResult, SolverDiagnostics | None]:
    solver: Any = cp_model.CpSolver()
    solver_config = config.solver
    solver.parameters.max_time_in_seconds = float(solver_config.max_time_seconds)
    solver.parameters.num_search_workers = int(solver_config.num_search_workers)
    solver.parameters.log_search_progress = bool(solver_config.log_search_progress)
    solver.parameters.cp_model_presolve = bool(solver_config.cp_model_presolve)
    if solver_config.random_seed is not None:
        solver.parameters.random_seed = int(solver_config.random_seed)
    if solver_config.relative_gap_limit is not None:
        solver.parameters.relative_gap_limit = float(solver_config.relative_gap_limit)

    status_code = solver.Solve(built.context.model)
    status = _map_status(status_code)
    has_solution = status.has_solution

    floor_plan = extract_floor_plan(solver, built) if has_solution else None
    result = FloorPlanSolveResult(
        status=status,
        floor_plan=floor_plan,
        profile_name=config.name,
        message=_status_message(status),
    )
    if not collect_details:
        return result, None

    try:
        raw_status = solver.StatusName(status_code)
    except TypeError:  # compatibility with older OR-Tools versions
        raw_status = solver.StatusName()
    diagnostics = SolverDiagnostics(
        raw_status=str(raw_status),
        wall_time_seconds=float(solver.WallTime()),
        objective_value=(
            float(solver.ObjectiveValue())
            if has_solution and built.has_objective
            else None
        ),
        best_objective_bound=(
            float(solver.BestObjectiveBound())
            if has_solution and built.has_objective
            else None
        ),
        conflicts=int(solver.NumConflicts()),
        branches=int(solver.NumBranches()),
        applied_hard_constraints=built.applied_hard_constraints,
        applied_soft_constraints=built.applied_soft_constraints,
        penalty_terms=built.penalty_terms,
    )
    return result, diagnostics
