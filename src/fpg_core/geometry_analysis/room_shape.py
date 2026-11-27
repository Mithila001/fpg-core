from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient

from .recesses import lines


@dataclass(frozen=True)
class RoomShapeMeasurements:
    width: float
    height: float
    edge_lengths: tuple[float, ...]
    horizontal_widths: tuple[float, ...]
    vertical_widths: tuple[float, ...]
    concave_corners: int


def measure_room_shape(polygon: Polygon) -> RoomShapeMeasurements:
    """Measure edges and exact vertex-interval cross-sections of a room."""
    polygon = orient(polygon, sign=1.0)
    coords = list(polygon.exterior.coords)[:-1]
    left, bottom, right, top = polygon.bounds
    edge_lengths = tuple(
        LineString((a, b)).length
        for a, b in zip(coords, coords[1:] + coords[:1], strict=True)
    )
    corners = sum(
        (coords[i][0] - coords[i - 1][0])
        * (coords[(i + 1) % len(coords)][1] - coords[i][1])
        - (coords[i][1] - coords[i - 1][1])
        * (coords[(i + 1) % len(coords)][0] - coords[i][0])
        < 0
        for i in range(len(coords))
    )
    xs = sorted({x for x, _ in coords})
    ys = sorted({y for _, y in coords})
    horizontal = tuple(
        line.length
        for low, high in zip(ys, ys[1:], strict=False)
        for line in lines(
            polygon.intersection(
                LineString(((left, (low + high) / 2), (right, (low + high) / 2)))
            )
        )
    )
    vertical = tuple(
        line.length
        for low, high in zip(xs, xs[1:], strict=False)
        for line in lines(
            polygon.intersection(
                LineString((((low + high) / 2, bottom), ((low + high) / 2, top)))
            )
        )
    )
    return RoomShapeMeasurements(
        right - left, top - bottom, edge_lengths, horizontal, vertical, corners
    )
