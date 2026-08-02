from __future__ import annotations

from dataclasses import dataclass

from ..domain import CandidatePoint, HallwayClassification
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
    """Production result with cleaned points and hallway traffic tags."""

    points: tuple[CandidatePoint, ...]
    hallway_classifications: tuple[HallwayClassification, ...] = ()

    def __post_init__(self) -> None:
        points = tuple(self.points)
        if not points:
            raise ValueError("Candidate circulation result cannot be empty.")
        if any(not isinstance(point, CandidatePoint) for point in points):
            raise TypeError("Every result point must be a CandidatePoint.")

        classifications = tuple(self.hallway_classifications)
        if any(
            not isinstance(item, HallwayClassification)
            for item in classifications
        ):
            raise TypeError(
                "Every hallway classification must be a HallwayClassification."
            )
        identities = [
            (item.room_id, item.hint_index) for item in classifications
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Hallway classifications must have unique identities.")

        object.__setattr__(self, "points", points)
        object.__setattr__(self, "hallway_classifications", classifications)


@dataclass(frozen=True, slots=True)
class CandidateCirculationDetails:
    """DEBUG-only route efficiency, hallway traffic, and removal data."""

    circulation_efficiency_score: float
    routing_pass_count: int
    grid_node_count: int
    passes: tuple[RoutingPassDetails, ...]
    final_hallway_traffic: tuple[HallwayTrafficDetails, ...]
    removed_hallway_points: tuple[RemovedHallwayPointDetails, ...]
