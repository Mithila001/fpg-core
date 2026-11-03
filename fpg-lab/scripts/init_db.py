from __future__ import annotations

from fpg_lab.core.settings import get_settings
from fpg_lab.database.session import Database
from fpg_lab.services.common import seed_namespace_registry


def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        database.create_schema()
        with database.session_factory() as session:
            seed_namespace_registry(session)
        print(f"Database initialized: {settings.database_url}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
