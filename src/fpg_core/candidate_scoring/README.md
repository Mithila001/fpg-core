# Candidate Scoring

Candidate Scoring receives a typed `CandidateMap`:

```python
scoring_input = CandidateScoringInput(
    specification=spec,
    candidate=circulation.result.candidate,
    hallway_classifications=circulation.result.hallway_classifications,
)
```

Grid behavior by evaluator:

- Relationship Quality uses `candidate.grid`.
- Zone Suitability uses `zone_count_per_axis` as a relative zoning overlay.
- Spatial Distribution uses `sample_count_per_axis` as a coverage measurement density.
- Exterior Clearance uses floor geometry and candidate coordinates.

Relationship configuration contains routing costs and rules, but no independent grid:

```python
relationship = RelationshipQualityConfig(
    costs=costs,
    route_rules=route_rules,
    always_traversable_room_types=(RoomType.HALLWAY,),
)
```
