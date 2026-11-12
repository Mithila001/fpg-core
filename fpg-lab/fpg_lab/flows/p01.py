from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import P01CandidateTrial, P01Experiment, P01FloorPlanRun
from fpg_lab.database.session import Database
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter, FpgCoreCandidateRejected

ACTIVE_STATUSES = ("queued", "running", "termination_requested")


def score_candidate(adapter, specification, circulation, *, debug):
    scoring = adapter.score_candidate(specification, circulation, debug=debug)
    return scoring, adapter.final_score(scoring)


def utc_now() -> datetime:
    return datetime.now(UTC)


def error_payload(
    exc: BaseException, *, stage: str, rejected: bool = False, code: str | None = None
) -> dict[str, Any]:
    cause = exc.__cause__ if exc.__cause__ is not None else exc
    raw_code = code or getattr(cause, "code", None)
    raw_details = getattr(cause, "details", None)
    try:
        details = to_jsonable(raw_details)
    except (TypeError, ValueError) as serialization_error:
        details = {"serialization_error": str(serialization_error)}
    source = (
        "fpg_core"
        if type(cause).__module__.startswith("fpg_core")
        or type(exc).__module__.startswith("fpg_lab.integrations.fpg_core")
        else "lab"
    )
    payload = {
        "stage": stage,
        "source": source,
        "type": type(exc).__name__,
        "message": str(exc),
        "code": getattr(raw_code, "value", raw_code),
        "details": details,
        "cause_type": type(cause).__name__
        if cause is not exc
        else getattr(exc, "cause_type", None),
        "rejected": rejected,
    }
    return payload


def result_document(value: Any) -> dict[str, Any]:
    document = to_jsonable(value)
    if not isinstance(document, dict):
        raise TypeError("A stage result must serialize to a JSON object")
    return document


def search_trial_document(trial: Any) -> dict[str, Any]:
    value = {
        "trial_no": trial.trial_no,
        "core_trial_no": trial.core_trial_no,
        "grid": trial.grid,
        "points": trial.points,
        "recorded_result": trial.result,
    }
    return result_document(value)


def recover_interrupted_experiments(session: Session) -> int:
    from fpg_lab.database.models import P01BIteration

    session.execute(
        update(P01BIteration)
        .where(P01BIteration.status == "running")
        .values(
            status="interrupted",
            error={"stage": "runtime", "message": "Lab stopped before this iteration finished."},
        )
    )
    result = cast(
        CursorResult[Any],
        session.execute(
            update(P01Experiment)
            .where(P01Experiment.status.in_(ACTIVE_STATUSES))
            .values(
                status="interrupted",
                stop_reason="lab_restart",
                finished_at=utc_now(),
                error_data={
                    "stage": "runtime",
                    "source": "lab",
                    "type": "LabRestart",
                    "message": "The Lab stopped before this experiment finished.",
                    "code": "lab_restart",
                    "details": None,
                    "cause_type": None,
                    "rejected": False,
                },
            )
        ),
    )
    session.execute(
        update(P01FloorPlanRun)
        .where(P01FloorPlanRun.status == "running")
        .values(
            status="interrupted",
            finished_at=utc_now(),
            error_data={
                "stage": "runtime",
                "source": "lab",
                "type": "LabRestart",
                "message": "The Lab stopped before this floor-plan run finished.",
                "code": "lab_restart",
                "details": None,
                "cause_type": None,
                "rejected": False,
            },
        )
    )
    session.commit()
    return int(result.rowcount or 0)


class PipelineTerminated(RuntimeError):
    pass


class StructuredStageFailure(RuntimeError):
    def __init__(self, stage: str, code: str, message: str) -> None:
        self.stage = stage
        self.code = code
        super().__init__(message)


