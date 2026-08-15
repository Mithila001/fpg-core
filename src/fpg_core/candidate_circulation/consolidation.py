from __future__ import annotations

import math
from dataclasses import dataclass

from ..domain import CandidateMap, DestinationSelection, HallwayTrafficClass, RoomType
from .contracts import CandidateCirculationInput
from .domain import (
    HallwayConsolidationAttemptDetails,
    HallwayConsolidationDecision,
)
from .exceptions import CandidateCirculationError
from .routing import HallwayTraffic, ResolvedRoute, RoutingPassResult, run_routing_passes
from .validation import IndexedCandidatePoint, ValidatedCirculationInput, validate_circulation_input


@dataclass(frozen=True, slots=True)
class RemovedHallwaySnapshot:
    traffic: HallwayTraffic
    traffic_class: HallwayTrafficClass


@dataclass(frozen=True, slots=True)
class HallwayConsolidationResult:
    validated: ValidatedCirculationInput
    routing_passes: tuple[RoutingPassResult, ...]
    removed_keys: frozenset[str]
    removed_snapshots: dict[str, RemovedHallwaySnapshot]
    attempts: tuple[HallwayConsolidationAttemptDetails, ...]


def consolidate_hallways(
    validated: ValidatedCirculationInput,
    *,
    unused_keys: set[str],
) -> HallwayConsolidationResult | None:
    """Route-verify removal of nearby redundant hallways.

    Returns ``None`` when consolidation is disabled. Unused hallway removal remains
    the separate existing cleanup behavior in that case.
    """

    policy = validated.source.config.hallway_consolidation
    if not policy.enabled:
        return None

    base_validated = _validated_without_keys(validated, unused_keys)
    base_passes = run_routing_passes(base_validated)
    baseline_routes = base_passes[-1].routes

    current_validated = base_validated
    current_passes = base_passes
    removed_keys: set[str] = set()
    removed_snapshots: dict[str, RemovedHallwaySnapshot] = {}
    attempts: list[HallwayConsolidationAttemptDetails] = []
    rejected_keys: set[str] = set()

    while True:
        final_pass = current_passes[-1]
        hallway_points = _hallway_points(current_validated)
        candidates = []
        for point in hallway_points:
            if point.point_key in rejected_keys:
                continue
            nearby = _nearby_hallways(
                point,
                hallway_points,
                policy.minimum_separation_grid_steps,
            )
            if not nearby:
                continue
            usage = final_pass.hallway_traffic[point.point_key]
            candidates.append(
                (
                    usage.public_importance_weight + usage.private_importance_weight,
                    usage.public_route_count + usage.private_route_count,
                    point.point_key,
                    point,
                    nearby,
                )
            )

        if not candidates:
            break

        _, _, _, point, nearby = min(candidates, key=lambda item: item[:3])
        trial = _try_remove_hallway(current_validated, point.point_key)
        if trial is None:
            rejected_keys.add(point.point_key)
            attempts.append(
                HallwayConsolidationAttemptDetails(
                    point_key=point.point_key,
                    nearby_point_keys=nearby,
                    decision=HallwayConsolidationDecision.KEPT_ROUTE_UNAVAILABLE,
                    max_route_cost_increase_ratio=None,
                )
            )
            continue

        trial_validated, trial_passes = trial
        comparison = _compare_route_quality(
            baseline_routes,
            trial_passes[-1].routes,
            policy.max_route_cost_increase_ratio,
        )
        if comparison.decision is not HallwayConsolidationDecision.REMOVED:
            rejected_keys.add(point.point_key)
            attempts.append(
                HallwayConsolidationAttemptDetails(
                    point_key=point.point_key,
                    nearby_point_keys=nearby,
                    decision=comparison.decision,
                    max_route_cost_increase_ratio=comparison.max_cost_increase_ratio,
                )
            )
            continue

        previous_traffic = final_pass.hallway_traffic[point.point_key]
        removed_snapshots[point.point_key] = RemovedHallwaySnapshot(
            traffic=HallwayTraffic(
                public_route_count=previous_traffic.public_route_count,
                private_route_count=previous_traffic.private_route_count,
                public_importance_weight=previous_traffic.public_importance_weight,
                private_importance_weight=previous_traffic.private_importance_weight,
            ),
            traffic_class=final_pass.hallway_classes[point.point_key],
        )
        removed_keys.add(point.point_key)
        attempts.append(
            HallwayConsolidationAttemptDetails(
                point_key=point.point_key,
                nearby_point_keys=nearby,
                decision=HallwayConsolidationDecision.REMOVED,
                max_route_cost_increase_ratio=comparison.max_cost_increase_ratio,
            )
        )
        current_validated = trial_validated
        current_passes = trial_passes

    return HallwayConsolidationResult(
        validated=current_validated,
        routing_passes=current_passes,
        removed_keys=frozenset(removed_keys),
        removed_snapshots=removed_snapshots,
        attempts=tuple(attempts),
    )


