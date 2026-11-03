from __future__ import annotations

from collections import Counter
from pathlib import Path

from fpg_lab.core.settings import ROOT
from fpg_lab.inputs import FloorPlanTemplateCreate
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.runtime import LabRuntime
from fpg_lab.services.common import FloorPlanTemplateService
from scripts.seed_db import seed_template


def test_four_research_templates_preprocess_and_seed_idempotently(tmp_path: Path) -> None:
    expected = {
        "example": (2, 0, 0, 0),
        "garage_veranda": (2, 0, 1, 1),
        "two_bedroom_ensuite": (2, 1, 1, 0),
        "three_bedroom_ensuites": (3, 2, 1, 0),
    }
    codec = CoreConfigCodec()
    adapter = FpgCoreAdapter(codec.decode_for_flow(codec.default_configuration().payload, "p01a"))
    paths = sorted((ROOT / "seed").glob("floor_plan_template.*.json"))
    assert len(paths) == 4
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'templates.db'}") as runtime:
        with runtime.database.session_factory() as session:
            service = FloorPlanTemplateService(session)
            ids = []
            for path in paths:
                template = FloorPlanTemplateCreate.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                request = template.template_data
                counts = Counter(room.room_type.value for room in request.rooms)
                assert (
                    tuple(counts[k] for k in ("bedroom", "attached_bathroom", "garage", "veranda"))
                    == expected[path.stem.split(".")[1]]
                )
                assert all(
                    counts[k] == 1 for k in ("living_room", "kitchen", "dining_room", "bathroom")
                )
                prepared = adapter.preprocess(request.model_dump(mode="json"), debug=True).result
                assert prepared.generation_spec.floor.width <= request.floor_limits.max_width
                assert prepared.generation_spec.floor.length <= request.floor_limits.max_length
                assert {room.id for room in request.rooms} <= {
                    room.id for room in prepared.generation_spec.rooms
                }
                ids.append(seed_template(service, session, path))
            assert [seed_template(service, session, path) for path in paths] == ids
            assert service.list(limit=10, offset=0)[1] == 4
