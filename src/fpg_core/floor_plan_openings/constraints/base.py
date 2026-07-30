from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..model import OpeningModelContext


class OpeningConstraint(Protocol):
    constraint_id: str

    def apply(self, context: OpeningModelContext) -> None: ...
