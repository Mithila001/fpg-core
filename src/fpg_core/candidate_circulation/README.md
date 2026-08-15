# Candidate Circulation

Candidate Circulation consumes a `CandidateMap`; it does not build or receive an independent fixed-scale grid.

```python
from fpg_core.candidate_circulation import HallwayConsolidationConfig

config = CandidateCirculationConfig(
    costs=costs,
    route_rules=route_rules,
    always_traversable_room_types=(RoomType.HALLWAY,),
    max_routing_passes=3,
    hallway_consolidation=HallwayConsolidationConfig(
        enabled=True,
        minimum_separation_grid_steps=2.0,
        max_route_cost_increase_ratio=0.15,
    ),
)

execution = refine_candidate_circulation(
    CandidateCirculationInput(candidate=candidate, config=config),
    mode=ExecutionMode.DEBUG,
)

clean_candidate = execution.result.candidate
hallway_tags = execution.result.hallway_classifications
```

## Required transit ("must cross")

A route rule may require one or more intermediate room types:

```python
CirculationRouteRule(
    ...,
    allowed_transit_room_types=(),
    required_transit_room_types=(RoomType.HALLWAY,),
)
```

When `required_transit_room_types` is non-empty, the resolved path must cross at least one intermediate candidate point whose room type is in that tuple before reaching the destination. Required transit types are automatically traversable; they do not also need to appear in `allowed_transit_room_types`.

## Hallway consolidation

Unused hallways are still removed first. When consolidation is enabled, nearby retained hallway hints are then tested one at a time. A hallway is removed only when all configured route coverage remains available and no route exceeds `max_route_cost_increase_ratio` relative to the post-unused-removal baseline.

`minimum_separation_grid_steps=2.0` treats orthogonally adjacent and diagonally adjacent hallway hints as candidates for consolidation. Set `enabled=False` to keep the old unused-only cleanup behavior.

Routing uses orthogonal neighboring grid indexes. Existing movement costs remain per entered node. The original candidate grid is preserved.

In DEBUG mode, route details include required-transit types and the actual required-transit point keys used. Hallway debug data reports whether a point was removed because it was `unused` or `consolidated`, plus every consolidation attempt and its decision.
