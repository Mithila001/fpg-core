from __future__ import annotations

from ..domain import BuildableSpaceErrorCode


class BuildableLandError(Exception):
    def __init__(self, code: BuildableSpaceErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
