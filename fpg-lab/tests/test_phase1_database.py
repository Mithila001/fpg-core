"""Phase 1 SQLite integrity fixtures. Every database lives under pytest's tmp_path."""

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import event, select

from fpg_lab.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from fpg_lab.database import maintenance as db
from fpg_lab.database.base import Base
from fpg_lab.database.models import (
    E02BRun,
    E02BSavedPlan,
    E02Run,
    FloorPlanTemplate,
    P01BIteration,
    P01BPreset,
    P01CandidateTrial,
    P01Experiment,
    SystemConfiguration,
)
from fpg_lab.database.session import Database
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.runtime import LabRuntime
from fpg_lab.services.common import SystemConfigurationService

PROFILE = SystemConfiguration.__tablename__


def reviewed_database(path, *, conflict=False):
    database = Database(f"sqlite:///{path}")
    Base.metadata.create_all(database.engine)
    ddl = (Path(__file__).parent / "revision1_floor_plan_run.sql").read_text(encoding="utf-8")
    with database.engine.begin() as connection:
        for statement in ddl.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
    codec = CoreConfigCodec()
    old = codec.default_configuration().payload
    del old["experiments"]["e03a"]
    for key in ("initial", "refinement_a", "refinement_b"):
        stage = old["floor_plan_solver"][key]
        stage["hard_constraints"] = [
            rule for rule in stage["hard_constraints"] if rule["key"] != "fully_shared_wall"
        ]
    custom = deepcopy(old)
    custom["floor_plan_solver"]["refinement_a"]["solver"]["max_time_seconds"] = 17
    if conflict:
        custom["floor_plan_solver"]["refinement_a"]["soft_constraints"][0]["weight"] = 99
    with database.session_factory() as session:
        session.add_all(
            [
                SystemConfiguration(
                    id=31,
                    name="research-default",
                    configuration_data=old,
                    config_hash=codec.hash_payload(old),
                    fpg_core_version="old",
                ),
                SystemConfiguration(
                    id=42,
                    name="custom",
                    is_active=True,
                    configuration_data=custom,
                    config_hash=codec.hash_payload(custom),
                    fpg_core_version="old",
                ),
            ]
        )
        session.commit()
    return database


def test_fresh_seed_and_inspection_are_repeatable(tmp_path):
    path = tmp_path / "fresh.db"
    database = Database(f"sqlite:///{path}")
    assert db.status(database)["compatibility"] == "empty"
    assert db.migrate(database, dry_run=True)["action"] == "initialize schema"
    assert not path.exists()
    assert db.migrate(database)["applied"]
    assert len(db.seed(database)["templates"]) == 5
    with database.session_factory() as session:
        service = SystemConfigurationService(session)
        profile = service.get_active()
        assert service.list(limit=25, offset=0)[1] == 1
        valid = service.validate(profile.id)
        for stage in ("initial", "refinement_a", "refinement_b"):
            assert "fully_shared_wall" in {
                rule["key"]
                for rule in valid.payload["floor_plan_solver"][stage]["hard_constraints"]
            }
        custom = service.duplicate(profile.id, "selected copy")
        service.activate(custom.id)
        custom_id = custom.id
        template = session.scalar(select(FloorPlanTemplate).order_by(FloorPlanTemplate.id))
        template.description = "tuned"
        session.commit()
        template_id = template.id
        before = db.record(database, PROFILE, custom_id)
        for key, value in db.seed(database).items():
            if key != "target":
                assert value == []
        assert (
            db.record(database, FloorPlanTemplate.__tablename__, template_id)["description"]
            == "tuned"
        )
        assert db.profiles(database, "validate") == {"checked": 2, "errors": []}
        assert db.profiles(database, "list")["records"]
        assert db.record(database, PROFILE, custom_id) == before
        assert service.resolve().id == custom_id
        with pytest.raises(NotFoundError, match="not found"):
            service.for_flow(999, "e02b")
        broken = deepcopy(custom.configuration_data)
        broken["floor_plan_scoring"] = None
        custom.configuration_data = broken
        custom.config_hash = service.codec.hash_payload(broken)
        session.commit()
        before = db.record(database, PROFILE, custom_id)
        with pytest.raises(InvalidInputError, match="floor_plan_scoring"):
            service.for_flow(None, "e02b")
        assert service.for_flow(None, "e03a")[0].id == custom_id
        assert db.profiles(database, "validate")["errors"][0]["id"] == custom_id
        assert db.record(database, PROFILE, custom_id) == before
        custom.is_active = False
        session.commit()
        with pytest.raises(NotFoundError, match="No active profile"):
            service.for_flow(None, "e03a")
        assert service.list(limit=25, offset=0)[1] == 2
    database.dispose()


