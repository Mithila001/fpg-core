from __future__ import annotations

from dataclasses import dataclass

from ..candidate_search.api import CandidatePoint
from .config import CandidateCirculationConfig
from .domain import (
    HallwayTrafficDetails,
    RemovedHallwayPointDetails,
    RoutingPassDetails,
)


@dataclass(frozen=True, slots=True)
class CandidateCirculationInput:
    """Candidate hint points and required circulation configuration."""

    points: tuple[CandidatePoint, ...]
    config: CandidateCirculationConfig

    def __post_init__(self) -> None:
        points = tuple(self.points)
        if not points:
            raise ValueError("Candidate circulation requires at least one hint point.")
        if any(not isinstance(point, CandidatePoint) for point in points):
            raise TypeError("Every circulation point must be a CandidatePoint.")
        if not isinstance(self.config, CandidateCirculationConfig):
            raise TypeError("config must be a CandidateCirculationConfig instance.")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class CandidateCirculationResult:
    """Normal feature result containing the hallway-cleaned candidate points."""

    points: tuple[CandidatePoint, ...]

    def __post_init__(self) -> None:
        points = tuple(self.points)
        if not points:
            raise ValueError("Candidate circulation result cannot be empty.")
        if any(not isinstance(point, CandidatePoint) for point in points):
            raise TypeError("Every result point must be a CandidatePoint.")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class CandidateCirculationDetails:
    """DEBUG-only route, scoring, hallway-traffic, and removal data."""

    diagnostic_score: float
    routing_pass_count: int
    grid_node_count: int
    passes: tuple[RoutingPassDetails, ...]
    final_hallway_traffic: tuple[HallwayTrafficDetails, ...]
    removed_hallway_points: tuple[RemovedHallwayPointDetails, ...]
