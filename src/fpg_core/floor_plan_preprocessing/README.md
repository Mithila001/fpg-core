# Floor Plan Preprocessing

Floor Plan Preprocessing converts client room requests and configuration data into:

1. a validated generation-specification template,
2. an exact centered candidate grid,
3. the allowed hallway-room count range.

The feature has no dependency on Candidate Search internals. It communicates through shared contracts from `fpg_core.domain`.

## Units

- `10` project units = `1` meter
- `1` project unit = `10` centimeters

Selected floor dimensions use whole project units.

## Candidate Search configuration

`PreprocessingConfig` now requires:

```python
candidate_search_grid_spacing: int
max_hallway_room_count: int
```

Rules:

- `candidate_search_grid_spacing >= 1`
- spacing must be even
- the selected floor must be at least two spacing intervals on both axes
- `max_hallway_room_count >= 1`
- the minimum hallway room count is always `1`

Example:

```python
config = PreprocessingConfig(
    room_count_rules=...,
    supported_aspect_ratios=...,
    room_sizes=...,
    room_relations=...,
    mandatory_room_types=...,
    floor_area_buffer=20.0,
    hallway_area_buffer=12.0,
    max_hallway_room_count=3,
    hallway_min_width=9.0,
    candidate_search_grid_spacing=6,
    default_room_size="medium",
    max_aspect_residual_units=20.0,
)
```

This produces the hallway range:

```text
minimum = 1
maximum = 3
```

## Centered divisible candidate grid

After selecting the actual floor, preprocessing shrinks each grid axis directly:

```text
grid_extent = floor_extent - (floor_extent % grid_spacing)
origin = (floor_extent - grid_extent) / 2
```

Example:

```text
selected floor = 121 x 83
spacing        = 6

grid width     = 121 - (121 % 6) = 120
grid length    = 83  - (83  % 6) = 78
origin x       = (121 - 120) / 2 = 0.5
origin y       = (83  - 78)  / 2 = 2.5
```

The resulting grid runs from:

```text
X: 0.5, 6.5, 12.5, ..., 120.5
Y: 2.5, 8.5, 14.5, ..., 80.5
```

This is an equal trim from opposite sides. The actual floor is not changed.

Preprocessing resolves these positions into one `ResolvedCandidateGrid` and
passes that exact object to downstream features. The full outer grid is kept,
but Candidate Search only uses non-edge nodes for hint points:

```text
X X X X X
X O O O X
X O O O X
X X X X X
```

`X` nodes are forbidden for hint points. `O` nodes are selectable. Because
points are selected without replacement, `candidate_search_grid_spacing` is the
minimum possible distance between two generated hint points.

## Hallway room identities

Preprocessing creates concrete potential hallway room IDs up to the configured maximum.

For:

```python
max_hallway_room_count=3
```

The generation template contains three hallway `RoomSpec`s, typically:

```text
hallway_1
hallway_2
hallway_3
```

Candidate Search chooses one global count per trial. If it chooses `2`, only `hallway_1` and `hallway_2` receive points. Each point represents one distinct hallway room.

## Running preprocessing

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_preprocessing import prepare_generation_input

execution = prepare_generation_input(
    preprocessing_input,
    mode=ExecutionMode.DEBUG,
)

prepared = execution.result
```

Production result fields:

```python
prepared.generation_spec
prepared.candidate_grid
prepared.hallway_room_count_range
```

`prepared.candidate_search_space` remains as a compatibility view derived from
the prepared grid.

DEBUG additionally provides:

```python
execution.details.floor_selection
execution.details.candidate_grid_selection
execution.details.hallway_room_count_range
```

## Using the result with Candidate Search

```python
from fpg_core.candidate_search import (
    CandidateSearchInput,
    CandidateSearchSettings,
    build_candidate_search_targets,
    search_candidates,
)

prepared = preprocessing_execution.result

targets = build_candidate_search_targets(prepared.generation_spec)
settings = CandidateSearchSettings(
    grid=prepared.candidate_grid,
    hallway_room_count_range=prepared.hallway_room_count_range,
    max_grid_node_count=250_000,
    trial_count=500,
    random_seed=42,
)

search_input = CandidateSearchInput(
    targets=targets,
    settings=settings,
    evaluator=evaluator,
)

search_execution = search_candidates(search_input)
best_candidate = search_execution.result.candidate
```

## Preparing the candidate-specific solver specification

`prepared.generation_spec` contains all potential hallway rooms up to the maximum. Do not pass that template directly to the solver after Candidate Search.

Filter it using the selected candidate:

```python
candidate_generation_spec = prepared.generation_spec_for_candidate(
    best_candidate
)
```

The returned specification contains:

- every non-hallway room,
- only the hallway rooms active in that candidate,
- relations filtered to active room IDs.

## Migration

Replace the old fixed field:

```python
hallway_count=...
```

with:

```python
max_hallway_room_count=...
candidate_search_grid_spacing=...
```

The hallway minimum is no longer configurable; it is always `1`.
