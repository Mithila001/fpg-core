# Candidate Circulation

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Checks configured room-type routes over the exact `CandidateMap.grid`, classifies
hallway traffic, removes unused hallway hints, and can conservatively consolidate
nearby retained hallway hints. It does not generate a second grid and does not mutate
the supplied `CandidateMap`.

## Public API

```python
refine_candidate_circulation(
    circulation_input: CandidateCirculationInput,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

Preferred imports are from `fpg_core.candidate_circulation`. The feature root exports
the input/config/result contracts, routing cost and route-rule contracts, traffic
enums, hallway cleanup configuration and DEBUG contracts, compatibility aliases
`TrafficClass` and `GridNode`, and the documented exception family.

## Inputs

```python
CandidateCirculationInput(
    candidate: CandidateMap,
    config: CandidateCirculationConfig,
)
```

`candidate.grid` is the exact routing grid. Candidate points must be unique, aligned
to that grid, and located on valid interior nodes. The feature supports at most
250,000 grid nodes. Route source and destination room types referenced by configured
rules must exist in the candidate.

## Configuration

```python
RoutingCostProfile(
    empty_node_cost: float,
    traversable_hint_node_cost: float,
    turn_cost: float,
    perimeter_bias_max_cost: float,
    traffic_conflict_cost: float,
)

CirculationRouteRule(
    id: int,
    name: str,
    source_room_type: RoomType,
    destination_room_type: RoomType,
    destination_selection: DestinationSelection,
    traffic_class: CirculationTrafficClass,
    allowed_transit_room_types: tuple[RoomType, ...],
    importance_weight: float,
    required_transit_room_types: tuple[RoomType, ...] = (),
)

HallwayConsolidationConfig(
    enabled: bool = True,
    minimum_separation_grid_steps: float = 2.0,
    max_route_cost_increase_ratio: float = 0.15,
)

