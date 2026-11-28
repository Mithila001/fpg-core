"""Generate openings on a snapshot of a portable floor plan."""

from time import perf_counter

from fpg_lab.core.results import error_payload, result_document
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BSavedPlan, E02CRun
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter
from fpg_lab.integrations.fpg_core.floor_plan import decode_plan
from fpg_lab.services.common import SystemConfigurationService


def start(runtime, *, document=None, layout_id=None, configuration_id=None, regenerate=False):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting generation")
    if (document is None) == (layout_id is None):
        raise ValueError("Select one saved floor plan or import a temporary layout")
    with runtime.database.session_factory() as session:
        profile, validated = SystemConfigurationService(session, runtime.codec).for_flow(configuration_id, "e02c")
        layout_name = "Temporary import"
        if layout_id is not None:
            saved = session.get(E02BSavedPlan, layout_id)
            if saved is None:
                raise ValueError("The selected floor plan has been deleted")
            document, layout_name = saved.document, saved.name
        plan, _ = decode_plan(document)
        if document["project_units_per_meter"] != validated.payload["project_units_per_meter"]:
            raise ValueError("Floor-plan and configuration units must match")
        if plan.openings and not regenerate:
            raise ValueError("Select regeneration to replace existing openings")
        snapshot = {"input": to_jsonable(document), "layout_name": layout_name,
                    "configuration": validated.payload, "configuration_id": profile.id,
                    "configuration_hash": profile.config_hash, "core_version": runtime.codec.fpg_core_version,
                    "regenerate": bool(regenerate)}
        row = E02CRun(status="queued", snapshot=snapshot)
        session.add(row)
        session.commit()
        run_id = row.id
    try:
        runtime.jobs.submit_task(execute, runtime, run_id)
    except Exception as exc:
        with runtime.database.session_factory() as session:
            row = session.get(E02CRun, run_id)
            row.status, row.error = "failed", error_payload(exc, stage="job_submission")
            session.commit()
        raise
    return run_id


def execute(runtime, run_id):
    started = perf_counter()
    with runtime.database.session_factory() as session:
        row = session.get(E02CRun, run_id)
        if row is None or row.status != "queued":
            return
        row.status = "running"
        session.commit()
        snapshot = row.snapshot
    result = diagnostics = error = None
    try:
        plan, _ = decode_plan(snapshot["input"])
        if snapshot["regenerate"]:
            plan.openings.clear()
        config = runtime.codec.decode_for_flow(snapshot["configuration"], "e02c")
        execution = FpgCoreAdapter(config).generate_floor_plan_openings(plan, debug=True)
        data = result_document(execution)
        result, diagnostics = data["result"], data.get("details")
        if not execution.result.solved:
            raise RuntimeError(execution.result.message)
    except Exception as exc:
        error = error_payload(exc, stage="openings")
    with runtime.database.session_factory() as session:
        row = session.get(E02CRun, run_id)
        row.result, row.diagnostics, row.error = result, diagnostics, error
        row.duration_seconds = perf_counter() - started
        row.status = "failed" if error else "completed"
        session.commit()
