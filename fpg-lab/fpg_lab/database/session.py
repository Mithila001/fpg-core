from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from fpg_lab.database.base import Base


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ensure_sqlite_parent_exists(database_url)

        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self.engine: Engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)

        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @staticmethod
    def _ensure_sqlite_parent_exists(database_url: str) -> None:
        url = make_url(database_url)
        if not url.drivername.startswith("sqlite"):
            return
        if not url.database or url.database == ":memory:":
            return
        Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def create_schema(self) -> None:
        import fpg_lab.database.models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        import fpg_lab.database.models  # noqa: F401

        Base.metadata.drop_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()
