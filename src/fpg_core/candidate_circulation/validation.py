from __future__ import annotations

import math
from dataclasses import dataclass

from ..candidate_search.api import CandidatePoint
from ..domain import RoomType
from .config import CandidateCirculationConfig
from .contracts import CandidateCirculationInput
from .exceptions import CandidateCirculationInputError, GridAlignmentError

_MAX_GRID_NODE_COUNT = 250_000


@dataclass(frozen=True, slots=True)
class IndexedCandidatePoint:
    point: CandidatePoint
    point_key: str
    x_index: int
    y_index: int


@dataclass(frozen=True, slots=True)
class ValidatedCirculationInput:
    source: CandidateCirculationInput
    x_node_count: int
    y_node_count: int
    indexed_points: tuple[IndexedCandidatePoint, ...]
    occupied_nodes: dict[tuple[int, int], IndexedCandidatePoint]

    @property
    def grid_node_count(self) -> int:
        return self.x_node_count * self.y_node_count


def validate_circulation_input(
    circulation_input: CandidateCirculationInput,
) -> ValidatedCirculationInput:
    if not isinstance(circulation_input, CandidateCirculationInput):
        raise TypeError(
            "circulation_input must be a CandidateCirculationInput instance."
        )

    config = circulation_input.config
    x_node_count = _axis_node_count(config.grid.width, config.grid.scale, "width")
    y_node_count = _axis_node_count(config.grid.length, config.grid.scale, "length")
    grid_node_count = x_node_count * y_node_count
    if grid_node_count > _MAX_GRID_NODE_COUNT:
        raise CandidateCirculationInputError(
            "Configured circulation grid exceeds the 250,000-node safety limit."
        )

    indexed_points: list[IndexedCandidatePoint] = []
    occupied_nodes: dict[tuple[int, int], IndexedCandidatePoint] = {}
    point_keys: set[str] = set()

    for point in circulation_input.points:
        if point.room_type is None:
            raise CandidateCirculationInputError(
                f"Candidate point '{point.room_id}' has no room_type."
            )

        x_index = _coordinate_index(
            coordinate=point.x,
            origin=config.grid.origin_x,
            scale=config.grid.scale,
            node_count=x_node_count,
            axis_name="x",
            point=point,
        )
        y_index = _coordinate_index(
            coordinate=point.y,
            origin=config.grid.origin_y,
            scale=config.grid.scale,
            node_count=y_node_count,
            axis_name="y",
            point=point,
        )
        point_key = candidate_point_key(point)
        if point_key in point_keys:
            raise CandidateCirculationInputError(
                f"Duplicate candidate point identity '{point_key}'."
            )
        point_keys.add(point_key)

        indexed = IndexedCandidatePoint(
            point=point,
            point_key=point_key,
            x_index=x_index,
            y_index=y_index,
        )
        node = (x_index, y_index)
        existing = occupied_nodes.get(node)
        if existing is not None:
            raise CandidateCirculationInputError(
                "Candidate hint points cannot overlap on the circulation grid: "
                f"'{existing.point_key}' and '{point_key}'."
            )
        occupied_nodes[node] = indexed
        indexed_points.append(indexed)

    _validate_route_matches(config, tuple(indexed_points))
    return ValidatedCirculationInput(
        source=circulation_input,
        x_node_count=x_node_count,
        y_node_count=y_node_count,
        indexed_points=tuple(indexed_points),
        occupied_nodes=occupied_nodes,
    )


def candidate_point_key(point: CandidatePoint) -> str:
    return f"{point.room_id}[{point.hint_index}]"


def _axis_node_count(extent: float, scale: float, axis_name: str) -> int:
    raw_steps = extent / scale
    steps = round(raw_steps)
    tolerance = max(1e-9, abs(raw_steps) * 1e-9)
    if not math.isclose(raw_steps, steps, rel_tol=0.0, abs_tol=tolerance):
        raise GridAlignmentError(
            f"Grid {axis_name} extent must be an exact multiple of grid scale."
        )
    return int(steps) + 1


def _coordinate_index(
    *,
    coordinate: float,
    origin: float,
    scale: float,
    node_count: int,
    axis_name: str,
    point: CandidatePoint,
) -> int:
    raw_index = (coordinate - origin) / scale
    index = round(raw_index)
    tolerance = max(1e-8, abs(raw_index) * 1e-9)
    if not math.isclose(raw_index, index, rel_tol=0.0, abs_tol=tolerance):
        raise GridAlignmentError(
            f"Candidate point '{candidate_point_key(point)}' {axis_name} coordinate "
            "does not align with the configured grid."
        )
    if index < 0 or index >= node_count:
        raise GridAlignmentError(
            f"Candidate point '{candidate_point_key(point)}' is outside the "
            f"configured grid on the {axis_name} axis."
        )
    return int(index)


def _validate_route_matches(
    config: CandidateCirculationConfig,
    points: tuple[IndexedCandidatePoint, ...],
) -> None:
    present_types = {
        point.point.room_type
        for point in points
        if point.point.room_type is not None
    }
    for rule in config.route_rules:
        if rule.source_room_type not in present_types:
            raise CandidateCirculationInputError(
                f"Route rule {rule.id} ('{rule.name}') has no matching source "
                f"point of type {rule.source_room_type.value}."
            )
        if rule.destination_room_type not in present_types:
            raise CandidateCirculationInputError(
                f"Route rule {rule.id} ('{rule.name}') has no matching destination "
                f"point of type {rule.destination_room_type.value}."
            )

    hallway_points = [
        point for point in points if point.point.room_type is RoomType.HALLWAY
    ]
    hallway_keys = [point.point_key for point in hallway_points]
    if len(hallway_keys) != len(set(hallway_keys)):
        raise CandidateCirculationInputError(
            "Hallway hint point identities must be unique."
        )
