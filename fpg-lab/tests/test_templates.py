from __future__ import annotations

from collections import Counter
from pathlib import Path

from test_lab import initialized_runtime

from fpg_lab.core.settings import ROOT
from fpg_lab.database.maintenance import seed
from fpg_lab.inputs import FloorPlanTemplateCreate
from fpg_lab.integrations.fpg_core.adapter import FpgCoreAdapter
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.services.common import FloorPlanTemplateService
from scripts.run_experiment import sample_hints, sample_request


def test_research_templates_preprocess_and_seed_idempotently(tmp_path: Path) -> None:
    common = {"living_room": 1, "kitchen": 1, "bathroom": 1}
    expected = {
        "example": ("Full Template (Default)", (240, 180), {**common, "bedroom": 3, "attached_bathroom": 1, "dining_room": 1, "veranda": 1, "garage": 1}),
        "minimal": ("Minimal", (180, 135), {**common, "bedroom": 1, "veranda": 1}),
        "super_minimal": ("Super Minimal", (160, 120), {**common, "bedroom": 1}),
        "average": ("Average", (220, 165), {**common, "bedroom": 2, "dining_room": 1, "veranda": 1, "garage": 1}),
        "big_plan": ("Big Plan", (280, 210), {**common, "bedroom": 4, "attached_bathroom": 2, "dining_room": 1, "veranda": 1, "garage": 1}),
    }
    codec = CoreConfigCodec()
    adapter = FpgCoreAdapter(codec.decode_for_flow(codec.default_configuration().payload, "p01a"))
    paths = sorted((ROOT / "seed").glob("floor_plan_template.*.json"))
    assert len(paths) == len(expected)
    with initialized_runtime(database_url=f"sqlite:///{tmp_path / 'templates.db'}") as runtime:
        with runtime.database.session_factory() as session:
            service = FloorPlanTemplateService(session)
            ids = {row.name: row.id for row in service.list(limit=10, offset=0)[0]}
            for path in paths:
                template = FloorPlanTemplateCreate.model_validate_json(path.read_text(encoding="utf-8"))
                name, limits, counts = expected[path.stem.split(".")[1]]
                request = template.template_data
                assert template.name == name
                assert Counter(room.room_type.value for room in request.rooms) == counts
                assert (request.floor_limits.max_width, request.floor_limits.max_length) == limits
                assert request.aspect_ratio == "4:3"
                prepared = adapter.preprocess(request.model_dump(mode="json"), debug=True).result
                assert prepared.generation_spec.floor.width <= request.floor_limits.max_width
                assert prepared.generation_spec.floor.length <= request.floor_limits.max_length
                assert {room.id for room in request.rooms} <= {room.id for room in prepared.generation_spec.rooms}
                candidate = adapter.create_candidate_search(prepared, trial_count=1).ask().candidate
                rules = adapter._circulation_config(candidate).route_rules
                room_types = {point.room_type for point in candidate.points}
                assert rules
                assert all(rule.source_room_type in room_types and rule.destination_room_type in room_types for rule in rules)
                circulation = adapter.run_circulation(candidate, prepared=prepared, debug=True)
                assert circulation.details.passes[-1].paths
            assert not seed(runtime.database)["templates"]
            assert {row.name: row.id for row in service.list(limit=10, offset=0)[0]} == ids
            assert service.list(limit=10, offset=0)[1] == len(expected)


def test_headless_manual_hints_use_the_default_grid() -> None:
    adapter = FpgCoreAdapter(CoreConfigCodec().default_configuration().config)
    prepared = adapter.preprocess(sample_request(), debug=False).result
    candidate = adapter.build_manual_candidate(prepared, sample_hints())
    assert adapter.run_circulation(candidate, prepared=prepared, debug=True).details.passes[-1].paths
