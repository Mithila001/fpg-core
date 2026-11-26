"""Inspect and maintain the local Lab SQLite database."""

import argparse
import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from fpg_lab.core.exceptions import AppError
from fpg_lab.core.serialization import to_jsonable
from fpg_lab.core.settings import get_settings
from fpg_lab.database import maintenance
from fpg_lab.database.session import Database
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigurationError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", help="Target SQLite URL (default: configured Lab database)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def command(group, name):
        operation = group.add_parser(name)
        operation.add_argument("--json", action="store_true", help="Emit compact JSON")
        return operation

    command(commands, "status")
    command(commands, "migrate").add_argument("--dry-run", action="store_true")
    command(commands, "seed")
    profiles = command(commands, "profiles").add_subparsers(dest="operation", required=True)
    listing = command(profiles, "list")
    records = command(commands, "records")
    for listing_parser in (listing, records):
        listing_parser.add_argument("--limit", type=int, default=25)
        listing_parser.add_argument("--offset", type=int, default=0)
    for name in ("show", "duplicate", "activate"):
        action = command(profiles, name)
        action.add_argument("id", type=int)
        if name == "duplicate":
            action.add_argument("--name", required=True)
    command(profiles, "validate").add_argument("--all", action="store_true", required=True)
    records.add_argument("table", choices=maintenance.RECORD_TABLES)
    records.add_argument("--status")
    records.add_argument("--experiment-id", type=int)
    for name in ("record", "export"):
        action = command(commands, name)
        action.add_argument("table", choices=maintenance.RECORD_TABLES)
        action.add_argument("id", type=int)
        if name == "export":
            action.add_argument("--output", type=Path, required=True)
    reset = command(commands, "reset")
    reset.add_argument("--scope", choices=("runs", "all"), required=True)
    reset.add_argument("--yes", action="store_true", required=True)
    args = parser.parse_args(argv)

    database = None
    target = args.database_url or get_settings().database_url
    try:
        database = Database(target)
        target = str(maintenance.database_path(database) or ":memory:")
        result = dispatch(database, args)
        code = int(bool(result.get("conflicts") or result.get("errors")))
    except (AppError, OSError, ValueError, CoreConfigurationError, SQLAlchemyError) as exc:
        result, code = {"error": str(exc)}, 1
    finally:
        if database is not None:
            database.dispose()
    print(
        json.dumps(
            to_jsonable({"target": target, **result}),
            indent=None if args.json else 2,
            allow_nan=False,
        )
    )
    return code


def dispatch(database, args):
    match args.command:
        case "status":
            return maintenance.status(database)
        case "migrate":
            return maintenance.migrate(database, dry_run=args.dry_run)
        case "seed":
            return maintenance.seed(database)
        case "reset":
            return maintenance.reset(database, scope=args.scope)
        case "profiles":
            return maintenance.profiles(
                database,
                args.operation,
                **{
                    name: getattr(args, name)
                    for name in ("id", "name", "limit", "offset")
                    if hasattr(args, name)
                },
            )
        case "records":
            return maintenance.records(
                database,
                args.table,
                limit=args.limit,
                offset=args.offset,
                status=args.status,
                experiment_id=args.experiment_id,
            )
        case "record":
            return {"record": maintenance.record(database, args.table, args.id)}
        case "export":
            return maintenance.export(database, args.table, args.id, args.output)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
