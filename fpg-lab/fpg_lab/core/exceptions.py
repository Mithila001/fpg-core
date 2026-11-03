from __future__ import annotations

from typing import Any


class AppError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, *, details: Any | None = None) -> None:
        super().__init__(code, message, details=details)


class InvalidInputError(AppError):
    def __init__(self, code: str, message: str, *, details: Any | None = None) -> None:
        super().__init__(code, message, details=details)
