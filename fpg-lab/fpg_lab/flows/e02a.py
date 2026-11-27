"""Solver inspection using prepared hint maps and a saved profile."""
from dataclasses import replace
from math import isfinite
from time import perf_counter
from typing import Any

from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    SeedSource,
    generate_floor_plan,
)

from fpg_lab.core.results import error_payload, result_document
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models.e02 import E02Run
from fpg_lab.integrations.fpg_core.e02a_input import load_hint_maps, select_hint_maps
from fpg_lab.integrations.fpg_core.hint_map import candidate_hints, validate_export
from fpg_lab.integrations.fpg_core.solver import refinement_profile
from fpg_lab.services.common import SystemConfigurationService


def effective_profiles(config, initial_time_limit=None, random_seed=None):
    initial = config.floor_plan_solver.initial
    initial = replace(initial, seed=replace(
        initial.seed, source=SeedSource.CANDIDATE_HINTS, require_source=True, apply_hints=True
    ))
    initial = replace(initial, solver=replace(
        initial.solver,
        max_time_seconds=initial_time_limit if initial_time_limit is not None else initial.solver.max_time_seconds,
        random_seed=random_seed if random_seed is not None else initial.solver.random_seed,
    ))
    return initial, refinement_profile(config)


def prepare(runtime, selection, refinement_rounds=0, configuration_id=None, initial_time_limit=None, random_seed=None, retry_until_feasible=False, maximum_attempts=10):
    if isinstance(refinement_rounds, bool) or not isinstance(refinement_rounds, int) or not 0 <= refinement_rounds <= 5:
        raise ValueError("Refinement stage count must be an integer from 0 to 5")
    if initial_time_limit is not None and (isinstance(initial_time_limit, bool) or not isinstance(initial_time_limit, (int, float)) or not isfinite(initial_time_limit) or initial_time_limit <= 0):
        raise ValueError("Initial time limit must be positive and finite")
    if random_seed is not None and (type(random_seed) is not int or random_seed < 0):
        raise ValueError("Random seed must be a nonnegative integer")
    if type(retry_until_feasible) is not bool:
        raise ValueError("Retry until feasible must be a boolean")
    if retry_until_feasible and (isinstance(maximum_attempts, bool) or not isinstance(maximum_attempts, (int, float)) or not isfinite(maximum_attempts) or maximum_attempts < 1 or maximum_attempts % 1):
        raise ValueError("Maximum attempts must be a positive integer")
    with runtime.database.session_factory() as session:
        record, config = SystemConfigurationService(session, runtime.codec).for_flow(configuration_id, "e02a")
        profile_id, profile_hash = record.id, record.config_hash
    maps = select_hint_maps(load_hint_maps(), selection)
    for name, value in maps.items():
        if value["project_units_per_meter"] != config.payload["project_units_per_meter"]:
            raise ValueError(f"Hint map {name!r} uses different project units")
    return {"configuration_id": profile_id, "configuration": config.payload, "refinement_rounds": refinement_rounds,
            "configuration_hash": profile_hash, "core_version": config.fpg_core_version,
            "initial_time_limit": initial_time_limit, "random_seed": random_seed,
            "retry_until_feasible": retry_until_feasible, "maximum_attempts": int(maximum_attempts) if retry_until_feasible else 1,
            "effective_solver": to_jsonable(dict(zip(
                ("initial", "refinement"), effective_profiles(config.config, initial_time_limit, random_seed), strict=True
            ))), "maps": maps}


def start(runtime, selection, refinement_rounds=0, configuration_id=None, initial_time_limit=None, random_seed=None, retry_until_feasible=False, maximum_attempts=10):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting experiments")
    snapshot = prepare(runtime, selection, refinement_rounds, configuration_id, initial_time_limit, random_seed, retry_until_feasible, maximum_attempts)
    return _queue_snapshot(runtime, snapshot)


def retry(runtime, run_id):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting experiments")
    with runtime.database.session_factory() as session:
        previous = session.get(E02Run, run_id)
        if previous is None:
            raise ValueError(f"E02A run {run_id} was not found")
        snapshot = previous.snapshot
    runtime.codec.validate_for_flow(snapshot["configuration"], "e02a")
    rounds = snapshot["refinement_rounds"]
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 0 <= rounds <= 5:
        raise ValueError("Saved refinement stage count is invalid")
    if not snapshot["maps"]:
        raise ValueError("Saved run has no hint maps")
    for document in snapshot["maps"].values():
        validate_export(document)
    return _queue_snapshot(runtime, snapshot)


