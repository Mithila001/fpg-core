from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

from .candidate import CandidatePoint

Coordinate: TypeAlias = int | float


def _coordinate(field_name: str, value: object) -> Coordinate:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a numeric project-unit coordinate.")
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"{field_name} must be a numeric project-unit coordinate."
        ) from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite.")
    return int(numeric) if numeric.is_integer() else numeric


def _positive_integer(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value


@dataclass(frozen=True, slots=True)
class CandidateSearchSpace:
    """Centered, divisible Candidate Search rectangle in floor coordinates.

    ``width`` and ``length`` are exact multiples of ``grid_spacing``. Origins may
    use half project units when an odd-sized floor is trimmed equally from both
    sides, for example ``origin_x=0.5``.
    """

    origin_x: Coordinate
    origin_y: Coordinate
    width: int
    length: int
    grid_spacing: int

    def __post_init__(self) -> None:
        origin_x = _coordinate("origin_x", self.origin_x)
        origin_y = _coordinate("origin_y", self.origin_y)
        width = _positive_integer("width", self.width)
        length = _positive_integer("length", self.length)
        spacing = _positive_integer("grid_spacing", self.grid_spacing)

        if spacing % 2 != 0:
            raise ValueError("grid_spacing must be an even project-unit value.")
        if spacing > min(width, length) // 2:
            raise ValueError(
                "grid_spacing cannot exceed half of the search space's smallest "
                "side rounded down."
            )
        if width % spacing != 0:
            raise ValueError("width must be exactly divisible by grid_spacing.")
        if length % spacing != 0:
            raise ValueError("length must be exactly divisible by grid_spacing.")

        object.__setattr__(self, "origin_x", origin_x)
        object.__setattr__(self, "origin_y", origin_y)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "length", length)
        object.__setattr__(self, "grid_spacing", spacing)

    @property
    def max_x(self) -> Coordinate:
        return _coordinate("max_x", float(self.origin_x) + self.width)

    @property
    def max_y(self) -> Coordinate:
        return _coordinate("max_y", float(self.origin_y) + self.length)

    @property
    def x_interval_count(self) -> int:
        return self.width // self.grid_spacing

    @property
    def y_interval_count(self) -> int:
        return self.length // self.grid_spacing

    @property
    def x_node_count(self) -> int:
        return self.x_interval_count + 1

    @property
    def y_node_count(self) -> int:
        return self.y_interval_count + 1

    @property
    def node_count(self) -> int:
        return self.x_node_count * self.y_node_count

    def x_positions(self) -> tuple[Coordinate, ...]:
        return tuple(
            _coordinate(
                f"x_positions[{index}]",
                float(self.origin_x) + index * self.grid_spacing,
            )
            for index in range(self.x_node_count)
        )

    def y_positions(self) -> tuple[Coordinate, ...]:
        return tuple(
            _coordinate(
                f"y_positions[{index}]",
                float(self.origin_y) + index * self.grid_spacing,
            )
            for index in range(self.y_node_count)
        )


def _validated_positions(
    axis_name: str,
    values: tuple[Coordinate, ...],
) -> tuple[Coordinate, ...]:
    positions = tuple(
        _coordinate(f"{axis_name}_positions[{index}]", value)
        for index, value in enumerate(values)
    )
    if len(positions) < 2:
        raise ValueError(f"{axis_name}_positions must contain at least two nodes.")
    if any(
        float(current) <= float(previous)
        for previous, current in zip(positions, positions[1:], strict=False)
    ):
        raise ValueError(f"{axis_name}_positions must be strictly increasing.")
    return positions


def _uniform_axis_spacing(
    axis_name: str,
    positions: tuple[Coordinate, ...],
) -> Coordinate:
    gaps = tuple(
        float(current) - float(previous)
        for previous, current in zip(positions, positions[1:], strict=False)
    )
    spacing = gaps[0]
    if any(
        not math.isclose(gap, spacing, rel_tol=0.0, abs_tol=1e-9)
        for gap in gaps[1:]
    ):
        raise ValueError(
            f"{axis_name}_positions must use one uniform grid spacing."
        )
    return _coordinate(f"{axis_name}_spacing", spacing)