def test_upgrade_preserves_identity_custom_values_and_atomic_conflicts(tmp_path):
    database = reviewed_database(tmp_path / "upgrade.db")
    try:
        before = db.record(database, PROFILE, 42)
        assert (
            db.migrate(database, dry_run=True)["profiles"][0]["action"] == "promote E02A baseline"
        )
        assert db.record(database, PROFILE, 42) == before
        assert db.migrate(database)["applied"]
        assert db.record(database, PROFILE, 31)["name"] == "research-default"
        result = db.record(database, PROFILE, 42)
        assert result["is_active"]
        upgraded = result["configuration_data"]
        assert upgraded["experiments"]["e03a"]
        stage = upgraded["floor_plan_solver"]["refinement_a"]
        assert stage["solver"]["max_time_seconds"] == 17
        assert any(rule["key"] == "fully_shared_wall" for rule in stage["hard_constraints"])
        assert db.migrate(database)["action"] == "none"
        assert db.record(database, PROFILE, 42) == result
    finally:
        database.dispose()

    database = reviewed_database(tmp_path / "conflict.db", conflict=True)
    try:
        primary = db.record(database, PROFILE, 31)
        custom = db.record(database, PROFILE, 42)
        planned = db.migrate(database, dry_run=True)
        rejected = db.migrate(database)
        assert planned["conflicts"] == rejected["conflicts"]
        assert (
            "floor_plan_solver.refinement_a.soft_constraints.0.weight"
            in rejected["conflicts"][0]["error"]
        )
        assert db.status(database)["revision"] == 0
        assert db.record(database, PROFILE, 31) == primary
        assert db.record(database, PROFILE, 42) == custom
    finally:
        database.dispose()


def test_ddl_and_profile_updates_roll_back_on_failure(tmp_path):
    fresh = Database(f"sqlite:///{tmp_path / 'ddl-rollback.db'}")
    upgrade = reviewed_database(tmp_path / "profile-rollback.db")
    before = db.record(upgrade, PROFILE, 31)

    def fail_revision(_conn, _cursor, statement, *_):
        if statement.startswith("PRAGMA user_version ="):
            raise RuntimeError("simulated revision write failure")

    for database, expected in ((fresh, "empty"), (upgrade, "upgrade_required")):
        try:
            event.listen(database.engine, "before_cursor_execute", fail_revision)
            with pytest.raises(RuntimeError, match="simulated revision write failure"):
                db.migrate(database)
            assert db.status(database)["compatibility"] == expected
        finally:
            event.remove(database.engine, "before_cursor_execute", fail_revision)
            database.dispose()
    assert db.record(upgrade, PROFILE, 31) == before
    upgrade.dispose()


def test_unknown_unversioned_structure_is_refused(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'unknown.db'}")
    try:
        with database.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE foreign_data (id INTEGER PRIMARY KEY)")
        with pytest.raises(ValueError, match="Unknown Lab database schema"):
            db.migrate(database)
        assert db.status(database)["compatibility"] == "unknown"
        with database.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 0
            assert connection.exec_driver_sql("SELECT count(*) FROM foreign_data").scalar_one() == 0
    finally:
        database.dispose()


def test_resets_preserve_reusable_records_and_require_stopped_execution(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'reset.db'}")
    db.migrate(database)
    db.seed(database)
    with database.session_factory() as session:
        profile = SystemConfigurationService(session).get_active()
        experiment = P01Experiment(
            flow_type="p01b",
            status="completed",
            floor_plan_request={},
            system_configuration_id=profile.id,
            system_configuration_snapshot={},
            system_configuration_hash=profile.config_hash,
            fpg_core_version=profile.fpg_core_version,
        )
        session.add(experiment)
        session.flush()
        trial = P01CandidateTrial(experiment_id=experiment.id, trial_no=1, status="completed")
        session.add(trial)
        session.flush()
        session.add_all(
            [
                E02Run(status="completed", snapshot={}, cases=[{"fixture": True}]),
                E02BRun(status="completed", snapshot={}),
                P01BIteration(experiment_id=experiment.id, number=1, status="completed"),
                P01BPreset(name="retain preset", data={"fixture": True}),
                E02BSavedPlan(name="retain plan", document={"fixture": True}),
            ]
        )
        session.commit()
    with LabRuntime(database_url=database.database_url):
        with pytest.raises(ConflictError, match="Stop Lab execution"):
            db.reset(database, scope="runs")
    counts = db.status(database)["counts"]
    assert db.reset(database, scope="runs")["removed"] == dict.fromkeys(db.RUN_TABLES, 1)
    remaining = db.status(database)["counts"]
    assert all(
        remaining[key] == (0 if key in db.RUN_TABLES else value) for key, value in counts.items()
    )
    assert db.reset(database, scope="all")["seeded"]["profiles"]
    final = db.status(database)["counts"]
    assert final["fpg_e02b_saved_plan"] == final["fpg_p01b_preset"] == 0
    assert final[PROFILE] == 1
    assert final[FloorPlanTemplate.__tablename__] == 5
    database.dispose()


