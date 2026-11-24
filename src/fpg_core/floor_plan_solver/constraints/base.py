from __future__ import annotations

from collections.abc import Iterable, Mapping
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


def nonnegative_multiplier(settings: ConstraintSettings, name: str, label: str) -> int:
    value = settings.get(name, 1)
    if type(value) is not int or value < 0:
        raise InvalidProfileError(f"{label}.{name} must be a non-negative integer")
    return value


def require_room_type_keys(values: Mapping[object, Any], label: str) -> None:
    for value in values:
        if not isinstance(value, RoomType):
            raise InvalidProfileError(f"{label} keys must be RoomType enum members")


PENALTY_MAX = 10_000
OBJECTIVE_SCALE = 1_000


def ceil_ratio(
    context: ModelContext, numerator: Any, denominator: Any, maximum: int,
    *, denominator_max: int | None = None,
) -> Any:
    result = context.model.NewIntVar(0, maximum, context.new_name("penalty"))
    upper = denominator if denominator_max is None else denominator_max
    dividend = context.model.NewIntVar(
        0, (maximum + 1) * upper - 1, context.new_name("penalty_dividend")
    )
    context.model.Add(dividend == numerator + denominator - 1)
    context.model.AddDivisionEquality(result, dividend, denominator)
    return result


def average_penalties(context: ModelContext, terms: list[tuple[Any, int]]) -> Any:
    if not terms:
        return 0
    if len(terms) == 1:
        return terms[0][0]
    return ceil_ratio(context, sum(value * weight for value, weight in terms),
                      sum(weight for _, weight in terms), PENALTY_MAX)


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

    def build_penalty(
        self,
        context: ModelContext,
        settings: ConstraintSettings,
    ) -> Any:
        ...
