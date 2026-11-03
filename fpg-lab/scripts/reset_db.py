from __future__ import annotations

import argparse

from fpg_lab.core.settings import get_settings
from fpg_lab.database.session import Database
from fpg_lab.services.common import seed_namespace_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop and recreate every FPG Lab table.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive database reset.",
    )
    args = parser.parse_args()
    if not args.yes:
        parser.error("Pass --yes to confirm the destructive reset")

    settings = get_settings()
    database = Database(settings.database_url)
    try:
        database.drop_schema()
        database.create_schema()
        with database.session_factory() as session:
            seed_namespace_registry(session)
        print(f"Database reset: {settings.database_url}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
