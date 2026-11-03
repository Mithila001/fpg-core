from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONDocument = JSON().with_variant(JSONB(), "postgresql")
