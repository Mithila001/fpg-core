from __future__ import annotations

from dataclasses import dataclass

from ..domain import CandidatePoint, RoomType
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

    grid = circulation_input.candidate.grid
    if grid.node_count > _MAX_GRID_NODE_COUNT:
        raise CandidateCirculationInputError(
            "Candidate grid exceeds the 250,000-node circulation safety limit."
        )

    indexed_points: list[IndexedCandidatePoint] = []
    occupied_nodes: dict[tuple[int, int], IndexedCandidatePoint] = {}
    point_keys: set[str] = set()

    for point in circulation_input.candidate.points:
        if point.room_type is None:
            raise CandidateCirculationInputError(
                f"Candidate point '{point.room_id}' has no room_type."
            )
        try:
            x_index, y_index = grid.node_indexes(point.x, point.y)
        except (TypeError, ValueError) as exc:
            raise GridAlignmentError(
                f"Candidate point '{point.point_key}' is not aligned with the "
                "candidate grid."
            ) from exc

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

    _validate_route_matches(circulation_input.config, tuple(indexed_points))
    return ValidatedCirculationInput(
        source=circulation_input,
        x_node_count=grid.x_node_count,
        y_node_count=grid.y_node_count,
        indexed_points=tuple(indexed_points),
        occupied_nodes=occupied_nodes,
    )


def candidate_point_key(point: CandidatePoint) -> str:
    return point.point_key


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
        if rule.required_transit_room_types and not any(
            required_type in present_types
            for required_type in rule.required_transit_room_types
        ):
            required_names = ", ".join(
                room_type.value for room_type in rule.required_transit_room_types
            )
            raise CandidateCirculationInputError(
                f"Route rule {rule.id} ('{rule.name}') requires transit through at "
                f"least one of [{required_names}], but no matching candidate point "
                "exists."
            )

    hallway_points = [
        point for point in points if point.point.room_type is RoomType.HALLWAY
    ]
    hallway_keys = [point.point_key for point in hallway_points]
    if len(hallway_keys) != len(set(hallway_keys)):
        raise CandidateCirculationInputError(
            "Hallway hint point identities must be unique."
        )
