"""Explicit SQLite maintenance for the reviewed Lab schema."""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from fpg_lab.core.exceptions import AppError, ConflictError
from fpg_lab.core.settings import ROOT
from fpg_lab.database.base import Base
from fpg_lab.database.models import FloorPlanTemplate, SystemConfiguration
from fpg_lab.database.session import Database
from fpg_lab.inputs import FloorPlanTemplateCreate
from fpg_lab.integrations.fpg_core.config_codec import COMPLETE_SECTIONS, CoreConfigCodec
from fpg_lab.services.common import (
    PRIMARY_PROFILE,
    SystemConfigurationService,
    seed_namespace_registry,
)

REVISION = 5
# Revision 5 adds the front wall setback policy to saved solver profiles; DDL is unchanged.
REVIEWED_SCHEMA_HASH = "26cf6f2e4a498ea86ac7adb6211ccaf13fd024ff6d1eb99c12f0de9f651d955a"
CURRENT_SCHEMA_HASH = "7c271e966b5efc5981e5bc0b0aee9ac880285ff3634306424d81cd5bc52c47f5"
RUN_TABLES = {
    "fpg_e02_run",
    "fpg_e02b_run",
    "fpg_p01_experiment",
    "fpg_p01_candidate_trial",
    "fpg_p01b_iteration",
}


def database_path(database: Database) -> Path | None:
    url = make_url(database.database_url)
    if url.get_backend_name() != "sqlite" or url.query:
        raise ValueError("Use a plain SQLite database URL, such as sqlite:///./data/fpg_lab.db.")
    return Path(url.database).resolve() if url.database not in (None, "", ":memory:") else None


@contextmanager
def execution_lock(database: Database):
    """Keep migration/reset and LabRuntime mutually exclusive for local files."""
    path = database_path(database)
    if path is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".execution.lock").open("a+b") as handle:
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ConflictError(
                "lab_execution_active", f"Stop Lab execution for {path} first."
            ) from exc
        yield  # Closing the handle releases the OS lock, including on failure.


def _schema(connection):
    return {
        name: " ".join(sql.split())
        for name, sql in connection.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT GLOB 'sqlite_*'"
        )
    }


