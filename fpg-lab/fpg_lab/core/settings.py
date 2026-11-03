from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    auto_create_schema: bool
    max_background_workers: int
    host: str
    port: int


def positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    url = make_url(os.getenv("FPG_LAB_DATABASE_URL", "sqlite:///./data/fpg_lab.db"))
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        path = Path(url.database).expanduser()
        if not path.is_absolute():
            url = url.set(database=str((ROOT / path).resolve()))
    port = positive_int("FPG_LAB_PORT", 8080)
    if port > 65535:
        raise ValueError("FPG_LAB_PORT must be at most 65535")
    return Settings(
        database_url=url.render_as_string(hide_password=False),
        auto_create_schema=os.getenv("FPG_LAB_AUTO_CREATE_SCHEMA", "true").lower()
        in {"1", "true", "yes", "on"},
        max_background_workers=positive_int("FPG_LAB_MAX_BACKGROUND_WORKERS", 1),
        host=os.getenv("FPG_LAB_HOST", "127.0.0.1"),
        port=port,
    )
