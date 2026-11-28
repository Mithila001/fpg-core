from __future__ import annotations

import json
import time
from copy import deepcopy

import pytest
from fpg_core.domain import (
    FloorPlan,
    FloorPlanGenerationSpec,
    FloorPlanRoom,
    FloorSpec,
    Point,
    Polygon,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)
from test_lab import initialized_runtime

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BSavedPlan, E02CRun
from fpg_lab.flows.e02b import save_layout
from fpg_lab.flows.e02c import start
from fpg_lab.services.common import SystemConfigurationService


def wait_for_run(runtime, run_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with runtime.database.session_factory() as session:
            row = session.get(E02CRun, run_id)
            if row.status not in {"queued", "running"}:
                return deepcopy(row)
        time.sleep(0.05)
    raise AssertionError("E02C run did not finish within 20 seconds")


def source_plan():
    def polygon(points):
        return Polygon(tuple(Point(x, y) for x, y in points))
    floor = FloorPlan(polygon([(0, 0), (40, 0), (40, 20), (0, 20)]), [
        FloorPlanRoom(RoomId("living"), RoomType.LIVING_ROOM, "Living", polygon([(0, 0), (20, 0), (20, 20), (0, 20)])),
        FloorPlanRoom(RoomId("bedroom"), RoomType.BEDROOM, "Bedroom", polygon([(20, 0), (40, 0), (40, 20), (20, 20)])),
    ])
    spec = FloorPlanGenerationSpec(FloorSpec(40, 20), tuple(
        RoomSpec(RoomId(name), kind, name, RoomSizeSpec(5, 20, 40, 400))
        for name, kind in (("living", RoomType.LIVING_ROOM), ("bedroom", RoomType.BEDROOM))
    ), ())
    return floor, spec


def portable():
    floor_plan, generation_spec = source_plan()
    return {"schema": "fpg-floor-plan", "version": 1, "project_units_per_meter": 10,
            "floor_plan": to_jsonable(floor_plan), "specification": to_jsonable(generation_spec),
            "source": {"experiment": "test"}}


def test_e02c_generates_and_snapshots_a_shared_saved_plan(tmp_path):
    runtime = initialized_runtime(database_url=f"sqlite:///{tmp_path / 'e02c.db'}")
    with runtime:
        document = portable()
        with runtime.database.session_factory() as session:
            profile = SystemConfigurationService(session).get_active()
            saved_id = save_layout(session, "E02C source", document)
            config_id = profile.id
        run_id = start(runtime, layout_id=saved_id, configuration_id=config_id)
        finished = wait_for_run(runtime, run_id)
        assert finished.status == "completed", finished.error
        assert finished.snapshot["input"] == json.loads(json.dumps(document))
        assert finished.result["floor_plan"]["openings"]
        assert finished.diagnostics is not None
        with runtime.database.session_factory() as session:
            saved = session.get(E02BSavedPlan, saved_id)
            assert saved.document == document


def test_e02c_requires_matching_units_and_explicit_regeneration(tmp_path):
    runtime = initialized_runtime(database_url=f"sqlite:///{tmp_path / 'e02c-validation.db'}")
    with runtime, runtime.database.session_factory() as session:
        profile = SystemConfigurationService(session).get_active()
        document = portable()
        document["project_units_per_meter"] = 20
        with pytest.raises(ValueError, match="units must match"):
            start(runtime, document=document, configuration_id=profile.id)
        document = portable()
        document["floor_plan"].setdefault("openings", []).append({"id": "old", "opening_type": "door", "purpose": "main_entrance", "start": {"x": 0, "y": 0}, "end": {"x": 1, "y": 0}, "connected_room_ids": []})
        with pytest.raises(ValueError, match="regeneration"):
            start(runtime, document=document, configuration_id=profile.id)