def _matches_schema(schema, expected):
    encoded = json.dumps(schema, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest() == expected


def _state(connection):
    revision = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
    schema = _schema(connection)
    if revision > REVISION:
        return revision, "newer"
    if not schema and revision == 0:
        return revision, "empty"
    expected = CURRENT_SCHEMA_HASH if revision >= 2 else REVIEWED_SCHEMA_HASH
    if not _matches_schema(schema, expected):
        return revision, "unknown"
    return revision, "current" if revision == REVISION else "upgrade_required"


def _require(state, database: Database | None = None):
    revision, compatibility = state
    if compatibility == "current":
        return
    if compatibility in {"empty", "upgrade_required"}:
        command = "python -m scripts.lab_db"
        if database is not None and (path := database_path(database)) is not None:
            command += f' --database-url "sqlite:///{path.as_posix()}"'
        raise ValueError(
            f"Database needs maintenance. From fpg-lab, run {command} migrate --json, "
            f"then {command} seed --json."
        )
    raise ValueError(
        f"{compatibility.capitalize()} Lab database schema (revision {revision}). "
        "Check the target URL or use a new SQLite database with this checkout."
    )


def require_current(database: Database):
    path = database_path(database)
    if path is not None and not path.is_file():
        _require((0, "empty"), database)
    with database.engine.connect() as connection:
        _require(_state(connection), database)
    with database.session_factory() as session:
        SystemConfigurationService(session).resolve()


def _counts(connection, names=None):
    return {
        table.name: connection.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
        if names is None or table.name in names
    }


def status(database: Database):
    path = database_path(database)
    result = {
        "target": str(path or ":memory:"),
        "revision": 0,
        "supported_revision": REVISION,
        "compatibility": "empty",
        "counts": {},
        "profile_revisions": {},
    }
    if path is not None and not path.exists():
        return result
    with database.engine.connect() as connection:
        revision, compatibility = _state(connection)
        result.update(revision=revision, compatibility=compatibility)
        if compatibility in {"current", "upgrade_required"}:
            result["counts"] = _counts(connection)
            result["profile_revisions"] = dict(
                connection.execute(
                    select(SystemConfiguration.schema_version, func.count()).group_by(
                        SystemConfiguration.schema_version
                    )
                ).all()
            )
    return result


@contextmanager
def _write(database):
    with database.engine.connect() as connection:
        # Explicit BEGIN also makes SQLite DDL and the revision marker transactional.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(bind=connection) as session:
            yield connection, session
            session.flush()
        connection.commit()


def _seed_document():
    return json.loads((ROOT / "seed/system_configuration.default.json").read_text(encoding="utf-8"))


def _seed_profile(session, source, validated):
    record = SystemConfiguration(
        name=PRIMARY_PROFILE,
        description=source["description"],
        is_active=session.scalar(
            select(SystemConfiguration.id).where(SystemConfiguration.is_active)
        )
        is None,
        **SystemConfigurationService.configuration_values(validated),
    )
    session.add(record)
    session.flush()
    return record


def _seed(session):
    changes = {"namespaces": seed_namespace_registry(session), "profiles": [], "templates": []}
    if (
        session.scalar(
            select(SystemConfiguration.id).where(SystemConfiguration.name == PRIMARY_PROFILE)
        )
        is None
    ):
        source = _seed_document()
        validated = CoreConfigCodec().validate_payload(source["configuration_data"])
        changes["profiles"].append(_seed_profile(session, source, validated).id)
    existing = set(session.scalars(select(FloorPlanTemplate.name)))
    for path in sorted((ROOT / "seed").glob("floor_plan_template.*.json")):
        payload = FloorPlanTemplateCreate.model_validate_json(path.read_bytes())
        if payload.name not in existing:
            session.add(FloorPlanTemplate(**payload.model_dump()))
            changes["templates"].append(payload.name)
            existing.add(payload.name)
    return changes


def seed(database: Database):
    require_current_schema(database)
    with _write(database) as (connection, session):
        _require(_state(connection))
        return {"target": str(database_path(database) or ":memory:"), **_seed(session)}


def _upgrade_profile(original, baseline):
    data = deepcopy(original)
    for key in COMPLETE_SECTIONS:
        if data.get(key) is None:
            data[key] = deepcopy(baseline[key])
    preprocessing = data["preprocessing"]
    if preprocessing.get("hallway_min_width", 10) < 10:
        preprocessing["hallway_min_width"] = 10.0
    if data.get("experiments") is None:
        data["experiments"] = {}
    experiments = data["experiments"]
    if not isinstance(experiments, dict):
        raise ValueError("experiments: expected a JSON object")
    experiments.pop("p01c", None)
    if experiments.get("e03a") is None:
        experiments["e03a"] = deepcopy(baseline["experiments"]["e03a"])
    for stage_name in ("initial", "refinement_a", "refinement_b", "p01b_refinement"):
        stage = (
            experiments.get(stage_name)
            if stage_name == "p01b_refinement"
            else data["floor_plan_solver"].get(stage_name)
        )
        base_stage = baseline["floor_plan_solver"][
            "refinement_a" if stage_name == "p01b_refinement" else stage_name
        ]
        if stage is None:
            if stage_name != "p01b_refinement":
                data["floor_plan_solver"][stage_name] = deepcopy(base_stage)
            continue
        path = (
            "experiments." if stage_name == "p01b_refinement" else "floor_plan_solver."
        ) + stage_name
        rules = stage.get("hard_constraints")
        if not isinstance(rules, list):
            raise ValueError(f"{path}.hard_constraints: expected a rule array")
        keys = [rule["key"] for rule in rules]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{path}.hard_constraints: duplicate rule key")
        if "fully_shared_wall" not in keys:
            rules.append(
                deepcopy(
                    next(
                        rule
                        for rule in base_stage["hard_constraints"]
                        if rule["key"] == "fully_shared_wall"
                    )
                )
            )
        for rule in rules:
            if rule["key"] == "hallway_dimensions":
                settings = rule.setdefault("settings", {})
                settings["minimum_width"] = max(10, settings.get("minimum_width", 10))
                settings["maximum_width"] = max(
                    settings["minimum_width"], settings.get("maximum_width", 10)
                )
    dimensions = data["openings"].get("dimensions") or {}
    if dimensions.get("door_width") == 8:
        dimensions["door_width"] = 10.0
    return data


def _reseed_relationship_evaluator(data, baseline):
    scoring = data.get("floor_plan_scoring")
    if scoring is None:
        return data
    obsolete = {"required_adjacency", "kitchen_dining_proximity"}
    rules = scoring["evaluators"]
    keys = {rule["key"] for rule in rules}
    if keys & obsolete:
        scoring["evaluators"] = [rule for rule in rules if rule["key"] not in obsolete]
        if "room_relationship_quality" not in keys and "kitchen_dining_proximity" in keys:
            scoring["evaluators"].append(
                deepcopy(
                    next(
                        rule
                        for rule in baseline["evaluators"]
                        if rule["key"] == "room_relationship_quality"
                    )
                )
            )
    return data


def _upgrade_post_processing(data, baseline):
    processing = data.get("post_processing")
    if processing is None:
        return data
    processors = processing["processors"]
    defaults = next(
        item for item in baseline["processors"] if item["processor_id"] == "wall_extension"
    )
    for item in processors:
        if item["processor_id"] != "wall_extension" or "exterior_steps" in item["config"]:
            continue
        previous = item["config"]
        replacement = deepcopy(defaults["config"])
        replacement["rules"] = [
            {"room_type": rule["room_type"], "max_distance": rule["max_distance"]}
            for rule in previous["rules"]
        ]
        item["config"] = replacement
    processors = [item for item in processors if item["processor_id"] != "veranda_adjustment"]
    order = {item["processor_id"]: index for index, item in enumerate(baseline["processors"])}
    processing["processors"] = sorted(
        processors, key=lambda item: order.get(item["processor_id"], len(order))
    )
    return data


def _upgrade_front_wall_setback(data, baseline):
    stages = data.get("floor_plan_solver") or {}
    base_stages = baseline["floor_plan_solver"]
    for name in ("initial", "refinement_a", "refinement_b", "p01b_refinement"):
        stage = (
            (data.get("experiments") or {}).get(name)
            if name == "p01b_refinement"
            else stages.get(name)
        )
        if stage is None:
            continue
        rules = stage["hard_constraints"]
        if not any(rule["key"] == "front_wall_setback" for rule in rules):
            source = base_stages["refinement_a" if name == "p01b_refinement" else name]
            rules.append(
                deepcopy(
                    next(
                        rule
                        for rule in source["hard_constraints"]
                        if rule["key"] == "front_wall_setback"
                    )
                )
            )
    return data


def _migration(connection, session, report, *, dry_run):
    revision, compatibility = _state(connection)
    report.update(from_revision=revision, compatibility=compatibility)
    if compatibility == "current":
        return
    if compatibility not in {"empty", "upgrade_required"}:
        _require((revision, compatibility))
    source = _seed_document()
    codec = CoreConfigCodec()
    baseline = codec.validate_payload(source["configuration_data"])
    rows = (
        list(session.scalars(select(SystemConfiguration)))
        if compatibility == "upgrade_required"
        else []
    )
    proposals = []
    for row in rows:
        try:
            if row.schema_version != "6" or row.configuration_data.get("schema_version") != 6:
                raise ValueError("schema_version: only reviewed version 6 profiles can be upgraded")
            primary = revision == 0 and row.name == PRIMARY_PROFILE
            if primary:
                validated = baseline
            else:
                data = deepcopy(row.configuration_data)
                if revision == 0:
                    data = _upgrade_profile(data, baseline.payload)
                if revision < 3:
                    data = _reseed_relationship_evaluator(
                        data, baseline.payload["floor_plan_scoring"]
                    )
                if revision < 4:
                    data = _upgrade_post_processing(
                        data, baseline.payload["post_processing"]
                    )
                data = _upgrade_front_wall_setback(data, baseline.payload)
                validated = codec.validate_payload(data)
            values = SystemConfigurationService.configuration_values(validated)
            if any(getattr(row, key) != value for key, value in values.items()):
                proposals.append((row, values))
                report["profiles"].append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "action": "promote E02A baseline" if primary else "upgrade saved profile",
                        "old_hash": row.config_hash,
                        "new_hash": validated.config_hash,
                    }
                )
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            report["conflicts"].append({"id": row.id, "name": row.name, "error": str(exc)})
    if not any(row.name == PRIMARY_PROFILE for row in rows):
        report["profiles"].append({"name": PRIMARY_PROFILE, "action": "create E02A baseline"})
    report["action"] = "initialize schema" if compatibility == "empty" else "upgrade saved profiles"
    if compatibility == "upgrade_required" and revision < 2:
        report["removed_floor_plan_runs"] = connection.exec_driver_sql(
            "SELECT count(*) FROM fpg_p01_floor_plan_run"
        ).scalar_one()
        report["removed_legacy_experiments"] = connection.exec_driver_sql(
            "SELECT count(*) FROM fpg_p01_experiment WHERE flow_type IN ('p01b', 'p01c') "
            "AND (hint_points IS NULL OR json_extract(hint_points, '$.preset') IS NULL)"
        ).scalar_one()
    if report["conflicts"] or dry_run:
        return
    if compatibility == "upgrade_required" and revision < 2:
        connection.exec_driver_sql("DROP TABLE fpg_p01_floor_plan_run")
        connection.exec_driver_sql(
            "DELETE FROM fpg_p01_experiment WHERE flow_type IN ('p01b', 'p01c') "
            "AND (hint_points IS NULL OR json_extract(hint_points, '$.preset') IS NULL)"
        )
    if compatibility == "empty":
        Base.metadata.create_all(connection)
        if not _matches_schema(_schema(connection), CURRENT_SCHEMA_HASH):
            raise ValueError("Generated schema differs from supported Lab schema.")
    for row, values in proposals:
        for key, value in values.items():
            setattr(row, key, value)
    if not any(row.name == PRIMARY_PROFILE for row in rows):
        report["profiles"][-1]["id"] = _seed_profile(session, source, baseline).id
    elif not any(row.is_active for row in rows):
        primary = next(row for row in rows if row.name == PRIMARY_PROFILE)
        primary.is_active = True
        report["profiles"].append({"id": primary.id, "name": primary.name, "action": "activate"})
    session.flush()
    connection.exec_driver_sql(f"PRAGMA user_version = {REVISION}")
    report["applied"] = True


