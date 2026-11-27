"""Application resources and execution; importing this module never imports NiceGUI."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from copy import deepcopy
from threading import Event, Lock
from typing import Any

from sqlalchemy import select, update

from fpg_lab.core.exceptions import AppError, InvalidInputError
from fpg_lab.core.results import error_payload
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import get_settings
from fpg_lab.database.maintenance import execution_lock, require_current
from fpg_lab.database.models import E02BRun, E02Run, P01Experiment
from fpg_lab.database.models.common import utc_now
from fpg_lab.database.session import Database
from fpg_lab.flows.p01 import (
    ACTIVE_STATUSES,
    P01FlowRunner,
    recover_interrupted_experiments,
)
from fpg_lab.inputs import FloorPlanRequest, ManualHints, P01AInput, P01BInput, P01CInput
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.services.p01a import P01AService
from fpg_lab.services.p01b import P01BService
from fpg_lab.services.p01c import P01CService
from fpg_lab.workers.executor import BackgroundExecutor

FLOW_INPUTS = {"p01a": P01AInput, "p01b": P01BInput, "p01c": P01CInput}
FLOW_SERVICES: dict[str, Any] = {"p01a": P01AService, "p01b": P01BService, "p01c": P01CService}


class LabRuntime:
    def __init__(
        self,
        *,
        database_url: str | None = None,
        codec: Any | None = None,
        adapter_factory: Callable[[Any], Any] = FpgCoreAdapter,
        max_workers: int | None = None,
    ) -> None:
        settings = get_settings()
        self.database = Database(database_url or settings.database_url)
        self.codec = codec or CoreConfigCodec()
        self.adapter_factory = adapter_factory
        self.runner = P01FlowRunner(self.database, self.codec, adapter_factory)
        self.jobs = BackgroundExecutor(
            self.runner, max_workers=max_workers or settings.max_background_workers
        )
        self._execution = ExitStack()
        self._started = False
        self._closed = False
        self._quick_cancels: set[Event] = set()
        self._quick_lock = Lock()

    def start_quick_hint(
        self, template_id: int, configuration_id: int, count: int, threshold: float
    ):
        from math import isfinite

        from fpg_lab.database.models import FloorPlanTemplate
        from fpg_lab.flows.quick_hint import search_hint_map

        if not self._started or self._closed:
            raise RuntimeError("Start the Lab runtime before submitting searches")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100_000:
            raise ValueError("Trial count must be an integer between 1 and 100000")
        if not isfinite(threshold) or not 0 <= threshold <= 100:
            raise ValueError("Required score must be between 0 and 100")
        with self.database.session_factory() as session:
            template = session.get(FloorPlanTemplate, template_id)
            if template is None:
                raise ValueError("Select an existing template")
            config, validated = SystemConfigurationService(session, self.codec).for_flow(
                configuration_id, "p01a"
            )
            request = deepcopy(template.template_data)
            configuration = validated.payload
            profile_id, profile_hash = config.id, config.config_hash
        adapter = self.adapter_factory(validated.config)
        state = {
            "status": "running",
            "completed": 0,
            "count": count,
            "configuration_id": profile_id,
            "configuration_hash": profile_hash,
            "configuration": configuration,
            "threshold": threshold,
            "best_score": None,
            "result": None,
        }
        cancel = Event()
        with self._quick_lock:
            self._quick_cancels.add(cancel)
        try:
            future = self.jobs.submit_task(
                search_hint_map, adapter, request, configuration, count, threshold, state, cancel
            )
        except Exception:
            with self._quick_lock:
                self._quick_cancels.discard(cancel)
            raise

        def finished(_future):
            with self._quick_lock:
                self._quick_cancels.discard(cancel)

        future.add_done_callback(finished)
        return state, cancel

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("The Lab runtime is closed")
        if self._started:
            return
        with ExitStack() as execution:
            execution.enter_context(execution_lock(self.database))
            require_current(self.database)
            with self.database.session_factory() as session:
                recover_interrupted_experiments(session)
                session.execute(update(E02Run).where(E02Run.status.in_(ACTIVE_STATUSES)).values(status="interrupted"))
                session.execute(update(E02BRun).where(E02BRun.status.in_(ACTIVE_STATUSES)).values(
                    status="interrupted", error={"stage": "startup", "message": "Previous Lab process stopped before completion."},
                ))
                session.commit()
            self._execution = execution.pop_all()
        self._started = True

    def start_experiment(self, flow_type: str, payload: Mapping[str, Any]) -> int:
        if not self._started or self._closed:
            raise RuntimeError("Start the Lab runtime before submitting experiments")
        if flow_type not in FLOW_INPUTS:
            raise InvalidInputError("unknown_flow", f"Unknown experiment flow {flow_type!r}")
        validated = FLOW_INPUTS[flow_type].model_validate(payload)
        with self.database.session_factory() as session:
            service = FLOW_SERVICES[flow_type](session, self.codec)
            experiment = service.create_experiment(validated)
            try:
                self.jobs.submit(experiment.id, flow_type)
            except Exception as exc:
                experiment.status = "failed"
                experiment.stop_reason = "job_submission_failed"
                experiment.error_data = error_payload(
                    exc, stage="job_submission", code="job_submission_failed"
                )
                experiment.finished_at = utc_now()
                session.commit()
                raise AppError(
                    "job_submission_failed",
                    "The experiment was saved but could not be queued.",
                    details={"experiment_id": experiment.id},
                ) from exc
            return experiment.id

    def preview_p01b(
        self,
        request: Mapping[str, Any],
        configuration_id: int | None,
        hints: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated = FloorPlanRequest.model_validate(request)
        with self.database.session_factory() as session:
            configuration, validated_config = SystemConfigurationService(session, self.codec).for_flow(
                configuration_id, "p01_preview"
            )
            result = self._manual_preview(validated, validated_config.config, hints)
            return {
                "configuration_id": configuration.id,
                "configuration_hash": configuration.config_hash,
                **result,
            }

    def _manual_preview(
        self,
        request: FloorPlanRequest,
        configuration: Any,
        hints: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        ids = [room.id for room in request.rooms if room.room_type.value != "hallway"]
        if not ids or any(not item for item in ids) or len(ids) != len(set(ids)):
            raise InvalidInputError(
                "explicit_room_ids_required", "P01B rooms require unique explicit IDs."
            )
        adapter = self.adapter_factory(configuration)
        execution = adapter.preprocess(request.model_dump(mode="json"), debug=True)
        validated_hints = (
            ManualHints.model_validate(hints).model_dump(mode="json") if hints is not None else None
        )
        candidate = (
            adapter.build_manual_candidate(execution.result, validated_hints)
            if validated_hints is not None
            else None
        )
        return {"preprocessing": to_jsonable(execution), "candidate": to_jsonable(candidate)}

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._quick_lock:
            for cancel in self._quick_cancels:
                cancel.set()
        try:
            if self._started:
                with self.database.session_factory() as session:
                    session.execute(update(E02Run).where(E02Run.status.in_(ACTIVE_STATUSES)).values(status="termination_requested"))
                    session.commit()
                    for experiment in session.scalars(
                        select(P01Experiment).where(P01Experiment.status.in_(ACTIVE_STATUSES))
                    ):
                        if experiment.flow_type == "p01c" and not (
                            experiment.hint_points or {}
                        ).get("preset"):
                            continue
                        FLOW_SERVICES[experiment.flow_type](session).request_termination(
                            experiment.id
                        )
        finally:
            try:
                self.jobs.shutdown(wait=True)
            finally:
                self.database.dispose()
                self._execution.close()

    def __enter__(self) -> LabRuntime:
        try:
            self.start()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
