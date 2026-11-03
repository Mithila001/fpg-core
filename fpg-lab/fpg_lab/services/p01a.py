from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpg_lab.database.models import P01CandidateTrial, P01Experiment
from fpg_lab.inputs import P01AInput
from fpg_lab.services.p01_common import P01Service


class P01AService(P01Service):
    def __init__(self, session: Session, codec: object | None = None) -> None:
        super().__init__(session, "p01a", codec)

    def create_experiment(self, payload: P01AInput) -> P01Experiment:
        return self._create_experiment(
            floor_plan_request=payload.floor_plan_request.model_dump(mode="json"),
            trial_count=payload.trial_count,
            should_save=payload.should_save,
            system_configuration_id=payload.system_configuration_id,
        )

    def get_experiment_detail(self, experiment_id: int) -> tuple[P01Experiment, int]:
        experiment = self.get_experiment(experiment_id)
        _, count = self.list_candidate_trials(experiment_id=experiment_id, limit=1, offset=0)
        return experiment, count

    def list_candidate_trials(
        self, *, experiment_id: int | None, limit: int, offset: int
    ) -> tuple[list[P01CandidateTrial], int]:
        rows, total = super().list_trials(experiment_id=experiment_id, limit=limit, offset=offset)
        return [row[0] for row in rows], total

    def get_candidate_trial(self, trial_id: int) -> P01CandidateTrial:
        return super().get_trial(trial_id)[0]

    def replay_trials(self, experiment_id: int, *, after: int = 0) -> list[P01CandidateTrial]:
        """Read one bounded chronological page, checking the experiment's flow first."""
        self.get_experiment(experiment_id)
        return list(
            self.session.scalars(
                select(P01CandidateTrial)
                .where(
                    P01CandidateTrial.experiment_id == experiment_id,
                    P01CandidateTrial.trial_no > after,
                )
                .order_by(P01CandidateTrial.trial_no)
                .limit(100)
            )
        )
