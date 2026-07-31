from __future__ import annotations

from ..domain import (
    EdgeClassification,
    LandSide,
    NormalizedLand,
)
from .geometry import unit_inward_normal

SIDE_ORDER = (
    LandSide.FRONT,
    LandSide.BACK,
    LandSide.LEFT,
    LandSide.RIGHT,
)


def classify_edges(land: NormalizedLand) -> tuple[EdgeClassification, ...]:
    entry = next(
        edge
        for edge in land.edges
        if edge.source_edge_index == land.main_entry_road.boundary_edge_index
    )
    into = unit_inward_normal(entry.segment)
    targets = {
        LandSide.FRONT: into,
        LandSide.BACK: (-into[0], -into[1]),
        LandSide.LEFT: (into[1], -into[0]),
        LandSide.RIGHT: (-into[1], into[0]),
    }

    result: list[EdgeClassification] = []
    for edge in land.edges:
        normal = unit_inward_normal(edge.segment)
        side = max(
            SIDE_ORDER,
            key=lambda candidate: (
                normal[0] * targets[candidate][0]
                + normal[1] * targets[candidate][1]
            ),
        )
        if edge.source_edge_index == entry.source_edge_index:
            side = LandSide.FRONT
        result.append(
            EdgeClassification(edge_index=edge.source_edge_index, side=side)
        )
    return tuple(sorted(result, key=lambda item: item.edge_index))
