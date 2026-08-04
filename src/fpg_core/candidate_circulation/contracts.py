from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    CandidateMap,
    CandidatePoint,
    HallwayClassification,
    ResolvedCandidateGrid,
)
from .config import CandidateCirculationConfig
from .domain import HallwayTrafficDetails, RemovedHallwayPointDetails, RoutingPassDetails


@dataclass(frozen=True, slots=True)
class CandidateCirculationInput:
    """Candidate map and reusable circulation policy."""

    candidate: CandidateMap
    config: CandidateCirculationConfig

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")
        if not isinstance(self.config, CandidateCirculationConfig):
            raise TypeError("config must be a CandidateCirculationConfig instance.")

    @property
    def points(self) -> tuple[CandidatePoint, ...]:
        return self.candidate.points

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self.candidate.grid


@dataclass(frozen=True, slots=True)
class CandidateCirculationResult:
    """Production result with cleaned candidate and hallway traffic tags."""

    candidate: CandidateMap
    hallway_classifications: tuple[HallwayClassification, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CandidateMap):
            raise TypeError("candidate must be a CandidateMap instance.")

        classifications = tuple(self.hallway_classifications)
        if any(
            not isinstance(item, HallwayClassification)
            for item in classifications
        ):
            raise TypeError(
                "Every hallway classification must be a HallwayClassification."
            )
        identities = [(item.room_id, item.hint_index) for item in classifications]
        if len(identities) != len(set(identities)):
            raise ValueError("Hallway classifications must have unique identities.")
        object.__setattr__(self, "hallway_classifications", classifications)

    @property
    def points(self) -> tuple[CandidatePoint, ...]:
        return self.candidate.points

    @property
    def grid(self) -> ResolvedCandidateGrid:
        return self.candidate.grid


@dataclass(frozen=True, slots=True)
class CandidateCirculationDetails:
    """DEBUG-only route efficiency, hallway traffic, and removal data."""

    circulation_efficiency_score: float
    routing_pass_count: int
    grid_node_count: int
    passes: tuple[RoutingPassDetails, ...]
    final_hallway_traffic: tuple[HallwayTrafficDetails, ...]
    removed_hallway_points: tuple[RemovedHallwayPointDetails, ...]
