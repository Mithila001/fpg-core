from __future__ import annotations

import json
from typing import Any, TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpg_lab.database.models import P01CandidateTrial, P01Experiment
from fpg_lab.database.serialization import row_document
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
        return super().list_trials(experiment_id=experiment_id, limit=limit, offset=offset)

    def get_candidate_trial(self, trial_id: int) -> P01CandidateTrial:
        return super().get_trial(trial_id)

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

    def export_history(self, experiment_ids: list[int], compact: bool, output: TextIO) -> None:
        """Write each saved trial once, without materializing the complete history."""
        output.write(
            '{"format_version":1,"mode":'
            + json.dumps("compact" if compact else "full")
            + ',"experiments":['
        )
        for index, experiment_id in enumerate(experiment_ids):
            experiment = self.get_experiment(experiment_id)
            document = row_document(experiment)
            reasons = []
            if not experiment.persist_trial_data:
                reasons.append("debug_data_disabled")
            if experiment.status in {"queued", "running", "termination_requested"}:
                reasons.append("experiment_active")
            if index:
                output.write(",")
            output.write(
                '{"incomplete":'
                + json.dumps(bool(reasons))
                + ',"incomplete_reasons":'
                + json.dumps(reasons)
                + ',"experiment":'
            )
            output.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
            output.write(',"trials":[')
            trials = self.session.scalars(
                select(P01CandidateTrial)
                .where(P01CandidateTrial.experiment_id == experiment_id)
                .order_by(P01CandidateTrial.trial_no)
                .execution_options(yield_per=50)
            )
            for trial_index, trial in enumerate(trials):
                if trial_index:
                    output.write(",")
                document = row_document(trial)
                if compact:
                    document = compact_trial(document)
                output.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
            output.write("]}")
        output.write("]}")


def compact_trial(document: dict[str, Any]) -> dict[str, Any]:
    candidate = document.get("candidate_search_data")
    if isinstance(candidate, dict):
        candidate = {key: candidate.get(key) for key in ("points", "recorded_result")}
        if isinstance(candidate["recorded_result"], dict):
            candidate["recorded_result"] = {
                key: value
                for key, value in candidate["recorded_result"].items()
                if key != "candidate"
            }
    circulation = document.get("circulation_data")
    if isinstance(circulation, dict):
        result = circulation.get("result")
        if isinstance(result, dict):
            result = dict(result)
            if isinstance(result.get("candidate"), dict):
                result["candidate"] = {"points": result["candidate"].get("points")}
        details = circulation.get("details")
        if isinstance(details, dict):
            details = {
                key: value
                for key, value in details.items()
                if key not in {"passes", "hallway_consolidation_attempts"}
            }
        circulation = {"result": result, "details": details}
    scoring = document.get("candidate_scoring_data")
    if isinstance(scoring, dict):
        scoring = json.loads(json.dumps(scoring))
        for evaluator in scoring.get("evaluator_results", []):
            if evaluator.get("evaluator_key") == "spatial_distribution" and isinstance(
                evaluator.get("details"), dict
            ):
                evaluator["details"].pop("nearest_distances", None)
                evaluator["details"].pop("points", None)
    return {
        "trial_no": document["trial_no"],
        "status": document["status"],
        "final_score": document["final_score"],
        "duration_ms": document["duration_ms"],
        "error_data": document["error_data"],
        "candidate_search_data": candidate,
        "circulation_data": circulation,
        "candidate_scoring_data": scoring,
    }