CandidateCirculationConfig(
    costs: RoutingCostProfile,
    route_rules: tuple[CirculationRouteRule, ...],
    always_traversable_room_types: tuple[RoomType, ...],
    max_routing_passes: int = 3,
    hallway_consolidation: HallwayConsolidationConfig = HallwayConsolidationConfig(),
)
```

Validation and meaning:

- `RoutingCostProfile.empty_node_cost` and `traversable_hint_node_cost` must be
  positive finite values. `turn_cost` and `perimeter_bias_max_cost` must be finite and
  non-negative. `traffic_conflict_cost` must be positive and finite. Routing cost
  values are capped by the implementation's numerical safety limit of `1e12`.
- `CirculationRouteRule.id` must be a unique non-negative integer in the config;
  `name` must be non-empty; source and destination room types must be different;
  `importance_weight` must be positive and finite.
- `allowed_transit_room_types` and `required_transit_room_types` must each contain
  unique `RoomType` values. A required-transit type cannot be the route's source or
  destination type.
- `DestinationSelection.ALL_MATCHING` resolves one route from each source to every
  matching destination. `LOWEST_COST_MATCH` selects one lowest-cost reachable
  destination per source.
- `CirculationTrafficClass` values are `PUBLIC='public'` and `PRIVATE='private'`.
- `always_traversable_room_types` must contain unique `RoomType` members.
- `max_routing_passes` defaults to `3` and must be between `2` and `10` inclusive.

### Required transit / “must cross”

When `required_transit_room_types` is non-empty, a resolved route must cross at least
one intermediate candidate point whose room type is one of those configured types
before reaching the destination. This is an **any-of** requirement: a tuple containing
multiple room types does not require the path to cross every listed type.

Required-transit types are automatically traversable for that route; consumers do not
also need to repeat them in `allowed_transit_room_types` or
`always_traversable_room_types`.

Example:

```python
CirculationRouteRule(
    id=7,
    name="living-to-bathroom-via-hallway",
    source_room_type=RoomType.LIVING_ROOM,
    destination_room_type=RoomType.BATHROOM,
    destination_selection=DestinationSelection.LOWEST_COST_MATCH,
    traffic_class=CirculationTrafficClass.PUBLIC,
    allowed_transit_room_types=(),
    importance_weight=1.0,
    required_transit_room_types=(RoomType.HALLWAY,),
)
```

### Hallway consolidation

Unused hallway hints are removed first. If `hallway_consolidation.enabled=True`, the
feature then evaluates retained hallway hints that are close to another hallway hint.
A hallway is removed only after rerouting confirms that configured route coverage is
preserved and route cost degradation stays within the configured limit.

`minimum_separation_grid_steps` is measured as Euclidean distance in grid-index space,
not project-unit distance. A candidate is considered “nearby” when its distance is
strictly less than the configured value. With the default `2.0`, orthogonally adjacent
and diagonally adjacent hallway hints are eligible; points exactly two grid steps
apart are not.

`max_route_cost_increase_ratio` is the maximum allowed relative increase in route cost
compared with the baseline after unused hallway removal. It must be finite and in
`0.0..1.0`; the default `0.15` allows at most a 15% increase. Setting
`HallwayConsolidationConfig(enabled=False)` preserves the previous unused-only cleanup
behavior.

The consolidation decision values exposed in DEBUG are:

- `HallwayConsolidationDecision.REMOVED = 'removed'`
- `HallwayConsolidationDecision.KEPT_ROUTE_UNAVAILABLE = 'kept_route_unavailable'`
- `HallwayConsolidationDecision.KEPT_ROUTE_COVERAGE_CHANGED = 'kept_route_coverage_changed'`
- `HallwayConsolidationDecision.KEPT_ROUTE_COST_INCREASE = 'kept_route_cost_increase'`

Removal reasons are:

- `HallwayRemovalReason.UNUSED = 'unused'`
- `HallwayRemovalReason.CONSOLIDATED = 'consolidated'`

## Recommended values

**Package defaults:** `max_routing_passes=3`, hallway consolidation enabled,
`minimum_separation_grid_steps=2.0`, and `max_route_cost_increase_ratio=0.15`.
Routing costs are relative and need project calibration. If preserving every retained
hallway hint is more important than compactness, disable consolidation rather than
raising the route-cost tolerance arbitrarily.

## Outputs

Production result:

```python
CandidateCirculationResult(
    candidate: CandidateMap,
    hallway_classifications: tuple[HallwayClassification, ...] = (),
)
```

`result.candidate` preserves the original `ResolvedCandidateGrid` and removes hallway
points classified as unused or safely consolidated. `hallway_classifications`
contains the classifications for hallway hints retained in the production candidate.

In `ExecutionMode.PRODUCTION`, `execution.details is None`.

In `ExecutionMode.DEBUG`, details are:

```python
CandidateCirculationDetails(
    circulation_efficiency_score: float,
    routing_pass_count: int,
    grid_node_count: int,
    passes: tuple[RoutingPassDetails, ...],
    final_hallway_traffic: tuple[HallwayTrafficDetails, ...],
    removed_hallway_points: tuple[RemovedHallwayPointDetails, ...],
    hallway_consolidation_attempts: tuple[HallwayConsolidationAttemptDetails, ...],
)
```

Each `CirculationPathDetails` includes all previous path/cost fields plus:

```python
required_transit_room_types: tuple[RoomType, ...]
required_transit_point_keys: tuple[str, ...]
```

Each `HallwayTrafficDetails` now also contains:

```python
removal_reason: HallwayRemovalReason | None
```

Each removed point is reported as:

```python
RemovedHallwayPointDetails(
    point_key: str,
    room_id: str,
    hint_index: int,
    x: float,
    y: float,
    reason: HallwayRemovalReason,
)
```

Each consolidation attempt is reported as:

```python
HallwayConsolidationAttemptDetails(
    point_key: str,
    nearby_point_keys: tuple[str, ...],
    decision: HallwayConsolidationDecision,
    max_route_cost_increase_ratio: float | None,
)
```

## Warnings / diagnostics

Candidate Circulation has no separate warning collection. In `DEBUG`, `CandidateCirculationDetails` exposes circulation-efficiency score, routing-pass count, grid-node count, each routing pass, final hallway traffic, removed hallway points, and hallway-consolidation attempts. Route/input/alignment failures raise the documented circulation exceptions rather than returning warning-only results.

## Errors / failure conditions

Bad input/configuration can raise `TypeError`, `ValueError`, or
`CandidateCirculationInputError`. Off-grid or grid-consistency problems raise
`GridAlignmentError`. A configured route that cannot satisfy reachability, including
a required-transit rule, raises `CirculationPathNotFoundError`.

A rejected consolidation attempt is not a feature failure; the hallway is simply kept
and the reason is available in DEBUG details.

## Usage example

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    HallwayConsolidationConfig,
    RoutingCostProfile,
    refine_candidate_circulation,
)

config = CandidateCirculationConfig(
    costs=RoutingCostProfile(2.0, 0.75, 0.35, 1.5, 8.0),
    route_rules=(example_route_rule,),
    always_traversable_room_types=(RoomType.HALLWAY,),
    hallway_consolidation=HallwayConsolidationConfig(
        enabled=True,
        minimum_separation_grid_steps=2.0,
        max_route_cost_increase_ratio=0.15,
    ),
)
execution = refine_candidate_circulation(
    CandidateCirculationInput(example_candidate, config)
)
cleaned = execution.result.candidate
```

## Important behavioral notes

Routing moves orthogonally between adjacent grid indexes. Required transit is checked
against intermediate **candidate points**, not arbitrary empty grid cells. The input
candidate is not mutated. If hallway hints are removed, the consumer must keep later
room specifications/solver inputs consistent with the returned candidate identities.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.candidate_circulation`. Its current exported symbols are:

- `CandidateCirculationConfig`
- `CandidateCirculationDetails`
- `CandidateCirculationError`
- `CandidateCirculationInput`
- `CandidateCirculationInputError`
- `CandidateCirculationResult`
- `CirculationPathDetails`
- `CirculationTrafficClass`
- `CirculationPathNotFoundError`
- `CirculationRouteRule`
- `DestinationSelection`
- `GridAlignmentError`
- `GridNode`
- `HallwayClassification`
- `HallwayConsolidationAttemptDetails`
- `HallwayConsolidationConfig`
- `HallwayConsolidationDecision`
- `HallwayRemovalReason`
- `HallwayTrafficClass`
- `HallwayTrafficDetails`
- `RemovedHallwayPointDetails`
- `RouteCostBreakdown`
- `RoutingCostProfile`
- `RoutingPassDetails`
- `TrafficClass`
- `refine_candidate_circulation`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