def migrate(database: Database, *, dry_run=False):
    path = database_path(database)
    report = {
        "target": str(path or ":memory:"),
        "to_revision": REVISION,
        "profiles": [],
        "conflicts": [],
        "applied": False,
        "action": "none",
    }
    if dry_run and path is not None and not path.exists():
        empty = Database("sqlite://")
        try:
            report.update(migrate(empty, dry_run=True), target=str(path))
        finally:
            empty.dispose()
        return report
    with nullcontext() if dry_run else execution_lock(database):
        if dry_run:
            with database.engine.connect() as connection, Session(bind=connection) as session:
                connection.exec_driver_sql("BEGIN")
                _migration(connection, session, report, dry_run=True)
        else:
            with _write(database) as (connection, session):
                _migration(connection, session, report, dry_run=False)
    return report


def reset(database: Database, *, scope: str):
    if scope not in {"runs", "all"}:
        raise ValueError("Reset scope must be runs or all.")
    with execution_lock(database), _write(database) as (connection, session):
        state = _state(connection)
        if scope == "runs" or state[1] not in {"empty", "upgrade_required"}:
            _require(state)
        tables = Base.metadata.sorted_tables
        names = RUN_TABLES if scope == "runs" else None
        removed = {} if state[1] == "empty" else _counts(connection, names)
        result = {
            "target": str(database_path(database) or ":memory:"),
            "scope": scope,
            "removed": removed,
        }
        if scope == "runs":
            for table in reversed(tables):
                if table.name in RUN_TABLES:
                    connection.execute(delete(table))
        else:
            if state[1] == "upgrade_required" and state[0] < 2:
                connection.exec_driver_sql("DROP TABLE fpg_p01_floor_plan_run")
            Base.metadata.drop_all(connection)
            Base.metadata.create_all(connection)
            if not _matches_schema(_schema(connection), CURRENT_SCHEMA_HASH):
                raise ValueError("Generated schema differs from supported Lab schema.")
            result["seeded"] = _seed(session)
            session.flush()
            connection.exec_driver_sql(f"PRAGMA user_version = {REVISION}")
        return result


