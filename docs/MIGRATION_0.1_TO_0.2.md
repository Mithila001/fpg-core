# Migrating Consumers from fpg-core 0.1.x to 0.2.0

## Impact level

This is a deliberate breaking release. Applications using preprocessing, Candidate Search, Candidate Circulation, or Candidate Scoring must update constructors, callback signatures, serialization, and configuration mapping.

The solver, post-processing, openings, buildable-land, usable-land, and final floor-plan scoring APIs are not directly changed by this grid migration. They can still observe different generated inputs because floor dimensions and candidate locations now change.

## 1. Configuration schema

Change package configuration schema:

```diff
- schema_version: 1
+ schema_version: 2
```

Remove the application-level fixed grid setting:

```diff
p01a:
-  grid_resolution: 10.0
```

Add Candidate Search adaptive-grid settings:

```yaml
candidate_search:
  long_axis_node_count: 20
  max_grid_node_count: 250000
  max_internal_sampling_attempts: 100
  min_hallway_hint_count: 1
  max_hallway_hint_count: 5
```

Add preprocessing aspect residual:

```yaml
preprocessing:
  max_aspect_residual_units: 20
```

Rename scoring fields:

```diff
candidate_scoring:
  zone_suitability:
-    grid_size: 3
+    zone_count_per_axis: 3

  spatial_distribution:
-    grid_size: 20
+    sample_count_per_axis: 20
```

## 2. Preprocessing behavior

Before 0.2.0, floor selection could return decimal dimensions such as `93.2737905309 x 124.3650540412`.

In 0.2.0:

1. Request maximum width and length are floored to whole project units.
2. Floor selection evaluates integer width/length combinations.
3. The selected area must remain between the calculated minimum and maximum target areas.
4. The selected dimensions must satisfy room-width requirements.
5. `abs(length - width * requested_ratio)` must not exceed `max_aspect_residual_units`.

Consequences:

- Floor dimensions can be up to almost one project unit below each supplied maximum before area/aspect selection.
- The selected floor may differ from 0.1.x even with the same request and room profile.
- Downstream solver geometry and final scores may change.
- DEBUG `FloorSelection` contains raw limits, normalized limits, selected dimensions, selected ratio, residual, and unused limit area.

## 3. Candidate Search API

### Old

```python
settings = CandidateSearchSettings(
    min_x=0,
    max_x=spec.floor.width,
    min_y=0,
    max_y=spec.floor.length,
    grid_resolution=10,
    trial_count=500,
    random_seed=42,
)

def evaluator(points: tuple[CandidatePoint, ...]) -> float:
    ...
```

### New

```python
settings = CandidateSearchSettings(
    floor=spec.floor,
    long_axis_node_count=20,
    max_grid_node_count=250_000,
    max_internal_sampling_attempts=100,
    trial_count=500,
    random_seed=42,
)

def evaluator(candidate: CandidateMap) -> float:
    ...
```

Search results now use:

```python
result.candidate
result.points  # convenience property
result.grid    # convenience property
```

Update persisted trial payloads to store the grid with the points. At minimum persist:

```json
{
  "grid": {
    "x_positions": [0, 6, 13],
    "y_positions": [0, 7, 13]
  },
  "points": []
}
```

Do not reconstruct a grid from selected points.

## 4. Candidate Circulation API

### Old

```python
config = CandidateCirculationConfig(
    grid=CirculationGrid(width=width, length=length, scale=10),
    costs=costs,
    route_rules=rules,
    always_traversable_room_types=(RoomType.HALLWAY,),
)

circulation_input = CandidateCirculationInput(
    points=suggestion.points,
    config=config,
)
```

### New

```python
config = CandidateCirculationConfig(
    costs=costs,
    route_rules=rules,
    always_traversable_room_types=(RoomType.HALLWAY,),
)

circulation_input = CandidateCirculationInput(
    candidate=suggestion.candidate,
    config=config,
)
```

Result access:

```python
clean_candidate = execution.result.candidate
clean_points = execution.result.points
classifications = execution.result.hallway_classifications
```

The candidate grid is preserved when unused hallway points are removed.

