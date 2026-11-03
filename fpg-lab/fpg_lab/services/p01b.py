from sqlalchemy.orm import Session

from fpg_lab.database.models import P01Experiment
from fpg_lab.inputs import P01BInput
from fpg_lab.services.p01_common import P01Service


class P01BService(P01Service):
    def __init__(self, session: Session, codec: object | None = None) -> None:
        super().__init__(session, "p01b", codec)

    def create_experiment(self, payload: P01BInput) -> P01Experiment:
        return self._create_experiment(
            floor_plan_request=payload.floor_plan_request.model_dump(mode="json"),
            hint_points=payload.hint_points.model_dump(mode="json"),
            should_save=payload.should_save,
            system_configuration_id=payload.system_configuration_id,
        )