def _validated_without_keys(
    validated: ValidatedCirculationInput,
    removed_keys: set[str],
) -> ValidatedCirculationInput:
    candidate = CandidateMap(
        grid=validated.source.candidate.grid,
        points=tuple(
            indexed.point
            for indexed in validated.indexed_points
            if indexed.point_key not in removed_keys
        ),
    )
    return validate_circulation_input(
        CandidateCirculationInput(candidate=candidate, config=validated.source.config)
    )


def _try_remove_hallway(
    validated: ValidatedCirculationInput,
    point_key: str,
) -> tuple[ValidatedCirculationInput, tuple[RoutingPassResult, ...]] | None:
    try:
        trial_validated = _validated_without_keys(validated, {point_key})
        return trial_validated, run_routing_passes(trial_validated)
    except (CandidateCirculationError, TypeError, ValueError):
        return None


def _hallway_points(
    validated: ValidatedCirculationInput,
) -> tuple[IndexedCandidatePoint, ...]:
    return tuple(
        point
        for point in validated.indexed_points
        if point.point.room_type is RoomType.HALLWAY
    )


def _nearby_hallways(
    point: IndexedCandidatePoint,
    hallway_points: tuple[IndexedCandidatePoint, ...],
    minimum_separation_grid_steps: float,
) -> tuple[str, ...]:
    nearby = []
    for other in hallway_points:
        if other.point_key == point.point_key:
            continue
        dx = point.x_index - other.x_index
        dy = point.y_index - other.y_index
        distance = math.hypot(dx, dy)
        if distance + 1e-12 < minimum_separation_grid_steps:
            nearby.append(other.point_key)
    return tuple(sorted(nearby))


@dataclass(frozen=True, slots=True)
class _RouteQualityComparison:
    decision: HallwayConsolidationDecision
    max_cost_increase_ratio: float | None


def _compare_route_quality(
    baseline_routes: tuple[ResolvedRoute, ...],
    trial_routes: tuple[ResolvedRoute, ...],
    allowed_cost_increase_ratio: float,
) -> _RouteQualityComparison:
    baseline_costs = {_route_coverage_key(route): route.total_cost for route in baseline_routes}
    trial_costs = {_route_coverage_key(route): route.total_cost for route in trial_routes}

    if baseline_costs.keys() != trial_costs.keys():
        return _RouteQualityComparison(
            decision=HallwayConsolidationDecision.KEPT_ROUTE_COVERAGE_CHANGED,
            max_cost_increase_ratio=None,
        )

    max_increase = 0.0
    for key, baseline_cost in baseline_costs.items():
        trial_cost = trial_costs[key]
        increase = max(0.0, (trial_cost - baseline_cost) / baseline_cost)
        max_increase = max(max_increase, increase)

    decision = (
        HallwayConsolidationDecision.REMOVED
        if max_increase <= allowed_cost_increase_ratio + 1e-12
        else HallwayConsolidationDecision.KEPT_ROUTE_COST_INCREASE
    )
    return _RouteQualityComparison(
        decision=decision,
        max_cost_increase_ratio=max_increase,
    )


def _route_coverage_key(route: ResolvedRoute) -> tuple[int, str, str | None]:
    destination_key = (
        route.destination.point_key
        if route.rule.destination_selection is DestinationSelection.ALL_MATCHING
        else None
    )
    return route.rule.id, route.source.point_key, destination_key
