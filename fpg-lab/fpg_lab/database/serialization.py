from typing import Any

from sqlalchemy import inspect

from fpg_lab.core.serialization import to_jsonable


def row_document(row: Any) -> dict[str, Any]:
    """Materialize mapped columns while the caller still owns the session."""
    return {
        column.key: to_jsonable(getattr(row, column.key))
        for column in inspect(row).mapper.column_attrs
    }


