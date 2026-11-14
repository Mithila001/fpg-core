"""File-backed solver inspection runs."""
import json
from dataclasses import replace
from time import perf_counter

from sqlalchemy import select, update
from fpg_core.floor_plan_solver import FloorPlanSolveRequest, RoomPlacementHint, SeedSource, generate_floor_plan

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import ROOT
from fpg_lab.database.models.e02 import E02Run
from fpg_lab.flows.p01 import error_payload, result_document
from fpg_lab.integrations.fpg_core.p01b_input import validate_export
from fpg_lab.integrations.fpg_core.e02a_input import load_hint_maps, select_hint_maps

CONFIG_PATH = ROOT / "experiments" / "e02a" / "config.json"


def prepare(codec, selection, refinement_rounds=0):
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load {CONFIG_PATH}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"configuration"}:
        raise ValueError("Configuration requires a configuration object")
    if isinstance(refinement_rounds, bool) or not isinstance(refinement_rounds, int) or not 0 <= refinement_rounds <= 5:
        raise ValueError("Refinement stage count must be an integer from 0 to 5")
    config = codec.validate_for_flow(data["configuration"], "p01b")
    maps = select_hint_maps(load_hint_maps(), selection)
    for name, value in maps.items():
        if value["project_units_per_meter"] != config.payload["project_units_per_meter"]:
            raise ValueError(f"Hint map {name!r} uses different project units")
    return {"configuration_file": data, "configuration": config.payload, "refinement_rounds": refinement_rounds,
            "configuration_hash": codec.hash_payload({"configuration": config.payload, "refinement_rounds": refinement_rounds}), "core_version": config.fpg_core_version,
            "maps": maps}


def start(runtime, selection, refinement_rounds=0):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting experiments")
    snapshot = prepare(runtime.codec, selection, refinement_rounds)
    return _queue_snapshot(runtime, snapshot)


def retry(runtime, run_id):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting experiments")
    with runtime.database.session_factory() as session:
        previous = session.get(E02Run, run_id)
        if previous is None:
            raise ValueError(f"E02A run {run_id} was not found")
        snapshot = previous.snapshot
    runtime.codec.validate_for_flow(snapshot["configuration"], "p01b")
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

    cases = []
    try:
        with runtime.database.session_factory() as session:
            snapshot = session.get(E02Run, run_id).snapshot
        save(status="running")
        config = runtime.codec.decode_for_flow(snapshot["configuration"], "p01b")
        initial = config.floor_plan_solver.initial
        refine = config.floor_plan_solver.refinement_a
        initial = replace(initial, seed=replace(initial.seed, source=SeedSource.CANDIDATE_HINTS, require_source=True, apply_hints=True))
        refine = replace(refine, seed=replace(refine.seed, source=SeedSource.EXISTING_FLOOR_PLAN, require_source=True))
        config = replace(config, floor_plan_solver=replace(config.floor_plan_solver, initial=initial, refinement_a=refine))
        adapter = runtime.adapter_factory(config)
        with runtime.database.session_factory() as session:
            row = session.get(E02Run, run_id)
            row.snapshot = {**snapshot, "effective_solver": to_jsonable({"initial": initial, "refinement": refine})}
            session.commit()
        for name, hint_map in snapshot["maps"].items():
            save(cases)
            case = {"name": name, "status": "running", "stages": [], "scoring": None, "error": None}
            cases.append(case)
            started = perf_counter()
            stage = "initial"
            try:
                spec = validate_export(hint_map)
                hints = tuple(RoomPlacementHint(room_id=p["room_id"], x=p["x"], y=p["y"]) for p in hint_map["candidate"]["points"])
                def record(label, action):
                    save(cases)
                    begin = perf_counter()
                    result = action()
                    case["stages"].append({"name": label, "data": result_document(result), "duration_ms": int((perf_counter()-begin)*1000)})
                    save(cases)
                    return result
                execution = record("Initial", lambda: generate_floor_plan(FloorPlanSolveRequest(specification=spec, config=initial, candidate_hints=hints), mode=adapter.execution_mode(debug=True)))
                if not execution.result.solved:
                    raise RuntimeError(f"{execution.result.status.value}: {execution.result.message}")
                plan = execution.result.floor_plan
                for index in range(snapshot["refinement_rounds"]):
                    stage = f"refinement_{index + 1}"
                    execution = record(f"Refinement {index + 1}", lambda: adapter.refine_floor_plan(spec, plan, profile="refinement_a", debug=True))
                    if not execution.result.solved:
                        raise RuntimeError(f"{execution.result.status.value}: {execution.result.message}")
                    plan = execution.result.floor_plan
                stage = "post_processing"
                execution = record("Post-process", lambda: adapter.post_process_floor_plan(spec, plan, debug=True))
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
