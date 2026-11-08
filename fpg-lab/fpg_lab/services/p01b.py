from sqlalchemy.orm import Session

from fpg_lab.database.models import P01BPreset, P01Experiment
from fpg_lab.inputs import P01BInput
from fpg_lab.services.p01_common import P01Service


class P01BService(P01Service):
    def __init__(self, session: Session, codec: object | None = None) -> None:
        super().__init__(session, "p01b", codec)

    def create_experiment(self, payload: P01BInput) -> P01Experiment:
        from fpg_lab.integrations.fpg_core.p01b_input import validate_export

        preset = self.session.get(P01BPreset, payload.preset_id)
        if preset is None:
            raise ValueError("Hint map preset not found")
        validate_export(preset.data)
        return self._create_experiment(
            floor_plan_request=preset.data["request"],
            hint_points={
                "preset": preset.data,
                "preset_name": preset.name,
                **payload.model_dump(mode="json"),
            },
            trial_count=payload.iterations,
            should_save=True,
            system_configuration_id=payload.system_configuration_id,
        )
