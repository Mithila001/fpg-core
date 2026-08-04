from __future__ import annotations

import math
from typing import Any, cast

from ..domain import FloorSpec, ResolvedCandidateGrid


def build_candidate_grid(
    floor: FloorSpec,
    *,
    long_axis_node_count: int,
    max_grid_node_count: int,
) -> ResolvedCandidateGrid:
    """Build an integer adaptive grid covering the exact floor boundary."""

    if not isinstance(floor, FloorSpec):
        raise TypeError("floor must be a FloorSpec instance.")
    if isinstance(long_axis_node_count, bool) or not isinstance(
        long_axis_node_count, int
    ):
        raise TypeError("long_axis_node_count must be an integer.")
    if long_axis_node_count < 2:
        raise ValueError("long_axis_node_count must be at least 2.")
    if isinstance(max_grid_node_count, bool) or not isinstance(
        max_grid_node_count, int
    ):
        raise TypeError("max_grid_node_count must be an integer.")
    if max_grid_node_count < 4:
        raise ValueError("max_grid_node_count must be at least 4.")

    width = _whole_extent("floor.width", floor.width)
    length = _whole_extent("floor.length", floor.length)
    long_extent = max(width, length)
    if long_axis_node_count > long_extent + 1:
        raise ValueError(
            "long_axis_node_count exceeds the number of unique whole-unit "
            "positions available on the longest floor axis."
        )

    long_intervals = long_axis_node_count - 1
    target_spacing = long_extent / long_intervals

    if width >= length:
        x_intervals = long_intervals
        y_intervals = _short_axis_interval_count(length, target_spacing)
    else:
        x_intervals = _short_axis_interval_count(width, target_spacing)
        y_intervals = long_intervals

    x_positions = _balanced_axis_positions(width, x_intervals)
    y_positions = _balanced_axis_positions(length, y_intervals)
    grid = ResolvedCandidateGrid(
        x_positions=x_positions,
        y_positions=y_positions,
    )
    if grid.node_count > max_grid_node_count:
        raise ValueError(
            "Resolved candidate grid contains "
            f"{grid.node_count} nodes, exceeding max_grid_node_count="
            f"{max_grid_node_count}."
        )
    return grid


def _whole_extent(field_name: str, value: object) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not boolean.")
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{field_name} must be positive and finite.")
    if not numeric.is_integer():
        raise ValueError(
            f"{field_name} must use whole project units before candidate search; "
            f"received {numeric}."
        )
    return int(numeric)


def _short_axis_interval_count(extent: int, target_spacing: float) -> int:
    interval_count = max(1, round(extent / target_spacing))
    return min(extent, interval_count)


def _balanced_axis_positions(extent: int, interval_count: int) -> tuple[int, ...]:
    if interval_count <= 0:
        raise ValueError("interval_count must be positive.")
    if interval_count > extent:
        raise ValueError(
            "Cannot create strictly increasing whole-unit grid positions when "
            "interval_count exceeds the axis extent."
        )
    return tuple((index * extent) // interval_count for index in range(interval_count + 1))
