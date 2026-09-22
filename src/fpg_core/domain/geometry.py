from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Segment:
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class Polygon:
    points: tuple[Point, ...]
