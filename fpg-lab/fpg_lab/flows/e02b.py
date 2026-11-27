"""Run the official scoring pipeline and retain an isolated diagnostic snapshot."""

from time import perf_counter

from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring import (
    FloorPlanScoringInput,
    diagnose_skipped_evaluators,
    score_floor_plan,
)

from fpg_lab.core.results import error_payload, result_document
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BRun, E02BSavedPlan
from fpg_lab.integrations.fpg_core.e02b_input import decode_plan
from fpg_lab.services.common import SystemConfigurationService


def save_layout(session, name, document):
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("Enter a floor-plan name of 1 to 120 characters")
    decode_plan(document)
    row = E02BSavedPlan(name=name, document=to_jsonable(document))
    session.add(row)
    session.commit()
    return row.id


def delete_layout(session, layout_id):
    row = session.get(E02BSavedPlan, layout_id)
    if row is not None:
        session.delete(row)
        session.commit()


def start(runtime, *, document=None, layout_id=None, configuration_id=None):
    if not runtime._started or runtime._closed:
        raise RuntimeError("Start the Lab runtime before submitting evaluations")
    if (document is None) == (layout_id is None):
        raise ValueError("Select one saved floor plan or import a temporary layout")
    with runtime.database.session_factory() as session:
        profile, validated = SystemConfigurationService(session, runtime.codec).for_flow(configuration_id, "e02b")
        layout_name = "Temporary import"
        if layout_id is not None:
            saved = session.get(E02BSavedPlan, layout_id)
            if saved is None:
                raise ValueError("The selected floor plan has been deleted")
            document, layout_name = saved.document, saved.name
        decode_plan(document)
        snapshot = {
            "input": to_jsonable(document),
            "layout_name": layout_name,
            "configuration": validated.payload["floor_plan_scoring"],
            "configuration_id": profile.id,
            "configuration_hash": profile.config_hash,
            "core_version": runtime.codec.fpg_core_version,
        }
        row = E02BRun(status="queued", snapshot=snapshot)
        session.add(row)
        session.commit()
        run_id = row.id
    try:
        runtime.jobs.submit_task(execute, runtime, run_id)
    except Exception as exc:
        with runtime.database.session_factory() as session:
            row = session.get(E02BRun, run_id)
            row.status, row.error = "failed", error_payload(exc, stage="job_submission")
            session.commit()
        raise
    return run_id


def execute(runtime, run_id):
    started = perf_counter()
    with runtime.database.session_factory() as session:
        row = session.get(E02BRun, run_id)
        if row is None or row.status != "queued":
            return
        row.status = "running"
        session.commit()
        snapshot = row.snapshot

    stage = "official_scoring"
    official = diagnostics = error = None
    try:
        plan, specification = decode_plan(snapshot["input"])
        request = FloorPlanScoringInput(
            plan, specification, runtime.codec.decode_floor_scoring(snapshot["configuration"])
        )
        execution = score_floor_plan(request, mode=ExecutionMode.DEBUG)
        official = result_document(execution)
        stage = "diagnostics"
        diagnostics = to_jsonable(diagnose_skipped_evaluators(request, execution))
    except Exception as exc:
        error = error_payload(exc, stage=stage)

    with runtime.database.session_factory() as session:
        row = session.get(E02BRun, run_id)
        row.official, row.diagnostics, row.error = official, diagnostics, error
        row.duration_seconds = perf_counter() - started
        row.status = "failed" if error else "completed"
        session.commit()
