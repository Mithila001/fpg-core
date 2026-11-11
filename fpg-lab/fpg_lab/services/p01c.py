from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpg_lab.core.exceptions import NotFoundError
from fpg_lab.database.models import P01Experiment
from fpg_lab.services.p01b import P01BService


class P01CService(P01BService):
    def __init__(self, session: Session, codec: object | None = None) -> None:
        super().__init__(session, codec, flow="p01c")

    def get_experiment(self, experiment_id):
        experiment = super().get_experiment(experiment_id)
        if not experiment.hint_points or "preset" not in experiment.hint_points:
            raise NotFoundError("p01c_experiment_not_found", "This legacy P01C run is unavailable.")
        return experiment

    def list_experiments(self, *, status, limit, offset):
        filters = [P01Experiment.flow_type == "p01c", P01Experiment.hint_points["preset"].as_string().is_not(None)]
        if status is not None:
            filters.append(P01Experiment.status == status)
        total = self.session.scalar(select(func.count()).select_from(P01Experiment).where(*filters)) or 0
        items = self.session.scalars(select(P01Experiment).where(*filters).order_by(
            P01Experiment.created_at.desc(), P01Experiment.id.desc()).limit(limit).offset(offset))
        return list(items), int(total)
