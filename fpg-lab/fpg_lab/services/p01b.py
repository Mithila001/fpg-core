import re
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpg_lab.database.models import P01BPreset, P01Experiment
from fpg_lab.inputs import P01BInput
from fpg_lab.services.p01_common import P01Service


def next_preset_name(session):
    names = session.scalars(select(P01BPreset.name)).all()
    numbers = [
        int(match.group(1)) for name in names if (match := re.fullmatch(r"hintMap_(\d+)", name))
    ]
    return f"hintMap_{max(numbers, default=0) + 1:03d}"


_preset_lock = (
    Lock()
)  # ponytail: one process serializes preset saves; use a DB constraint for multiple writers.


def save_preset(session, name, data, suggested=None):
    from fpg_lab.integrations.fpg_core.p01b_input import validate_export

    validate_export(data)
    with _preset_lock:
        name = (name or "").strip()
        if suggested is not None and (not name or name == suggested):
            name = next_preset_name(session)
        if not name or len(name) > 128:
            raise ValueError("Preset name must contain 1 to 128 characters")
        if session.scalar(select(P01BPreset.id).where(P01BPreset.name == name)) is not None:
            raise ValueError("A preset with this name already exists")
        row = P01BPreset(name=name, data=data)
        session.add(row)
        session.commit()
        return row.id


class P01BService(P01Service):
    def __init__(
        self, session: Session, codec: object | None = None, *, flow: str = "p01b"
    ) -> None:
        super().__init__(session, flow, codec)

    def create_experiment(self, payload: P01BInput) -> P01Experiment:
        from fpg_lab.integrations.fpg_core.p01b_input import validate_export

        preset = self.session.get(P01BPreset, payload.preset_id) if payload.preset_id else None
        if preset is None and payload.preset_data is None:
            raise ValueError("Hint map preset not found")
        data = preset.data if preset is not None else payload.preset_data
        validate_export(data)
        return self._create_experiment(
            floor_plan_request=data["request"],
            hint_points={
                "preset": data,
                "preset_name": preset.name if preset is not None else "Unsaved hint map",
                **payload.model_dump(mode="json", exclude={"preset_data"}),
            },
            trial_count=payload.iterations,
            should_save=True,
            system_configuration_id=payload.system_configuration_id,
        )
