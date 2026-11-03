from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpg_lab.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from fpg_lab.database.models import (
    P01CandidateTrial,
    P01Experiment,
    P01FloorPlanRun,
    SystemConfiguration,
)

TERMINAL_STATUSES = {"completed", "terminated", "failed", "interrupted"}


def utc_now() -> datetime:
    return datetime.now(UTC)


class P01Service:
    def __init__(self, session: Session, flow_type: str, codec: Any | None = None) -> None:
        self.session = session
        self.flow_type = flow_type
        self.codec = codec

    def _create_experiment(
        self,
        *,
        floor_plan_request: dict[str, Any],
        should_save: bool,
        system_configuration_id: int | None,
        trial_count: int | None = None,
        hint_points: dict[str, Any] | None = None,
    ) -> P01Experiment:
        configuration = self._resolve_configuration(system_configuration_id)
        experiment = P01Experiment(
            flow_type=self.flow_type,
            status="queued",
            requested_trial_count=trial_count,
            persist_trial_data=should_save,
            floor_plan_request=floor_plan_request,
            hint_points=hint_points,
            system_configuration_id=configuration.id,
            system_configuration_snapshot=configuration.configuration_data,
            system_configuration_hash=configuration.config_hash,
            fpg_core_version=configuration.fpg_core_version,
        )
        self.session.add(experiment)
        self.session.commit()
        return experiment

    def get_experiment(self, experiment_id: int) -> P01Experiment:
        experiment = self.session.get(P01Experiment, experiment_id)
        if experiment is None or experiment.flow_type != self.flow_type:
            raise NotFoundError(
                f"{self.flow_type}_experiment_not_found",
                f"{self.flow_type.upper()} experiment {experiment_id} was not found.",
            )
        return experiment

    def list_experiments(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[P01Experiment], int]:
        filters = [P01Experiment.flow_type == self.flow_type]
        if status is not None:
            filters.append(P01Experiment.status == status)
        total = (
            self.session.scalar(select(func.count()).select_from(P01Experiment).where(*filters))
            or 0
        )
        items = list(
            self.session.scalars(
                select(P01Experiment)
                .where(*filters)
                .order_by(P01Experiment.created_at.desc(), P01Experiment.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total)

    def request_termination(self, experiment_id: int) -> P01Experiment:
        experiment = self.get_experiment(experiment_id)
        if (
            experiment.status not in TERMINAL_STATUSES
            and experiment.status != "termination_requested"
        ):
            experiment.status = "termination_requested"
            experiment.termination_requested_at = utc_now()
            experiment.stop_reason = "termination_requested"
            self.session.commit()
        return experiment

    def list_trials(
        self, *, experiment_id: int | None, limit: int, offset: int
    ) -> tuple[list[tuple[P01CandidateTrial, int | None]], int]:
        filters = [P01Experiment.flow_type == self.flow_type]
        if experiment_id is not None:
            self.get_experiment(experiment_id)
            filters.append(P01CandidateTrial.experiment_id == experiment_id)
        base = select(P01CandidateTrial).join(P01Experiment).where(*filters)
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(P01CandidateTrial)
                .join(P01Experiment)
                .where(*filters)
            )
            or 0
        )
        trials = list(
            self.session.scalars(
                base.order_by(P01CandidateTrial.experiment_id.desc(), P01CandidateTrial.trial_no)
                .limit(limit)
                .offset(offset)
            )
        )
        if not trials:
            return [], int(total)
        run_ids: dict[int, int] = {}
        rows = self.session.execute(
            select(P01FloorPlanRun.source_trial_id, P01FloorPlanRun.id).where(
                P01FloorPlanRun.source_trial_id.in_([item.id for item in trials])
            )
        )
        for source_trial_id, run_id in rows:
            if source_trial_id is not None:
                run_ids[source_trial_id] = run_id
        return [(item, run_ids.get(item.id)) for item in trials], int(total)

    def get_trial(self, trial_id: int) -> tuple[P01CandidateTrial, int | None]:
        trial = self.session.get(P01CandidateTrial, trial_id)
        if trial is None or trial.experiment.flow_type != self.flow_type:
            raise NotFoundError(
                f"{self.flow_type}_trial_not_found",
                f"{self.flow_type.upper()} trial {trial_id} was not found.",
            )
        run_id = self.session.scalar(
            select(P01FloorPlanRun.id).where(P01FloorPlanRun.source_trial_id == trial.id)
        )
        return trial, run_id

    def list_floor_plan_runs(
        self, *, experiment_id: int | None, limit: int, offset: int
    ) -> tuple[list[P01FloorPlanRun], int]:
        filters = [P01Experiment.flow_type == self.flow_type]
        if experiment_id is not None:
            self.get_experiment(experiment_id)
            filters.append(P01FloorPlanRun.experiment_id == experiment_id)
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(P01FloorPlanRun)
                .join(P01Experiment)
                .where(*filters)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(P01FloorPlanRun)
                .join(P01Experiment)
                .where(*filters)
                .order_by(P01FloorPlanRun.created_at.desc(), P01FloorPlanRun.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total)

    def get_floor_plan_run(self, run_id: int) -> P01FloorPlanRun:
        run = self.session.get(P01FloorPlanRun, run_id)
        if run is None or run.experiment.flow_type != self.flow_type:
            raise NotFoundError(
                f"{self.flow_type}_floor_plan_run_not_found",
                f"{self.flow_type.upper()} floor-plan run {run_id} was not found.",
            )
        return run

    def _resolve_configuration(self, configuration_id: int | None) -> SystemConfiguration:
        if configuration_id is not None:
            configuration = self.session.get(SystemConfiguration, configuration_id)
            if configuration is None:
                raise NotFoundError(
                    "system_configuration_not_found",
                    f"System configuration {configuration_id} was not found.",
                )
            return self._validate_configuration(configuration)
        configuration = self.session.scalar(
            select(SystemConfiguration).where(SystemConfiguration.is_active.is_(True))
        )
        if configuration is None:
            raise ConflictError(
                "active_system_configuration_required",
                f"Activate a system configuration before starting a {self.flow_type.upper()} experiment.",
            )
        return self._validate_configuration(configuration)

    def _validate_configuration(self, configuration: SystemConfiguration) -> SystemConfiguration:
        if self.codec is None:
            return configuration
        from fpg_lab.integrations.fpg_core.config_codec import CoreConfigurationError

        try:
            validated = self.codec.validate_for_flow(
                configuration.configuration_data,
                self.flow_type,
            )
        except CoreConfigurationError as exc:
            raise InvalidInputError("invalid_fpg_core_configuration", str(exc)) from exc
        configuration.configuration_data = validated.payload
        configuration.schema_version = str(validated.payload["schema_version"])
        configuration.config_hash = validated.config_hash
        configuration.fpg_core_version = validated.fpg_core_version
        self.session.commit()
        return configuration