# Only mapped Lab tables can be inspected. Collection reads select scalar metadata.
RECORD_TABLES = dict(Base.metadata.tables)
PROFILE_METADATA = (
    "id",
    "name",
    "description",
    "is_active",
    "schema_version",
    "fpg_core_version",
    "config_hash",
    "created_at",
    "updated_at",
)
RECORD_METADATA = (
    *PROFILE_METADATA,
    "tag",
    "kind",
    "flow_type",
    "status",
    "experiment_id",
    "trial_no",
    "number",
    "source_trial_id",
    "system_configuration_id",
    "finished_at",
)


def _page(limit, offset):
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("Use a limit from 1 to 500 and a nonnegative offset.")


@contextmanager
def _inspect(database):
    path = database_path(database)
    if path is not None and not path.is_file():
        _require((0, "empty"))
    with database.engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        state = _state(connection)
        if state[1] != "upgrade_required":
            _require(state)
        yield connection, state


def records(database, table, *, limit=25, offset=0, status=None, experiment_id=None):
    _page(limit, offset)
    source = RECORD_TABLES[table]
    statement = select(*(source.c[name] for name in RECORD_METADATA if name in source.c))
    for name, value in (("status", status), ("experiment_id", experiment_id)):
        if value is not None:
            if name not in source.c:
                raise ValueError(f"{table} does not have a {name} filter.")
            statement = statement.where(source.c[name] == value)
    with _inspect(database) as (connection, _):
        rows = connection.execute(statement.order_by(source.c.id).limit(limit).offset(offset))
        return {
            "table": table,
            "records": [dict(row) for row in rows.mappings()],
            "limit": limit,
            "offset": offset,
        }


