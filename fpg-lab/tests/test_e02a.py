import json
import time

import pytest
from sqlalchemy import func, select
from test_lab import (
    PLAN,
    Execution,
    RecordingAdapter,
    Solve,
    create_profile,
    initialized_runtime,
    payload,
    wait,
)

from fpg_lab.database.models import P01BPreset, SystemConfiguration
from fpg_lab.database.models.e02 import E02Run
from fpg_lab.flows import e02a
from fpg_lab.integrations.fpg_core.p01b_input import export_trial
from fpg_lab.services.common import SystemConfigurationService


def test_prepared_maps_and_selected_profile_snapshot(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        e02a,
        "generate_floor_plan",
        lambda request, *, mode: calls.append(request) or Execution(Solve(PLAN)),
    )
    maps_path = tmp_path / "maps.json"
    monkeypatch.setattr("fpg_lab.integrations.fpg_core.e02a_input.HINT_MAPS_PATH", maps_path)
    monkeypatch.setattr(e02a, "load_hint_maps", lambda: json.loads(maps_path.read_text()))
    with initialized_runtime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        profile_id = create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        maps_path.write_text(
            json.dumps({"one": document, "two": document, "three": document, "four": document})
        )
        with runtime.database.session_factory() as session:
            profiles = session.scalar(select(func.count()).select_from(SystemConfiguration))
            presets = session.scalar(select(func.count()).select_from(P01BPreset))
        snapshot = e02a.prepare(runtime, "one", configuration_id=profile_id)
        assert snapshot["configuration_id"] == profile_id
        assert list(snapshot["maps"]) == ["one"]
        assert len(e02a.prepare(runtime, None)["maps"]) == 4
        run_id = e02a.start(runtime, "one", initial_time_limit=1, random_seed=19)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                row = session.get(E02Run, run_id)
                if row.status not in ("queued", "running"):
                    break
            time.sleep(0.02)
        assert row.status == "completed", row.error
        assert row.cases[0]["status"] == "completed", row.cases
        assert [stage["name"] for stage in row.cases[0]["stages"]] == ["Initial", "Post-process"]
        assert row.cases[0]["scoring"]["result"]["total_score"] == 90
        assert calls[0].candidate_hints and row.snapshot["effective_solver"]
        assert calls[0].config.solver.random_seed == 19
        assert row.snapshot["effective_solver"]["initial"]["solver"]["max_time_seconds"] == 1
        assert row.snapshot["effective_solver"]["initial"]["solver"]["random_seed"] == 19
        with runtime.database.session_factory() as session:
            assert profiles == session.scalar(select(func.count()).select_from(SystemConfiguration))
            assert presets == session.scalar(select(func.count()).select_from(P01BPreset))
        maps_path.write_text("{}")
        with pytest.raises(ValueError, match="exactly four"):
            e02a.prepare(runtime, None)


def test_invalid_config_and_independent_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(
        e02a, "generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN))
    )
    with initialized_runtime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        monkeypatch.setattr(e02a, "load_hint_maps", lambda: {str(i): document for i in range(4)})
        with runtime.database.session_factory() as session:
            profile = SystemConfigurationService(session, runtime.codec).get_active()
            original = profile.configuration_data
            from copy import deepcopy

            invalid = deepcopy(original)
            invalid["floor_plan_solver"]["initial"]["unexpected_field"] = True
            profile.configuration_data = invalid
            profile.config_hash = runtime.codec.hash_payload(invalid)
            session.commit()
            with pytest.raises(Exception, match="unexpected_field"):
                e02a.prepare(runtime, "0")
            profile.configuration_data = original
            profile.config_hash = runtime.codec.hash_payload(original)
            session.commit()

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
            time.sleep(0.02)
        assert row.status == "completed", row.error
        assert [case["status"] for case in row.cases] == [
            "failed",
            "completed",
            "completed",
            "completed",
        ]
        assert row.cases[0]["error"]["stage"] == "refinement_1"


