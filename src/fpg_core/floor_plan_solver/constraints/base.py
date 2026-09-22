from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from ...domain import RoomType
from ..exceptions import InvalidProfileError

if TYPE_CHECKING:
    from ..model import ModelContext

ConstraintSettings = Mapping[str, Any]


def require_room_types(values: Iterable[object], label: str) -> tuple[RoomType, ...]:
    try:
        raw_values = tuple(values)
    except TypeError as exc:
        raise InvalidProfileError(f"{label} must be an iterable of RoomType members") from exc
    room_types: list[RoomType] = []
    for value in raw_values:
        if not isinstance(value, RoomType):
            raise InvalidProfileError(
                f"{label} must contain only RoomType enum members"
            )
        room_types.append(value)
    return tuple(room_types)


def require_room_type_keys(values: Mapping[object, Any], label: str) -> None:
    for value in values:
        if not isinstance(value, RoomType):
            raise InvalidProfileError(f"{label} keys must be RoomType enum members")


@dataclass(frozen=True, slots=True)
class PenaltyTerm:
    name: str
    expression: Any
    multiplier: int = 1

    def __post_init__(self) -> None:
        if self.multiplier <= 0:
            raise ValueError("Penalty multiplier must be positive")


class HardConstraint(Protocol):
    key: str

    def apply(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> None:
        ...


class SoftConstraint(Protocol):
    key: str

    def build_penalties(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> tuple[PenaltyTerm, ...]:
        ...