def record(database, table, id):
    source = RECORD_TABLES[table]
    with _inspect(database) as (connection, _):
        row = connection.execute(select(source).where(source.c.id == id)).mappings().one_or_none()
        if row is None:
            raise ValueError(f"{table} record {id} was not found.")
        return dict(row)


def export(database, table, id, output):
    from fpg_lab.core.serialization import to_jsonable

    document = record(database, table, id)
    # Exclusive creation keeps a mistaken output path from replacing the database or an existing export.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(to_jsonable(document), stream, indent=2, allow_nan=False)
        stream.write("\n")
    return {"table": table, "id": id, "output": str(output.resolve())}


def profiles(database, operation, *, id=None, name=None, limit=25, offset=0):
    if operation == "list":
        return records(database, SystemConfiguration.__tablename__, limit=limit, offset=offset)
    if operation == "show":
        return {"profile": record(database, SystemConfiguration.__tablename__, id)}
    if operation == "validate":
        errors = []
        with _inspect(database) as (connection, _), Session(bind=connection) as session:
            service = SystemConfigurationService(session)
            ids = list(
                session.scalars(select(SystemConfiguration.id).order_by(SystemConfiguration.id))
            )
            for profile_id in ids:
                try:
                    service.validate(profile_id)
                except (ValueError, RuntimeError, AppError) as exc:
                    errors.append({"id": profile_id, "error": str(exc)})
        return {"checked": len(ids), "errors": errors}
    require_current_schema(database)
    with database.session_factory() as session:
        service = SystemConfigurationService(session)
        if operation == "duplicate":
            profile = service.duplicate(id, name)
        elif operation == "activate":
            profile = service.activate(id)
        else:
            raise ValueError(f"Unknown profile operation {operation!r}")
        return {
            "operation": operation,
            "profile": {key: getattr(profile, key) for key in PROFILE_METADATA},
        }


def require_current_schema(database):
    with _inspect(database) as (_, state):
        _require(state)
