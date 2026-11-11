from sqlalchemy import select
from test_lab import PLAN, Execution, RecordingAdapter, Solve, create_profile, payload, wait

from fpg_lab.database.models import P01BIteration, P01BPreset
from fpg_lab.integrations.fpg_core.p01b_input import export_trial, validate_export
from fpg_lab.runtime import LabRuntime


def test_export_and_independent_iterations(tmp_path, monkeypatch):
    calls = []

    def solve(request, *, mode):
        calls.append(request)
        return Execution(Solve(PLAN))

    monkeypatch.setattr("fpg_lab.flows.p01b.generate_floor_plan", solve)
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        older_trial = dict(source["trials"][0])
        older_trial["circulation_data"] = dict(older_trial["circulation_data"])
        older_trial["circulation_data"].pop("lab_generation_specification")
        assert (
            export_trial(source["experiment"], older_trial)["specification"]
            == document["specification"]
        )
        spec = validate_export(document)
        assert {p["room_id"] for p in document["candidate"]["points"]} == {r.id for r in spec.rooms}
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b",
            {
                "preset_id": preset_id,
                "initial_time_limit": 1,
                "iterations": 2,
                "refinement_rounds": 2,
                "disable_hints": True,
            },
        )
        result = wait(runtime, "p01b", experiment_id)
        assert result["experiment"]["status"] == "completed"
        with runtime.database.session_factory() as session:
            session.delete(session.get(P01BPreset, preset_id))
            session.commit()
            rows = list(
                session.scalars(
                    select(P01BIteration)
                    .where(P01BIteration.experiment_id == experiment_id)
                    .order_by(P01BIteration.number)
                )
            )
            assert len(rows) == 2
            assert all(row.status == "completed" for row in rows), [row.error for row in rows]
            assert all(
                [s["name"] for s in row.stages]
                == ["Initial", "Refinement 1", "Refinement 2", "Post-process"]
                for row in rows
            )
            assert all(row.scoring["result"]["total_score"] == 90 for row in rows)
        assert len(calls) == 2 and all(not call.candidate_hints for call in calls)
        assert calls[0].config == calls[1].config


def test_failed_refinement_keeps_initial_and_continues(tmp_path, monkeypatch):
    class FailingAdapter(RecordingAdapter):
        def refine_floor_plan(self, specification, floor_plan, *, profile, debug):
            raise RuntimeError("refinement broke")

    monkeypatch.setattr(
        "fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN))
    )
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'lab.db'}", adapter_factory=FailingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b",
            {
                "preset_id": preset_id,
                "initial_time_limit": 1,
                "iterations": 2,
                "refinement_rounds": 1,
            },
        )
        result = wait(runtime, "p01b", experiment_id)
        assert result["experiment"]["failed_trial_count"] == 2
        with runtime.database.session_factory() as session:
            rows = list(
                session.scalars(
                    select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
                )
            )
            assert len(rows) == 2
            assert all(
                row.status == "failed" and row.error["stage"] == "refinement_1" for row in rows
            )
            assert all(row.stages[0]["data"]["result"]["floor_plan"] == PLAN for row in rows)


def test_real_initial_solver_with_and_without_hints(tmp_path):
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'real.db'}", adapter_factory=RecordingAdapter
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="real", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        for disabled in (False, True):
            experiment_id = runtime.start_experiment(
                "p01b",
                {"preset_id": preset_id, "initial_time_limit": 0.2, "disable_hints": disabled},
            )
            result = wait(runtime, "p01b", experiment_id)
            assert result["experiment"]["status"] == "completed"
            with runtime.database.session_factory() as session:
                row = session.scalar(
                    select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
                )
                assert row.stages[0]["name"] == "Initial"
                assert "result" in row.stages[0]["data"], row.error


def test_scoring_failure_retains_post_processed_plan(tmp_path, monkeypatch):
    class FailingScore(RecordingAdapter):
        def score_completed_floor_plan(self, floor_plan, specification, *, debug):
            raise RuntimeError("scoring unavailable")

    monkeypatch.setattr(
        "fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN))
    )
    with LabRuntime(
        database_url=f"sqlite:///{tmp_path / 'score.db'}", adapter_factory=FailingScore
    ) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="test", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment(
            "p01b", {"preset_id": preset_id, "initial_time_limit": 1, "refinement_rounds": 0}
        )
        wait(runtime, "p01b", experiment_id)
        with runtime.database.session_factory() as session:
            row = session.scalar(
                select(P01BIteration).where(P01BIteration.experiment_id == experiment_id)
            )
            assert row.error["stage"] == "scoring"
            assert [stage["name"] for stage in row.stages] == ["Initial", "Post-process"]
            assert row.stages[-1]["data"]["result"]["floor_plan"] == PLAN