@dataclass(frozen=True, slots=True)
class ResolvedCandidateGrid:
    """Exact uniform candidate-location and orthogonal-routing grid.

    Both axes use the same project-unit spacing. Coordinates may have a
    fractional origin when preprocessing centered an evenly spaced grid inside
    an odd-sized floor.
    """

    x_positions: tuple[Coordinate, ...]
    y_positions: tuple[Coordinate, ...]

    def __post_init__(self) -> None:
        x_positions = _validated_positions("x", tuple(self.x_positions))
        y_positions = _validated_positions("y", tuple(self.y_positions))
        x_spacing = _uniform_axis_spacing("x", x_positions)
        y_spacing = _uniform_axis_spacing("y", y_positions)
        if not math.isclose(
            float(x_spacing),
            float(y_spacing),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "x_positions and y_positions must use the same grid spacing."
            )

        object.__setattr__(self, "x_positions", x_positions)
        object.__setattr__(self, "y_positions", y_positions)

    @property
    def origin_x(self) -> Coordinate:
        return self.x_positions[0]

    @property
    def origin_y(self) -> Coordinate:
        return self.y_positions[0]

    @property
    def max_x(self) -> Coordinate:
        return self.x_positions[-1]

    @property
    def max_y(self) -> Coordinate:
        return self.y_positions[-1]

    @property
    def width(self) -> Coordinate:
        return _coordinate("width", float(self.max_x) - float(self.origin_x))

    @property
    def length(self) -> Coordinate:
        return _coordinate("length", float(self.max_y) - float(self.origin_y))

    @property
    def grid_spacing(self) -> Coordinate:
        return _coordinate(
            "grid_spacing",
            float(self.x_positions[1]) - float(self.x_positions[0]),
        )

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
    def interior_x_node_count(self) -> int:
        """Number of non-edge nodes on the X axis."""

        return max(0, self.x_node_count - 2)

    @property
    def interior_y_node_count(self) -> int:
        """Number of non-edge nodes on the Y axis."""

        return max(0, self.y_node_count - 2)

    @property
    def interior_node_count(self) -> int:
        """Number of grid nodes that may be used as room hint points."""

        return self.interior_x_node_count * self.interior_y_node_count

    @property
    def minimum_x_gap(self) -> Coordinate:
        return self.grid_spacing

    @property
    def maximum_x_gap(self) -> Coordinate:
        return self.grid_spacing

    @property
    def minimum_y_gap(self) -> Coordinate:
        return self.grid_spacing

    @property
    def maximum_y_gap(self) -> Coordinate:
        return self.grid_spacing

    def x_index(self, coordinate: object) -> int:
        return self._coordinate_index("x", coordinate, self.x_positions)

    def y_index(self, coordinate: object) -> int:
        return self._coordinate_index("y", coordinate, self.y_positions)

    def node_indexes(self, x: object, y: object) -> tuple[int, int]:
        return self.x_index(x), self.y_index(y)

    def coordinates(self, x_index: int, y_index: int) -> tuple[Coordinate, Coordinate]:
        self._validate_x_index(x_index)
        self._validate_y_index(y_index)
        return self.x_positions[x_index], self.y_positions[y_index]

    def flat_node_index(self, x_index: int, y_index: int) -> int:
        """Return the row-major flat index for one grid node."""

        self._validate_x_index(x_index)
        self._validate_y_index(y_index)
        return (y_index * self.x_node_count) + x_index

    def is_edge_node(self, x_index: int, y_index: int) -> bool:
        """Return whether a node lies on the outer grid boundary."""

        self._validate_x_index(x_index)
        self._validate_y_index(y_index)
        return (
            x_index == 0
            or x_index == self.x_node_count - 1
            or y_index == 0
            or y_index == self.y_node_count - 1
        )

    def interior_flat_node_indexes(self) -> tuple[int, ...]:
        """Return row-major indexes for all non-edge hint-point nodes."""

        return tuple(
            self.flat_node_index(x_index, y_index)
            for y_index in range(1, self.y_node_count - 1)
            for x_index in range(1, self.x_node_count - 1)
        )

    def indexes_from_flat_node_index(self, flat_node_index: int) -> tuple[int, int]:
        """Return ``(x_index, y_index)`` for a row-major flat node index."""

        if isinstance(flat_node_index, bool) or not isinstance(flat_node_index, int):
            raise TypeError("flat_node_index must be an integer.")
        if not 0 <= flat_node_index < self.node_count:
            raise IndexError("flat_node_index is outside the candidate grid.")
        y_index, x_index = divmod(flat_node_index, self.x_node_count)
        return x_index, y_index

    def _validate_x_index(self, x_index: object) -> None:
        if isinstance(x_index, bool) or not isinstance(x_index, int):
            raise TypeError("x_index must be an integer.")
        if not 0 <= x_index < self.x_node_count:
            raise IndexError("x_index is outside the candidate grid.")

    def _validate_y_index(self, y_index: object) -> None:
        if isinstance(y_index, bool) or not isinstance(y_index, int):
            raise TypeError("y_index must be an integer.")
        if not 0 <= y_index < self.y_node_count:
            raise IndexError("y_index is outside the candidate grid.")

    @staticmethod
    def _coordinate_index(
        axis_name: str,
        coordinate: object,
        positions: tuple[Coordinate, ...],
    ) -> int:
        value = _coordinate(f"{axis_name} coordinate", coordinate)
        numeric_positions = tuple(float(position) for position in positions)
        numeric_value = float(value)
        index = bisect.bisect_left(numeric_positions, numeric_value)
        if index >= len(positions) or not math.isclose(
            numeric_positions[index],
            numeric_value,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"{axis_name} coordinate {value} is not a node on the resolved "
                "candidate grid."
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
                    f"Candidate point '{point.point_key}' is not aligned with the "
                    "resolved grid."
                ) from exc
            if self.grid.is_edge_node(*node):
                raise ValueError(
                    f"Candidate point '{point.point_key}' cannot use an outer "
                    "grid-edge node."
                )
            previous = occupied.get(node)
            if previous is not None:
                raise ValueError(
                    "CandidateMap points cannot overlap: "
                    f"'{previous.point_key}' and '{point.point_key}'."
                )
            occupied[node] = point

        object.__setattr__(self, "points", points)
