import json
import time

import pytest
from sqlalchemy import func, select
from test_lab import PLAN, Execution, RecordingAdapter, Solve, create_profile, payload, wait

from fpg_lab.database.models import P01BPreset, SystemConfiguration
from fpg_lab.database.models.e02 import E02Run
from fpg_lab.flows import e02a
from fpg_lab.integrations.fpg_core.p01b_input import export_trial
from fpg_lab.runtime import LabRuntime


def test_file_backed_run_and_isolation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(e02a, "generate_floor_plan", lambda request, *, mode: (calls.append(request) or Execution(Solve(PLAN))))
    maps_path = tmp_path / "maps.json"
    monkeypatch.setattr("fpg_lab.integrations.fpg_core.e02a_input.HINT_MAPS_PATH", maps_path)
    monkeypatch.setattr(e02a, "load_hint_maps", lambda: json.loads(maps_path.read_text()))
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        maps_path.write_text(json.dumps({"one": document, "two": document, "three": document, "four": document}))
        with runtime.database.session_factory() as session:
            profiles = session.scalar(select(func.count()).select_from(SystemConfiguration))
            presets = session.scalar(select(func.count()).select_from(P01BPreset))
        snapshot = e02a.prepare(runtime.codec, "one")
        assert list(snapshot["maps"]) == ["one"]
        assert len(e02a.prepare(runtime.codec, None)["maps"]) == 4
        run_id = e02a.start(runtime, "one")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                row = session.get(E02Run, run_id)
                if row.status not in ("queued", "running"):
                    break
            time.sleep(.02)
        assert row.status == "completed", row.error
        assert row.cases[0]["status"] == "completed", row.cases
        assert [stage["name"] for stage in row.cases[0]["stages"]] == ["Initial", "Post-process"]
        assert row.cases[0]["scoring"]["result"]["total_score"] == 90
        assert calls[0].candidate_hints and row.snapshot["effective_solver"]
        with runtime.database.session_factory() as session:
            assert profiles == session.scalar(select(func.count()).select_from(SystemConfiguration))
            assert presets == session.scalar(select(func.count()).select_from(P01BPreset))
        maps_path.write_text('{}')
        with pytest.raises(ValueError, match="exactly four"):
            e02a.prepare(runtime.codec, None)


def test_invalid_config_and_independent_failures(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config = json.loads(e02a.CONFIG_PATH.read_text(encoding="utf-8"))
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(e02a, "CONFIG_PATH", config_path)
    monkeypatch.setattr(e02a, "generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN)))
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        monkeypatch.setattr(e02a, "load_hint_maps", lambda: {str(i): document for i in range(4)})
        config["configuration"]["floor_plan_solver"]["initial"]["unexpected_field"] = True
        config_path.write_text(json.dumps(config))
        with pytest.raises(Exception, match="unexpected_field"):
            e02a.prepare(runtime.codec, "0")
        del config["configuration"]["floor_plan_solver"]["initial"]["unexpected_field"]
        config_path.write_text(json.dumps(config))
        class FailFirst(RecordingAdapter):
            count = 0
            def refine_floor_plan(self, *args, **kwargs):
                self.count += 1
                if self.count == 1:
                    raise RuntimeError("refinement broke")
                return super().refine_floor_plan(*args, **kwargs)
        runtime.adapter_factory = FailFirst
        run_id = e02a.start(runtime, None, refinement_rounds=1)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                row = session.get(E02Run, run_id)
                if row.status not in ("queued", "running"):
                    break
            time.sleep(.02)
        assert row.status == "completed", row.error
        assert [case["status"] for case in row.cases] == ["failed", "completed", "completed", "completed"]
        assert row.cases[0]["error"]["stage"] == "refinement_1"