def test_p01c_scores_the_opening_plan_and_keeps_it_on_score_failure(tmp_path, monkeypatch):
    class OpeningsAdapter(RecordingAdapter):
        def generate_floor_plan_openings(self, floor_plan, *, debug):
            return Execution(Solve({**floor_plan, "openings": [{"id": "door"}]}))

        def score_completed_floor_plan(self, floor_plan, specification, *, debug):
            assert floor_plan["openings"] == [{"id": "door"}]
            raise RuntimeError("scoring unavailable")

    monkeypatch.setattr("fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN)))
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'p01c.db'}", adapter_factory=OpeningsAdapter) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="for-p01c", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment("p01c", {"preset_id": preset_id, "initial_time_limit": 1})
        result = wait(runtime, "p01c", experiment_id)
        assert result["experiment"]["failed_trial_count"] == 1
        with runtime.database.session_factory() as session:
            row = session.scalar(select(P01BIteration).where(P01BIteration.experiment_id == experiment_id))
            assert [stage["name"] for stage in row.stages] == ["Initial", "Post-process", "Openings"]
            assert row.stages[-1]["data"]["result"]["floor_plan"]["openings"] == [{"id": "door"}]
            assert row.error["stage"] == "scoring"


def test_saved_profile_migration_preserves_run_snapshot(tmp_path):
    from copy import deepcopy

    from fpg_lab.database.models import P01Experiment, SystemConfiguration

    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    runtime = LabRuntime(database_url=database_url)
    runtime.database.create_schema()
    old = deepcopy(runtime.codec.default_configuration().payload)
    old["preprocessing"]["hallway_min_width"] = 8
    old["openings"]["dimensions"]["door_width"] = 8
    old["experiments"]["p01c"] = {"floor_plan_generation_score_threshold": 80}
    for stage in old["floor_plan_solver"].values():
        if isinstance(stage, dict):
            for constraint in stage.get("hard_constraints", []):
                if constraint["key"] == "hallway_dimensions":
                    constraint["settings"]["minimum_width"] = 8
    with runtime.database.session_factory() as session:
        config = SystemConfiguration(name="old", configuration_data=deepcopy(old),
                                     schema_version="6", config_hash="old", fpg_core_version="old", is_active=True)
        session.add(config)
        session.flush()
        experiment = P01Experiment(flow_type="p01a", status="completed", floor_plan_request={},
                                   system_configuration_id=config.id, system_configuration_snapshot=deepcopy(old),
                                   system_configuration_hash="old", fpg_core_version="old")
        session.add(experiment)
        session.commit()
        config_id, experiment_id = config.id, experiment.id
    runtime.start()
    with runtime.database.session_factory() as session:
        migrated = session.get(SystemConfiguration, config_id)
        assert migrated.configuration_data["preprocessing"]["hallway_min_width"] == 10
        assert migrated.configuration_data["openings"]["dimensions"]["door_width"] == 10
        assert "p01c" not in migrated.configuration_data["experiments"]
        assert migrated.config_hash != "old"
        assert session.get(P01Experiment, experiment_id).system_configuration_snapshot == old
    runtime.close()


def test_p01c_opening_failure_stops_iteration(tmp_path, monkeypatch):
    class FailedOpenings(RecordingAdapter):
        def generate_floor_plan_openings(self, floor_plan, *, debug):
            raise RuntimeError("cannot place openings")

        def score_completed_floor_plan(self, floor_plan, specification, *, debug):
            raise AssertionError("scoring must not run after opening failure")

    monkeypatch.setattr("fpg_lab.flows.p01b.generate_floor_plan", lambda request, *, mode: Execution(Solve(PLAN)))
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'openings.db'}", adapter_factory=FailedOpenings) as runtime:
        create_profile(runtime)
        source = wait(runtime, "p01a", runtime.start_experiment("p01a", payload("p01a")))
        document = export_trial(source["experiment"], source["trials"][0])
        with runtime.database.session_factory() as session:
            preset = P01BPreset(name="p01c-opening-failure", data=document)
            session.add(preset)
            session.commit()
            preset_id = preset.id
        experiment_id = runtime.start_experiment("p01c", {"preset_id": preset_id, "initial_time_limit": 1})
        wait(runtime, "p01c", experiment_id)
        with runtime.database.session_factory() as session:
            row = session.scalar(select(P01BIteration).where(P01BIteration.experiment_id == experiment_id))
            assert row.status == "failed"
            assert row.error["stage"] == "openings"
            assert row.stages[-1]["name"] == "Openings"
            assert row.scoring is None
