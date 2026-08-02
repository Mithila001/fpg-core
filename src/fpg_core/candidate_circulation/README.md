# Candidate Circulation

Builds orthogonal grid routes between candidate hint points, classifies hallway traffic, and removes unused hallway hints. It runs after Candidate Search and before Candidate Scoring or floor-plan solving.

## Guide

### Public API

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    RoutingCostProfile,
    refine_candidate_circulation,
)
from fpg_core.domain import (
    CirculationGrid,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    ExecutionMode,
    RoomType,
)

execution = refine_candidate_circulation(
    CandidateCirculationInput(
        points=candidate_points,
        config=CandidateCirculationConfig(
            grid=CirculationGrid(width=100, length=80, scale=10),
            costs=RoutingCostProfile(
                empty_node_cost=2,
                traversable_hint_node_cost=1,
                turn_cost=0.25,
                perimeter_bias_max_cost=0.2,
                traffic_conflict_cost=25,
            ),
            route_rules=(
                CirculationRouteRule(
                    id=1,
                    name="Living to all bedrooms",
                    source_room_type=RoomType.LIVING_ROOM,
                    destination_room_type=RoomType.BEDROOM,
                    destination_selection=DestinationSelection.ALL_MATCHING,
                    traffic_class=CirculationTrafficClass.PRIVATE,
                    allowed_transit_room_types=(),
                    importance_weight=1,
                ),
            ),
            always_traversable_room_types=(RoomType.HALLWAY,),
        ),
    ),
    mode=ExecutionMode.DEBUG,
)

cleaned_points = execution.result.points
hallway_tags = execution.result.hallway_classifications
```

`TrafficClass` remains re-exported by this feature as a compatibility alias for `CirculationTrafficClass`.

### Inputs

- `CandidatePoint`, `CirculationGrid`, `CirculationRouteRule`, route enums, and hallway classification contracts are shared through `fpg_core.domain`.
- `RoutingCostProfile` adds the feature-specific multi-pass hallway conflict cost.
- `DestinationSelection.ALL_MATCHING` routes every source to every matching destination.
- `DestinationSelection.LOWEST_COST_MATCH` keeps the cheapest reachable destination per source.
- Occupied hints are blocked unless they are the destination or their room type is explicitly traversable.
- Grid dimensions must be exact multiples of the scale. Hints must align to the grid and cannot overlap.

### Routing and hallway removal

Pass 1 routes without hallway conflict penalties. Later passes penalize public routes using private hallways and private routes using public hallways. Routing stops when hallway classifications stabilize or the configured pass limit is reached.

Final hallway classes are:

- `PUBLIC`
- `PRIVATE`
- `MIXED`
- `UNCLASSIFIED`
- `UNUSED`

`UNUSED` hallway hints are removed from `result.points`.

### Outputs

`refine_candidate_circulation()` returns:

```text
FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

Production always returns:

- `result.points`: cleaned candidate points.
- `result.hallway_classifications`: all original hallway identities and their final classes, including removed `UNUSED` hints.
- `details=None`.

DEBUG additionally returns routing passes, paths, cost breakdowns, hallway usage, removed hints, per-path `path_efficiency_score`, and aggregate `circulation_efficiency_score`.

The efficiency values compare routed cost with the direct Manhattan reference cost. They are debug information, not a Candidate Scoring contribution.

### Errors and Expected Behaviour

The feature fails for invalid configuration, missing endpoint room types, grid misalignment, out-of-bounds or overlapping hints, and unresolved required routes. Inputs are not mutated and routing is deterministic.

## AI Instructions

- Keep routing and hallway removal inside this feature.
- Keep shared circulation contracts in `fpg_core.domain`.
- Preserve room IDs and hallway hint indexes.
- Keep production hallway classifications available even when DEBUG details are omitted.
- Do not import another feature's internal modules.
