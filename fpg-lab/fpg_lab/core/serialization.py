from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, cast
from uuid import UUID


def to_jsonable(value: Any, *, _depth: int = 0) -> Any:
    if _depth > 40:
        raise ValueError("Result exceeds maximum serialization depth (40)")
    if isinstance(value, Enum):
        return to_jsonable(value.value, _depth=_depth + 1)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite result cannot be stored as JSON")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Path, Decimal)):
        return str(value)
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json"), _depth=_depth + 1)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(
                getattr(value, field.name),
                _depth=_depth + 1,
            )
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(to_jsonable(key)): to_jsonable(item, _depth=_depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (set, frozenset, tuple, list)):
        return [to_jsonable(item, _depth=_depth + 1) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_jsonable(item, _depth=_depth + 1) for item in value]
    if hasattr(value, "__geo_interface__"):
        return to_jsonable(cast(Any, value).__geo_interface__, _depth=_depth + 1)
    if hasattr(value, "tolist"):
        try:
            return to_jsonable(cast(Any, value).tolist(), _depth=_depth + 1)
        except Exception:
            pass
    raise TypeError(f"Unsupported result type: {type(value).__module__}.{type(value).__name__}")
