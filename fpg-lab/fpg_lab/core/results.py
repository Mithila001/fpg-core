from typing import Any

from fpg_lab.core.serialization import to_jsonable


def error_payload(
    exc: BaseException, *, stage: str, rejected: bool = False, code: str | None = None
) -> dict[str, Any]:
    cause = exc.__cause__ if exc.__cause__ is not None else exc
    raw_code = code or getattr(cause, "code", None)
    raw_details = getattr(cause, "details", None)
    try:
        details = to_jsonable(raw_details)
    except (TypeError, ValueError) as serialization_error:
        details = {"serialization_error": str(serialization_error)}
    source = (
        "fpg_core"
        if type(cause).__module__.startswith("fpg_core")
        or type(exc).__module__.startswith("fpg_lab.integrations.fpg_core")
        else "lab"
    )
    payload = {
        "stage": stage,
        "source": source,
        "type": type(exc).__name__,
        "message": str(exc),
        "code": getattr(raw_code, "value", raw_code),
        "details": details,
        "cause_type": type(cause).__name__
        if cause is not exc
        else getattr(exc, "cause_type", None),
        "rejected": rejected,
    }
    return payload


def result_document(value: Any) -> dict[str, Any]:
    document = to_jsonable(value)
    if not isinstance(document, dict):
        raise TypeError("A stage result must serialize to a JSON object")
    return document
