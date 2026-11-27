from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpg_lab.core.exceptions import NotFoundError
from fpg_lab.database.models import (
    P01CandidateTrial,
    P01Experiment,
)
from fpg_lab.database.models.common import utc_now
from fpg_lab.services.common import SystemConfigurationService

TERMINAL_STATUSES = {"completed", "terminated", "failed", "interrupted"}


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
        configuration, validated = SystemConfigurationService(self.session, self.codec).for_flow(
            system_configuration_id, self.flow_type
        )
        if hint_points is not None and self.flow_type in ("p01b", "p01c"):
            from fpg_lab.core.serialization import to_jsonable
            from fpg_lab.flows.p01b import effective_profiles

            initial, refinement = effective_profiles(validated.config, hint_points)
            hint_points = {**hint_points, "effective_solver": to_jsonable({
                "initial": initial, "refinement": refinement,
            })}
        experiment = P01Experiment(
            flow_type=self.flow_type,
            status="queued",
            requested_trial_count=trial_count,
            persist_trial_data=should_save,
            floor_plan_request=floor_plan_request,
            hint_points=hint_points,
            system_configuration_id=configuration.id,
            system_configuration_snapshot=validated.payload,
            system_configuration_hash=configuration.config_hash,
            fpg_core_version=validated.fpg_core_version,
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
    ) -> tuple[list[P01CandidateTrial], int]:
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
        return trials, int(total)

    def get_trial(self, trial_id: int) -> P01CandidateTrial:
        trial = self.session.get(P01CandidateTrial, trial_id)
        if trial is None or trial.experiment.flow_type != self.flow_type:
            raise NotFoundError(
                f"{self.flow_type}_trial_not_found",
                f"{self.flow_type.upper()} trial {trial_id} was not found.",
            )
        return trial