## 5. Candidate Scoring API

### Old

```python
scoring_input = CandidateScoringInput(
    specification=spec,
    candidate=circulation_result.points,
    hallway_classifications=circulation_result.hallway_classifications,
)
```

### New

```python
scoring_input = CandidateScoringInput(
    specification=spec,
    candidate=circulation_result.candidate,
    hallway_classifications=circulation_result.hallway_classifications,
)
```

Relationship configuration no longer contains a grid:

```diff
relationship = RelationshipQualityConfig(
-    grid=CirculationGrid(...),
     costs=relationship_costs,
     route_rules=route_rules,
     always_traversable_room_types=(RoomType.HALLWAY,),
)
```

Relationship Quality validates that `candidate.grid` exactly matches the specification floor.

## 6. P01A orchestration update

Recommended flow:

```python
preprocessed = prepare_generation_input(...)
spec = preprocessed.result.generation_spec

session = CandidateSearchSession(
    CandidateSearchInput(
        targets=targets,
        settings=CandidateSearchSettings(
            floor=spec.floor,
            long_axis_node_count=config.candidate_search.long_axis_node_count,
            max_grid_node_count=config.candidate_search.max_grid_node_count,
            max_internal_sampling_attempts=(
                config.candidate_search.max_internal_sampling_attempts
            ),
            trial_count=trial_count,
            random_seed=random_seed,
            min_hallway_hint_count=(
                config.candidate_search.min_hallway_hint_count
            ),
            max_hallway_hint_count=(
                config.candidate_search.max_hallway_hint_count
            ),
        ),
        evaluator=score_candidate_map,
    )
)

suggestion = session.ask_next_trial()

circulation = refine_candidate_circulation(
    CandidateCirculationInput(
        candidate=suggestion.candidate,
        config=circulation_config,
    ),
    mode=mode,
)

score = evaluate_candidate(
    CandidateScoringInput(
        specification=spec,
        candidate=circulation.result.candidate,
        hallway_classifications=(
            circulation.result.hallway_classifications
        ),
    ),
    registry=registry,
    config=scoring_config,
    mode=mode,
)

session.record_score(suggestion, score.total_score)
```

## 7. Database and API payload updates

Applications storing candidate trials should add grid data to every candidate record. Recommended normalized meaning:

- `x_positions`: complete selectable X coordinates.
- `y_positions`: complete selectable Y coordinates.
- points reference physical `x/y`; optional node indexes may be stored as derived/debug fields.

Old records containing only points cannot reliably recover the original search grid. Treat them as legacy records and do not run new Circulation or Relationship Quality against a guessed grid.

For frontend visualization:

- draw grid lines from `x_positions` and `y_positions`;
- use the exact floor width/length from the specification;
- do not assume uniform pixel/project-unit gap from a single scale;
- adjacent project-unit gaps can differ by one unit.

## 8. Score changes

Expect changed Candidate Search output and scores even with the same random seed:

- Search parameter ranges and coordinates changed.
- Invalid overlaps no longer reach the external evaluation pipeline.
- Optuna trial numbers can have gaps.
- Circulation routes use a different number of index steps than a former fixed 10-unit grid.
- Relationship Quality now receives a matching grid instead of failing width/length validation.
- When Relationship Quality previously errored and evaluator errors were ignored, the remaining weights were renormalized. It now participates with its configured weight, materially changing total scores.

Do not compare 0.1.x and 0.2.0 score distributions as if they use the same scoring model. Start a new experiment/version label.

## 9. Consumer test checklist

- Configuration schema upgraded to 2.
- No use of `p01a.grid_resolution` remains.
- Search callback accepts `CandidateMap`.
- Candidate grid is persisted with each trial.
- No constructor passes `CirculationGrid` to Circulation or Relationship Quality.
- Circulation input uses `candidate=`.
- Scoring input uses `CandidateMap`.
- UI handles non-uniform adjacent axis gaps.
- Trial indexing does not assume contiguous Optuna numbers.
- Relationship Quality status is `completed` for valid candidates.
- Existing experiment results are versioned separately.
