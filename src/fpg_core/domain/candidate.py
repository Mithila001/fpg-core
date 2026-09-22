from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from .floor_plan_spec import RoomId, RoomType


@dataclass(frozen=True, slots=True)
class HallwayRoomCountRange:
    """Allowed number of distinct hallway rooms in one candidate trial.

    Candidate generation always requires at least one hallway room. ``maximum``
    is prepared by Floor Plan Preprocessing and consumed by Candidate Search.
    """

    maximum: int
    minimum: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.minimum, bool) or not isinstance(self.minimum, int):
            raise TypeError("minimum must be an integer.")
        if isinstance(self.maximum, bool) or not isinstance(self.maximum, int):
            raise TypeError("maximum must be an integer.")
        if self.minimum != 1:
            raise ValueError("Hallway room-count minimum must always be 1.")
        if self.maximum < self.minimum:
            raise ValueError("maximum must be at least 1.")


@dataclass(frozen=True, slots=True)
class CandidatePoint:
    """A reusable room hint coordinate passed between generation features."""

    room_id: RoomId
    x: float
    y: float
    room_type: RoomType | None = None
    hint_index: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.room_id, str):
            raise TypeError("Candidate point room_id must be a string-based RoomId.")

        cleaned_room_id = self.room_id.strip()
        if not cleaned_room_id:
            raise ValueError("Candidate point room_id cannot be empty.")

        if self.room_type is not None and not isinstance(self.room_type, RoomType):
            raise TypeError("Candidate point room_type must be a RoomType or None.")

        if isinstance(self.hint_index, bool) or not isinstance(self.hint_index, int):
            raise TypeError("Candidate point hint_index must be an integer.")
        if self.hint_index <= 0:
            raise ValueError("Candidate point hint_index must be greater than zero.")
        if self.room_type is not RoomType.HALLWAY and self.hint_index != 1:
            raise ValueError(
                "Only hallway candidate points may use a hint_index greater than one."
            )

        object.__setattr__(self, "room_id", RoomId(cleaned_room_id))
        object.__setattr__(self, "x", _finite_number("x", self.x))
        object.__setattr__(self, "y", _finite_number("y", self.y))

    @property
    def point_key(self) -> str:
        """Stable point identity.

        Current Candidate Search creates one point per room, so generated points
        use ``hint_index=1``. The index remains in the shared contract for
        compatibility with existing downstream feature data.
        """

        return f"{self.room_id}[{self.hint_index}]"


def _finite_number(field_name: str, value: object) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not boolean.")
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number