def test_revision1_removes_obsolete_runs_atomically(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'revision1.db'}")
    db.migrate(database)
    db.seed(database)
    ddl = (Path(__file__).parent / "revision1_floor_plan_run.sql").read_text(encoding="utf-8")
    with database.engine.begin() as connection:
        for statement in ddl.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        connection.exec_driver_sql("PRAGMA user_version = 1")
    with database.session_factory() as session:
        profile = SystemConfigurationService(session).get_active()
        for flow, hints in (("p01c", None), ("p01b", {"preset": {"version": 1}})):
            session.add(P01Experiment(
                flow_type=flow, status="completed", floor_plan_request={}, hint_points=hints,
                system_configuration_id=profile.id, system_configuration_snapshot={},
                system_configuration_hash=profile.config_hash, fpg_core_version=profile.fpg_core_version,
            ))
        session.commit()
        rows = list(session.scalars(select(P01Experiment).order_by(P01Experiment.id)))
        legacy_id, current_id, profile_id = rows[0].id, rows[1].id, profile.id
    with database.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO fpg_p01_floor_plan_run (experiment_id, status, duration_ms, created_at) "
            "VALUES (?, 'completed', 0, CURRENT_TIMESTAMP)", (legacy_id,)
        )
    planned = db.migrate(database, dry_run=True)
    assert planned["removed_floor_plan_runs"] == planned["removed_legacy_experiments"] == 1
    assert db.status(database)["revision"] == 1
    def fail_revision(_conn, _cursor, statement, *_):
        if statement.startswith("PRAGMA user_version ="):
            raise RuntimeError("revision failure")
    event.listen(database.engine, "before_cursor_execute", fail_revision)
    with pytest.raises(RuntimeError, match="revision failure"):
        db.migrate(database)
    event.remove(database.engine, "before_cursor_execute", fail_revision)
    assert db.status(database)["revision"] == 1
    assert db.migrate(database)["applied"]
    with database.session_factory() as session:
        assert session.get(P01Experiment, legacy_id) is None
        assert session.get(P01Experiment, current_id) is not None
        assert session.get(SystemConfiguration, profile_id) is not None
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name = 'fpg_p01_floor_plan_run'").first() is None
    database.dispose()


def test_revision2_reseeds_relationship_evaluator_without_reset(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'revision2.db'}")
    codec = CoreConfigCodec()
    assert db.migrate(database)["applied"]
    with database.session_factory() as session:
        profile = SystemConfigurationService(session).get_active()
        profile_id = profile.id
        old = deepcopy(profile.configuration_data)
        scoring = old["floor_plan_scoring"]
        scoring["groups"][1]["weight"] = 3
        scoring["evaluators"] = [
            rule for rule in scoring["evaluators"] if rule["key"] != "room_relationship_quality"
        ]
        scoring["evaluators"].extend([
            {
                "key": "required_adjacency", "group_key": "critical", "enabled": True,
                "order": 20, "weight": 1, "minimum_score": 100,
                "settings": {"minimum_shared_boundary": 10, "tolerance": 1e-6},
            },
            {
                "key": "kitchen_dining_proximity", "group_key": "functional", "enabled": True,
                "order": 20, "weight": 1, "minimum_score": None,
                "settings": {"minimum_shared_boundary": 10, "maximum_distance": 2000,
                             "tolerance": 1e-6},
            },
        ])
        profile.configuration_data = old
        profile.config_hash = old_hash = codec.hash_payload(old)
        session.commit()
    with database.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version = 2")

    planned = db.migrate(database, dry_run=True)
    assert not planned["applied"] and not planned["conflicts"]
    assert [item["id"] for item in planned["profiles"]] == [profile_id]
    assert db.status(database)["revision"] == 2
    assert db.migrate(database)["applied"]
    assert db.status(database)["revision"] == 4
    assert not db.migrate(database)["applied"]
    with database.session_factory() as session:
        updated = session.get(SystemConfiguration, profile_id)
        assert updated.is_active and updated.config_hash != old_hash
        validated = codec.validate_payload(updated.configuration_data)
        scoring = validated.payload["floor_plan_scoring"]
        assert scoring["groups"][1]["weight"] == 3
        assert {rule["key"] for rule in scoring["evaluators"]} == {
            "geometry_integrity", "enclosed_voids", "inward_recess",
            "room_size_consistency", "room_relationship_quality",
        }
        assert scoring["evaluators"][-1]["settings"] == (
            codec.default_configuration().payload["floor_plan_scoring"]["evaluators"][-1]["settings"]
        )
    database.dispose()