def test_retry_initial_solve_and_attempt_limit(tmp_path, monkeypatch):
    calls = []

    def solve(request, *, mode):
        calls.append(request.config.solver)
        return Execution(Solve(PLAN, solved=len(calls) >= 2))

    monkeypatch.setattr(e02a, "generate_floor_plan", solve)
    with initialized_runtime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        monkeypatch.setattr(e02a, "load_hint_maps", lambda: {"one": document})
        with pytest.raises(ValueError, match="Maximum attempts"):
            e02a.prepare(runtime, "one", retry_until_feasible=True, maximum_attempts=0)
        run_id = e02a.start(
            runtime,
            "one",
            initial_time_limit=2,
            random_seed=19,
            retry_until_feasible=True,
            maximum_attempts=10.0,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                row = session.get(E02Run, run_id)
                if row.status not in ("queued", "running"):
                    break
            time.sleep(0.02)
        assert row.cases[0]["status"] == "completed", row.cases
        assert [s["name"] for s in row.cases[0]["stages"]] == ["Initial", "Post-process"]
        assert [call.random_seed for call in calls] == [19, 20]
        assert all(call.max_time_seconds <= 2 for call in calls)

        calls.clear()
        monkeypatch.setattr(
            e02a,
            "generate_floor_plan",
            lambda request, *, mode: calls.append(request) or Execution(Solve(PLAN, solved=False)),
        )
        run_id = e02a.start(runtime, "one", retry_until_feasible=True, maximum_attempts=3)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with runtime.database.session_factory() as session:
                row = session.get(E02Run, run_id)
                if row.status not in ("queued", "running"):
                    break
            time.sleep(0.02)
        assert row.cases[0]["status"] == "failed"
        assert len(calls) == 3
        assert row.cases[0]["stages"] == []


def test_exposure_rules_map_for_all_e02a_profiles():
    from fpg_core.domain import RoomType

    from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec, CoreConfigurationError

    payload = CoreConfigCodec().default_configuration().payload
    config = CoreConfigCodec().validate_for_flow(payload, "e02a").config.floor_plan_solver
    for stage in (config.initial, config.refinement_a, config.refinement_b):
        back = next(item for item in stage.hard_constraints if item.key == "exterior_wall_exposure")
        rule = back.settings["rules"][0]
        assert rule["room_types"] == (RoomType.HALLWAY, RoomType.KITCHEN)
        assert rule["requirement"]["minimum_length"] == 10
        assert (
            next(
                item for item in stage.soft_constraints if item.key == "exterior_wall_exposure"
            ).weight
            == 10
        )
    old_payload = json.loads(json.dumps(payload))
    old_payload["floor_plan_solver"]["initial"]["hard_constraints"][-1]["key"] = "back_exposure"
    with pytest.raises(CoreConfigurationError, match="Unknown hard constraint 'back_exposure'"):
        CoreConfigCodec().validate_payload(old_payload)
    payload["floor_plan_solver"]["initial"]["hard_constraints"][-1]["key"] = (
        "exterior_wall_exposure"
    )
    payload["floor_plan_solver"]["initial"]["hard_constraints"][-1]["settings"] = {
        "rules": [
            {
                "id": "bad",
                "room_types": ["bedroom"],
                "match": {"policy": "all"},
                "requirement": {"side": "north", "coverage": "full_wall"},
            }
        ]
    }
    with pytest.raises(CoreConfigurationError, match="side"):
        CoreConfigCodec().validate_payload(payload)


def test_inward_recess_config_and_debug_overlay():
    from fpg_core.floor_plan_scoring import (
        INWARD_RECESS_KEY,
        InwardRecessSettings,
        InwardRecessVisualizationData,
        RecessSectionVisualization,
        RecessVisualization,
    )

    from fpg_lab.core.serialization import to_jsonable
    from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec, CoreConfigurationError
    from fpg_lab.visualization.figures import add_inward_recesses, floor_plan

    payload = CoreConfigCodec().default_configuration().payload
    codec = CoreConfigCodec()
    config = codec.validate_for_flow(payload, "e02a").config.floor_plan_scoring
    settings = next(rule.settings for rule in config.evaluators if rule.key == INWARD_RECESS_KEY)
    assert settings == InwardRecessSettings()
    profile = next(
        rule
        for rule in payload["floor_plan_scoring"]["evaluators"]
        if rule["key"] == INWARD_RECESS_KEY
    )
    profile["settings"]["maximum_length"] = 20
    with pytest.raises(CoreConfigurationError, match="maximum_length"):
        codec.validate_payload(payload)

    ring = ((0, 0), (10, 0), (10, 20), (0, 20), (0, 0))
    region = RecessSectionVisualization(((ring,),), 10, 20, 200, 2, 1, (), (0, -1), (), ())
    section = RecessSectionVisualization(
        ((ring,),),
        10,
        20,
        200,
        2,
        1,
        (0,),
        (0, -1),
        (),
        ("INWARD_RECESS_DEPTH_TO_WIDTH_EXCEEDED",),
    )
    debug = InwardRecessVisualizationData(
        settings,
        (RecessVisualization(region, ((0, 20), (10, 20)), (0, -1), 1, (section,)),),
    )
    plot = floor_plan(None)
    add_inward_recesses(
        plot,
        {
            "evaluator_results": [
                {"evaluator_key": INWARD_RECESS_KEY, "visualization_payload": to_jsonable(debug)}
            ]
        },
    )
    assert [trace.name for trace in plot.data] == [
        "Recess 0 entrance",
        "Recess 0",
        "Recess 0, section 0",
    ]
    assert tuple(zip(plot.data[-1].x, plot.data[-1].y, strict=True)) == ring


def test_fully_shared_wall_rules_map_for_all_e02a_profiles():
    from fpg_core.domain import RoomType
    from fpg_core.floor_plan_solver import DEFAULT_PROFILES

    from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec, CoreConfigurationError

    key = "fully_shared_wall"
    payload = CoreConfigCodec().default_configuration().payload
    codec = CoreConfigCodec()
    config = codec.validate_for_flow(payload, "e02a").config.floor_plan_solver
    expected = [
        (
            (
                RoomType.BEDROOM,
                RoomType.BATHROOM,
                RoomType.ATTACHED_BATHROOM,
                RoomType.DINING_ROOM,
                RoomType.KITCHEN,
                RoomType.HALLWAY,
            ),
            2,
            0,
            None,
        ),
        ((RoomType.LIVING_ROOM,), 3, 0, {"room_type": RoomType.VERANDA, "exists": True}),
        ((RoomType.LIVING_ROOM,), 2, 0, {"room_type": RoomType.VERANDA, "exists": False}),
        ((RoomType.VERANDA,), 1, 0, None),
        ((RoomType.GARAGE,), 2, 10, None),
    ]
    for stage_name in ("initial", "refinement_a", "refinement_b"):
        stage = getattr(config, stage_name)
        assert all(
            item.key != key for item in getattr(DEFAULT_PROFILES, stage_name).hard_constraints
        )
        rules = next(item.settings["rules"] for item in stage.hard_constraints if item.key == key)
        assert all(rule["arrangement"] == "adjacent" for rule in rules)
        assert all(isinstance(value, RoomType) for rule in rules for value in rule["room_types"])
        assert rules[1]["when"]["room_type"] is RoomType.VERANDA
        assert rules[2]["when"]["room_type"] is RoomType.VERANDA
        assert [
            (
                rule["room_types"],
                rule["minimum_shared_sides"],
                rule["uncovered_length_tolerance"],
                rule.get("when"),
            )
            for rule in rules
        ] == expected

    hard_constraints = payload["floor_plan_solver"]["initial"]["hard_constraints"]
    rules = next(item["settings"]["rules"] for item in hard_constraints if item["key"] == key)
    rules[1]["when"]["room_type"] = "invalid"
    with pytest.raises(
        CoreConfigurationError, match=r"fully_shared_wall\.rules\[1\]\.when\.room_type"
    ):
        codec.validate_payload(payload)
    rules[1]["when"]["room_type"] = "veranda"
    rules[1]["when"]["exists"] = 1
    with pytest.raises(
        CoreConfigurationError, match=r"fully_shared_wall\.rules\[1\]\.when\.exists"
    ):
        codec.validate_payload(payload)