def _queue_snapshot(runtime, snapshot):
    with runtime.database.session_factory() as session:
        row = E02Run(status="queued", snapshot=snapshot, cases=[])
        session.add(row)
        session.commit()
        run_id = row.id
    try:
        runtime.jobs.submit_task(execute, runtime, run_id)
    except Exception as exc:
        with runtime.database.session_factory() as session:
            row = session.get(E02Run, run_id)
            row.status, row.error = "failed", error_payload(exc, stage="job_submission")
            session.commit()
        raise
    return run_id


def execute(runtime, run_id):
    def save(cases=None, status=None, error=None):
        with runtime.database.session_factory() as session:
            row = session.get(E02Run, run_id)
            if row.status == "termination_requested":
                raise InterruptedError("Termination requested")
            if cases is not None:
                row.cases = to_jsonable(cases)
            if status:
                row.status = status
            if error:
                row.error = error
            session.commit()

    cases: list[dict[str, Any]] = []
    try:
        with runtime.database.session_factory() as session:
            snapshot = session.get(E02Run, run_id).snapshot
        save(status="running")
        config = runtime.codec.decode_for_flow(snapshot["configuration"], "e02a")
        initial, refine = effective_profiles(config, snapshot.get("initial_time_limit"), snapshot.get("random_seed"))
        config = replace(config, floor_plan_solver=replace(config.floor_plan_solver, initial=initial, refinement_a=refine))
        adapter = runtime.adapter_factory(config)
        for name, hint_map in snapshot["maps"].items():
            save(cases)
            case = {"name": name, "status": "running", "stages": [], "scoring": None, "error": None}
            cases.append(case)
            started = perf_counter()
            stage = "initial"
            try:
                spec = validate_export(hint_map)
                hints = candidate_hints(hint_map)
                def record(label, action, *args, current_case=case, **kwargs):
                    save(cases)
                    begin = perf_counter()
                    result = action(*args, **kwargs)
                    current_case["stages"].append({"name": label, "data": result_document(result), "duration_ms": int((perf_counter()-begin)*1000)})
                    save(cases)
                    return result
                attempts = snapshot.get("maximum_attempts", 1) if snapshot.get("retry_until_feasible") else 1
                for attempt in range(1, attempts + 1):
                    case["current_attempt"] = attempt
                    solver = initial.solver
                    if snapshot.get("retry_until_feasible"):
                        solver = replace(solver, random_seed=((solver.random_seed or 0) + attempt - 1) % 2147483647)
                    attempt_config = replace(initial, solver=solver)
                    save(cases)
                    begin = perf_counter()
                    execution = generate_floor_plan(FloorPlanSolveRequest(specification=spec, config=attempt_config, candidate_hints=hints), mode=adapter.execution_mode(debug=True))
                    if execution.result.solved:
                        case["stages"].append({"name": "Initial", "data": result_document(execution), "duration_ms": int((perf_counter()-begin)*1000)})
                        save(cases)
                        break
                case.pop("current_attempt", None)
                if not execution.result.solved:
                    raise RuntimeError(f"{execution.result.status.value}: {execution.result.message}")
                plan = execution.result.floor_plan
                for index in range(snapshot["refinement_rounds"]):
                    stage = f"refinement_{index + 1}"
                    execution = record(f"Refinement {index + 1}", adapter.refine_floor_plan, spec, plan, profile="refinement_a", debug=True)
                    if not execution.result.solved:
                        raise RuntimeError(f"{execution.result.status.value}: {execution.result.message}")
                    plan = execution.result.floor_plan
                stage = "post_processing"
                execution = record("Post-process", adapter.post_process_floor_plan, spec, plan, solver_config=refine if snapshot["refinement_rounds"] else attempt_config, debug=True)
                if getattr(execution.result.status, "value", execution.result.status) != "success":
                    raise RuntimeError(str(execution.result.failure))
                plan = execution.result.floor_plan
                stage = "scoring"
                save(cases)
                case["scoring"] = result_document(adapter.score_completed_floor_plan(plan, spec, debug=True))
                case["status"] = "completed"
            except InterruptedError:
                case["status"] = "terminated"
                raise
            except Exception as exc:
                case["status"], case["error"] = "failed", error_payload(exc, stage=stage)
            finally:
                case["duration_ms"] = int((perf_counter()-started)*1000)
            save(cases)
        save(cases, "completed")
    except InterruptedError:
        with runtime.database.session_factory() as session:
            row = session.get(E02Run, run_id)
            row.status, row.cases = "terminated", to_jsonable(cases)
            session.commit()
    except Exception as exc:
        with runtime.database.session_factory() as session:
            row = session.get(E02Run, run_id)
            row.status, row.cases, row.error = "failed", to_jsonable(cases), error_payload(exc, stage="setup")
            session.commit()
