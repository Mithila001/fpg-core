# Candidate Circulation

Builds orthogonal grid routes between candidate hint points, infers hallway traffic roles, and removes hallway hints unused by the final routes. It is intended to run after Candidate Search and before Candidate Scoring or floor-plan solving.

## Guide

### Public API

```python
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    CirculationGrid,
    CirculationRouteRule,
    DestinationSelection,
    RoutingCostProfile,
    TrafficClass,
    refine_candidate_circulation,
)
from fpg_core.domain import ExecutionMode, RoomType

execution = refine_candidate_circulation(
    CandidateCirculationInput(
        points=candidate_points,
        config=CandidateCirculationConfig(
            grid=CirculationGrid(
                width=100,
                length=80,
                scale=10,
            ),
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
                    traffic_class=TrafficClass.PRIVATE,
                    allowed_transit_room_types=(),
                    importance_weight=1,
                ),
                CirculationRouteRule(
                    id=2,
                    name="Bedroom to nearest bathroom",
                    source_room_type=RoomType.BEDROOM,
                    destination_room_type=RoomType.BATHROOM,
                    destination_selection=DestinationSelection.LOWEST_COST_MATCH,
                    traffic_class=TrafficClass.PRIVATE,
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
```

### Inputs

- `CirculationGrid`: required usable-floor width, length, and grid scale. `origin_x` and `origin_y` default to `0`.
- `RoutingCostProfile`: all routing costs are required. The caller owns tuning.
- `CirculationRouteRule`: room-type endpoints, destination selection, traffic class, explicit transit permissions, and diagnostic importance weight.
- `DestinationSelection.ALL_MATCHING`: every matching source routes to every matching destination.
- `DestinationSelection.LOWEST_COST_MATCH`: every matching source keeps only its lowest-cost reachable matching destination.
- `always_traversable_room_types`: global transit permissions, normally including `RoomType.HALLWAY`.
- `max_routing_passes`: defaults to `3`, must be between `2` and `10`.

Every move enters one orthogonal grid node. Entering an empty node or an allowed hint node uses the corresponding configured cost. A turn adds `turn_cost`. `perimeter_bias_max_cost` adds a rectangular centre-to-boundary tie-break cost based on the traversed edge midpoint.

Occupied hint nodes are blocked unless they are the destination, their room type is globally traversable, or the active route explicitly allows that room type. This supports cases such as Kitchen to Living Room through Dining Room without making all rooms valid transit spaces.

The feature does not infer a grid. Grid dimensions must be exact multiples of the scale, every hint must align with the grid and stay inside it, and overlapping hints are rejected. Grids above 250,000 nodes fail through an internal safety limit.

### Routing passes and hallway removal

Pass 1 routes without hallway traffic penalties. Hallway usage is then classified from public/private route counts:

- one used hallway hint: `UNCLASSIFIED`;
- no traffic: `UNUSED`;
- equal public/private route count: `MIXED`;
- otherwise the majority traffic class.

Pass 2 adds `traffic_conflict_cost` when a public route enters a private hallway or a private route enters a public hallway. Mixed, unclassified, and unused hallways add no conflict cost. Another pass runs only while classifications change and the configured pass limit permits it.

Hallway hints classified `UNUSED` after the final pass are removed. Remaining point identities and hallway `hint_index` values are preserved; points are not renumbered.

### Outputs

`refine_candidate_circulation()` returns:

```text
FeatureExecution[CandidateCirculationResult, CandidateCirculationDetails]
```

- `result.points`: candidate points after unused hallway hints are removed.
- `details`: `None` in `PRODUCTION`.
- `details` in `DEBUG`: every routed path and grid node, cost breakdowns, diagnostic scores, all routing passes, hallway traffic/classification, and removed hallway information.
- `metadata`: selected execution mode and duration.

The diagnostic score is not a Candidate Scoring contribution. It compares each final route cost with a direct Manhattan reference cost and combines route scores using the required rule importance weights. Hallway PUBLIC/PRIVATE/MIXED classification itself uses route counts, not those score weights.

### Errors and Expected Behaviour

The feature fails fast for invalid configuration, missing route endpoint room types, grid misalignment, out-of-bounds or overlapping hints, and routes that cannot be resolved. It does not mutate input points. Routing is deterministic for identical inputs.

## AI Instructions

- Keep routing and hallway removal inside this feature.
- Do not move its diagnostic score back into Candidate Scoring.
- Keep tuning values explicit; do not add silent scoring or routing defaults.
- Preserve room IDs and hallway hint indexes when pruning points.
- Keep public operations and contracts exposed through `api.py`.
- Update this README when route expansion, costs, traffic classification, pruning, or DEBUG details change.
- Do not import another feature's internal modules.
