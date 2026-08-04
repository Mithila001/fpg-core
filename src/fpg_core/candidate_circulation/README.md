# Candidate Circulation

Candidate Circulation consumes a `CandidateMap`; it does not build or receive an independent fixed-scale grid.

```python
config = CandidateCirculationConfig(
    costs=costs,
    route_rules=route_rules,
    always_traversable_room_types=(RoomType.HALLWAY,),
    max_routing_passes=3,
)

execution = refine_candidate_circulation(
    CandidateCirculationInput(candidate=candidate, config=config),
    mode=ExecutionMode.DEBUG,
)

clean_candidate = execution.result.candidate
hallway_tags = execution.result.hallway_classifications
```

Routing uses orthogonal neighboring grid indexes. Existing movement costs remain per entered node. Unused hallway points are removed while the original candidate grid is preserved.