class P01FlowRunner:
    def __init__(
        self,
        database: Database,
        config_codec: Any,
        adapter_factory: Callable[[Any], FpgCoreAdapter] = FpgCoreAdapter,
    ) -> None:
        self.database = database
        self.config_codec = config_codec
        self.adapter_factory = adapter_factory

    def run(self, experiment_id: int, flow_type: str | None = None) -> None:
        with self.database.session_factory() as session:
            experiment = session.get(P01Experiment, experiment_id)
            if experiment is None or (flow_type is not None and experiment.flow_type != flow_type):
                return
            if experiment.status == "termination_requested":
                self._finish_terminated(session, experiment)
                return
            if experiment.status != "queued":
                return
            experiment.status = "running"
            experiment.started_at = utc_now()
            experiment.stop_reason = None
            session.commit()
            if experiment.flow_type in ("p01b", "p01c"):
                from fpg_lab.flows.p01b import run_p01b

                run_p01b(self, session, experiment)
            else:
                self._run_candidate_flow(session, experiment)

    def _initialize(
        self, session: Session, experiment: P01Experiment
    ) -> tuple[FpgCoreAdapter, Any, Any]:
        configuration = self.config_codec.decode_for_flow(
            experiment.system_configuration_snapshot,
            experiment.flow_type,
        )
        adapter = self.adapter_factory(configuration)
        execution = adapter.preprocess(
            experiment.floor_plan_request, debug=experiment.persist_trial_data
        )
        if experiment.persist_trial_data:
            experiment.preprocessing_result = result_document(execution)
            session.commit()
        return adapter, execution.result, execution

    def _run_candidate_flow(self, session: Session, experiment: P01Experiment) -> None:
        try:
            adapter, prepared, _ = self._initialize(session, experiment)
            specification = prepared.generation_spec
            search = adapter.create_candidate_search(
                prepared, trial_count=experiment.requested_trial_count or 0
            )
        except Exception as exc:
            self._finish_failed(session, experiment, error_payload(exc, stage="preprocessing"))
            return

        while (
            experiment.completed_trial_count < (experiment.requested_trial_count or 0)
            and search.has_remaining_trials
        ):
            if self._termination_requested(experiment.id):
                self._finish_terminated(session, experiment)
                return
            started = perf_counter()
            trial = None
            candidate_data = circulation_data = scoring_data = None
            try:
                trial = search.ask()
                candidate_data = search_trial_document(trial)
                if self._termination_requested(experiment.id):
                    search.fail_pending()
                    self._store_trial(
                        session,
                        experiment,
                        trial.trial_no,
                        "terminated",
                        started,
                        candidate_data=candidate_data,
                    )
                    self._finish_terminated(session, experiment)
                    return
                try:
                    circulation = adapter.run_circulation(
                        trial.candidate, debug=experiment.persist_trial_data
                    )
                except FpgCoreCandidateRejected as exc:
                    search.record_score(trial, 0.0)
                    candidate_data = search_trial_document(trial)
                    self._record_completed_trial(
                        session,
                        experiment,
                        trial.trial_no,
                        started,
                        0.0,
                        candidate_data,
                        None,
                        None,
                        error_payload(exc, stage="candidate_circulation", rejected=True),
                    )
                    continue
                circulation_data = result_document(circulation)
                if self._termination_requested(experiment.id):
                    search.fail_pending()
                    self._store_trial(
                        session,
                        experiment,
                        trial.trial_no,
                        "terminated",
                        started,
                        candidate_data=candidate_data,
                        circulation_data=circulation_data,
                    )
                    self._finish_terminated(session, experiment)
                    return
                if experiment.persist_trial_data and experiment.flow_type == "p01a":
                    circulation_data["lab_final_routing"] = to_jsonable(
                        adapter.final_circulation_routing(circulation)
                    )
                    # Keep the specification paired with the cleaned candidate, including
                    # the hallway identities selected by circulation.
                    try:
                        circulation_data["lab_generation_specification"] = to_jsonable(
                            adapter.generation_specification_for_candidate(
                                prepared, circulation.result.candidate
                            )
                        )
                    except Exception as exc:
                        circulation_data["lab_generation_specification_error"] = str(exc)
                scoring, final_score = score_candidate(
                    adapter, specification, circulation, debug=experiment.persist_trial_data
                )
                scoring_data = result_document(scoring)
                search.record_score(trial, final_score)
                candidate_data = search_trial_document(trial)
                self._record_completed_trial(
                    session,
                    experiment,
                    trial.trial_no,
                    started,
                    final_score,
                    candidate_data,
                    circulation_data,
                    scoring_data,
                    None,
                )
                if self._termination_requested(experiment.id):
                    self._finish_terminated(session, experiment)
                    return
            except PipelineTerminated:
                self._finish_terminated(session, experiment)
                return
            except Exception as exc:
                search.fail_pending()
                experiment.completed_trial_count += 1
                experiment.failed_trial_count += 1
                self._store_trial(
                    session,
                    experiment,
                    trial.trial_no if trial else experiment.completed_trial_count,
                    "failed",
                    started,
                    candidate_data=candidate_data,
                    circulation_data=circulation_data,
                    scoring_data=scoring_data,
                    error=error_payload(exc, stage="candidate_trial"),
                )
                session.commit()

        if self._termination_requested(experiment.id):
            self._finish_terminated(session, experiment)
        elif experiment.successful_trial_count == 0:
            self._finish_failed(
                session,
                experiment,
                error_payload(
                    RuntimeError("No candidate trial produced a score."),
                    stage="experiment",
                    code="no_recorded_scores",
                ),
                stop_reason="no_recorded_scores",
            )
        else:
            experiment.status = "completed"
            experiment.stop_reason = (
                "trial_count_reached"
                if experiment.completed_trial_count >= (experiment.requested_trial_count or 0)
                else "candidate_search_exhausted"
            )
            experiment.finished_at = utc_now()
            session.commit()

    def _record_completed_trial(
        self,
        session: Session,
        experiment: P01Experiment,
        trial_no: int,
        started: float,
        final_score: float,
        candidate_data: dict[str, Any],
        circulation_data: dict[str, Any] | None,
        scoring_data: dict[str, Any] | None,
        error: dict[str, Any] | None,
    ) -> P01CandidateTrial | None:
        experiment.completed_trial_count += 1
        experiment.successful_trial_count += 1
        if experiment.best_candidate_score is None or final_score > experiment.best_candidate_score:
            experiment.best_candidate_score = final_score
            experiment.best_trial_no = trial_no
        should_store = experiment.persist_trial_data
        row = None
        if should_store:
            row = self._store_trial(
                session,
                experiment,
                trial_no,
                "completed",
                started,
                candidate_data=candidate_data if experiment.persist_trial_data else None,
                circulation_data=circulation_data if experiment.persist_trial_data else None,
                scoring_data=scoring_data if experiment.persist_trial_data else None,
                final_score=final_score,
                error=error,
            )
        session.commit()
        return row

    def _store_trial(
        self,
        session: Session,
        experiment: P01Experiment,
        trial_no: int,
        status: str,
        started: float,
        *,
        candidate_data: dict[str, Any] | None = None,
        circulation_data: dict[str, Any] | None = None,
        scoring_data: dict[str, Any] | None = None,
        final_score: float | None = None,
        error: dict[str, Any] | None = None,
    ) -> P01CandidateTrial | None:
        if not experiment.persist_trial_data and experiment.flow_type == "p01a":
            return None
        row = P01CandidateTrial(
            experiment_id=experiment.id,
            trial_no=trial_no,
            status=status,
            candidate_search_data=candidate_data,
            circulation_data=circulation_data,
            candidate_scoring_data=scoring_data,
            final_score=final_score,
            error_data=error,
            duration_ms=round((perf_counter() - started) * 1000),
            finished_at=utc_now(),
        )
        session.add(row)
        session.commit()
        return row

    def _termination_requested(self, experiment_id: int) -> bool:
        with self.database.session_factory() as check_session:
            return (
                check_session.scalar(
                    select(P01Experiment.status).where(P01Experiment.id == experiment_id)
                )
                == "termination_requested"
            )

    def _check_termination(self, experiment_id: int) -> None:
        if self._termination_requested(experiment_id):
            raise PipelineTerminated()

    @staticmethod
    def _finish_terminated(session: Session, experiment: P01Experiment) -> None:
        session.refresh(experiment)
        experiment.status = "terminated"
        experiment.stop_reason = "termination_requested"
        experiment.finished_at = utc_now()
        session.commit()

    @staticmethod
    def _finish_failed(
        session: Session,
        experiment: P01Experiment,
        error: dict[str, Any],
        *,
        stop_reason: str = "execution_failed",
    ) -> None:
        experiment.status = "failed"
        experiment.stop_reason = stop_reason
        experiment.error_data = error
        experiment.finished_at = utc_now()
        session.commit()
