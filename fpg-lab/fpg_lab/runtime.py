"""Application resources and execution; importing this module never imports NiceGUI."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from sqlalchemy import inspect, select

from fpg_lab.core.exceptions import AppError, InvalidInputError
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import get_settings
from fpg_lab.database.models import P01Experiment
from fpg_lab.database.session import Database
from fpg_lab.flows.p01 import (
    ACTIVE_STATUSES,
    P01FlowRunner,
    error_payload,
    recover_interrupted_experiments,
)
from fpg_lab.inputs import FloorPlanRequest, ManualHints, P01AInput, P01BInput, P01CInput
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.services.common import seed_namespace_registry
from fpg_lab.services.p01a import P01AService
from fpg_lab.services.p01b import P01BService
from fpg_lab.services.p01c import P01CService
from fpg_lab.workers.p01_jobs import P01JobManager

FLOW_INPUTS = {"p01a": P01AInput, "p01b": P01BInput, "p01c": P01CInput}
FLOW_SERVICES: dict[str, Any] = {"p01a": P01AService, "p01b": P01BService, "p01c": P01CService}


def row_document(row: Any) -> dict[str, Any]:
    """Materialize mapped columns while the caller still owns the session."""
    return {
        column.key: to_jsonable(getattr(row, column.key))
        for column in inspect(row).mapper.column_attrs
    }


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
        self.jobs = P01JobManager(
            self.runner, max_workers=max_workers or settings.max_background_workers
        )
        self._started = False
        self._closed = False

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("The Lab runtime is closed")
        if self._started:
            return
        if get_settings().auto_create_schema:
            self.database.create_schema()
        with self.database.session_factory() as session:
            from fpg_lab.integrations.fpg_core.profile_migration import migrate_profiles

            migrate_profiles(session, self.codec)
            seed_namespace_registry(session)
            recover_interrupted_experiments(session)
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
                from fpg_lab.services.p01_common import utc_now

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
            configuration = P01BService(session, self.codec)._resolve_configuration(
                configuration_id
            )
            result = self._manual_preview(validated, configuration.configuration_data, hints)
            return {
                "configuration_id": configuration.id,
                "configuration_hash": configuration.config_hash,
                **result,
            }

    def _manual_preview(
        self,
        request: FloorPlanRequest,
        configuration: Mapping[str, Any],
        hints: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        ids = [room.id for room in request.rooms if room.room_type.value != "hallway"]
        if not ids or any(not item for item in ids) or len(ids) != len(set(ids)):
            raise InvalidInputError(
                "explicit_room_ids_required", "P01B rooms require unique explicit IDs."
            )
        adapter = self.adapter_factory(self.codec.decode_for_flow(deepcopy(configuration), "p01b"))
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
        try:
            if self._started:
                with self.database.session_factory() as session:
                    for experiment in session.scalars(
                        select(P01Experiment).where(P01Experiment.status.in_(ACTIVE_STATUSES))
                    ):
                        if experiment.flow_type == "p01c" and not (experiment.hint_points or {}).get("preset"):
                            continue
                        FLOW_SERVICES[experiment.flow_type](session).request_termination(
                            experiment.id
                        )
        finally:
            try:
                self.jobs.shutdown(wait=True)
            finally:
                self.database.dispose()

    def __enter__(self) -> LabRuntime:
        try:
            self.start()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
