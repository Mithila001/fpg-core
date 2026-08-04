from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, cast

from .candidate import CandidatePoint


def _integer_coordinate(field_name: str, value: object) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer project-unit coordinate.")
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"{field_name} must be an integer project-unit coordinate."
        ) from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite.")
    if not numeric.is_integer():
        raise ValueError(
            f"{field_name} must use whole project units; received {numeric}."
        )
    return int(numeric)


def _validated_positions(
    axis_name: str,
    values: tuple[int, ...],
) -> tuple[int, ...]:
    positions = tuple(
        _integer_coordinate(f"{axis_name}_positions[{index}]", value)
        for index, value in enumerate(values)
    )
    if len(positions) < 2:
        raise ValueError(f"{axis_name}_positions must contain at least two nodes.")
    if any(current <= previous for previous, current in zip(positions, positions[1:])):
        raise ValueError(f"{axis_name}_positions must be strictly increasing.")
    return positions


@dataclass(frozen=True, slots=True)
class ResolvedCandidateGrid:
    """Exact candidate-location and orthogonal-routing grid.

    Coordinates are expressed in whole project units. Axis gaps may differ by one
    unit so the grid can cover the exact floor boundary without shrinking it.
    """

    x_positions: tuple[int, ...]
    y_positions: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x_positions",
            _validated_positions("x", tuple(self.x_positions)),
        )
        object.__setattr__(
            self,
            "y_positions",
            _validated_positions("y", tuple(self.y_positions)),
        )

    @property
    def origin_x(self) -> int:
        return self.x_positions[0]

    @property
    def origin_y(self) -> int:
        return self.y_positions[0]

    @property
    def max_x(self) -> int:
        return self.x_positions[-1]

    @property
    def max_y(self) -> int:
        return self.y_positions[-1]

    @property
    def width(self) -> int:
        return self.max_x - self.origin_x

    @property
    def length(self) -> int:
        return self.max_y - self.origin_y

    @property
    def x_node_count(self) -> int:
        return len(self.x_positions)

    @property
    def y_node_count(self) -> int:
        return len(self.y_positions)

    @property
    def node_count(self) -> int:
        return self.x_node_count * self.y_node_count

    @property
    def minimum_x_gap(self) -> int:
        return min(
            current - previous
            for previous, current in zip(self.x_positions, self.x_positions[1:])
        )

    @property
    def maximum_x_gap(self) -> int:
        return max(
            current - previous
            for previous, current in zip(self.x_positions, self.x_positions[1:])
        )

    @property
    def minimum_y_gap(self) -> int:
        return min(
            current - previous
            for previous, current in zip(self.y_positions, self.y_positions[1:])
        )

    @property
    def maximum_y_gap(self) -> int:
        return max(
            current - previous
            for previous, current in zip(self.y_positions, self.y_positions[1:])
        )

    def x_index(self, coordinate: object) -> int:
        return self._coordinate_index("x", coordinate, self.x_positions)

    def y_index(self, coordinate: object) -> int:
        return self._coordinate_index("y", coordinate, self.y_positions)

    def node_indexes(self, x: object, y: object) -> tuple[int, int]:
        return self.x_index(x), self.y_index(y)

    def coordinates(self, x_index: int, y_index: int) -> tuple[int, int]:
        if isinstance(x_index, bool) or not isinstance(x_index, int):
            raise TypeError("x_index must be an integer.")
        if isinstance(y_index, bool) or not isinstance(y_index, int):
            raise TypeError("y_index must be an integer.")
        if not 0 <= x_index < self.x_node_count:
            raise IndexError("x_index is outside the candidate grid.")
        if not 0 <= y_index < self.y_node_count:
            raise IndexError("y_index is outside the candidate grid.")
        return self.x_positions[x_index], self.y_positions[y_index]

    @staticmethod
    def _coordinate_index(
        axis_name: str,
        coordinate: object,
        positions: tuple[int, ...],
    ) -> int:
        value = _integer_coordinate(f"{axis_name} coordinate", coordinate)
        index = bisect.bisect_left(positions, value)
        if index >= len(positions) or positions[index] != value:
            raise ValueError(
                f"{axis_name} coordinate {value} is not a node on the resolved candidate grid."
            )
        return index


@dataclass(frozen=True, slots=True)
class CandidateMap:
    """A candidate hint map coupled to the exact grid that produced it."""

    grid: ResolvedCandidateGrid
    points: tuple[CandidatePoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.grid, ResolvedCandidateGrid):
            raise TypeError("grid must be a ResolvedCandidateGrid instance.")

        points = tuple(self.points)
        if not points:
            raise ValueError("CandidateMap must contain at least one point.")
        if any(not isinstance(point, CandidatePoint) for point in points):
            raise TypeError("Every CandidateMap point must be a CandidatePoint.")

        occupied: dict[tuple[int, int], CandidatePoint] = {}
        identities: set[str] = set()
        for point in points:
            if point.point_key in identities:
                raise ValueError(
                    f"CandidateMap contains duplicate point identity '{point.point_key}'."
                )
            identities.add(point.point_key)
            try:
                node = self.grid.node_indexes(point.x, point.y)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Candidate point '{point.point_key}' is not aligned with the resolved grid."
                ) from exc
            previous = occupied.get(node)
            if previous is not None:
                raise ValueError(
                    "CandidateMap points cannot overlap: "
                    f"'{previous.point_key}' and '{point.point_key}'."
                )
            occupied[node] = point

        object.__setattr__(self, "points", points)
