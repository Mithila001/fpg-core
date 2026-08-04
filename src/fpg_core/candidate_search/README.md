# Candidate Search

Candidate Search uses Optuna to place one hint point per active room on the exact grid prepared by Floor Plan Preprocessing.

## Core rules

- Every active room receives exactly one point.
- One hallway point represents one hallway room.
- Every trial has between `1` and the prepared maximum number of hallway rooms.
- The hallway count is sampled once globally per trial.
- Points are sampled without replacement, so overlap cannot occur.

## Required preprocessing data

Candidate Search receives shared domain contracts:

```python
CandidateSearchSpace
HallwayRoomCountRange
```

The search space includes:

```python
origin_x
origin_y
width
length
grid_spacing
```

Candidate Search does not shrink or reposition the floor. That work belongs to Floor Plan Preprocessing.

## Complete usage

```python
from fpg_core.candidate_search import (
    CandidateSearchInput,
    CandidateSearchSettings,
    build_candidate_search_targets,
    search_candidates,
)
from fpg_core.domain import ExecutionMode

prepared = preprocessing_execution.result

targets = build_candidate_search_targets(prepared.generation_spec)
settings = CandidateSearchSettings(
    search_space=prepared.candidate_search_space,
    hallway_room_count_range=prepared.hallway_room_count_range,
    max_grid_node_count=250_000,
    trial_count=500,
    random_seed=42,
)


def evaluator(candidate):
    return 100.0


search_input = CandidateSearchInput(
    targets=targets,
    settings=settings,
    evaluator=evaluator,
)

execution = search_candidates(
    search_input,
    mode=ExecutionMode.DEBUG,
)

best = execution.result
```

## Hallway behavior

Assume preprocessing supplies:

```text
HallwayRoomCountRange(minimum=1, maximum=3)
```

and the targets include:

```text
hallway_1
hallway_2
hallway_3
```

A trial samples one value:

```text
hallway_room_count = 2
```

That trial activates:

```text
hallway_1 -> one point
hallway_2 -> one point
hallway_3 -> inactive
```

It does not create multiple indexed points under one hallway ID.

The selected count is available as:

```python
execution.result.hallway_room_count
```

## Sampling without replacement

For each trial Candidate Search:

1. creates the complete available-node list,
2. samples one remaining-node rank for each active room,
3. removes the selected node,
4. continues with the smaller remaining-node pool.

Therefore all completed candidates are non-overlapping by construction. `CandidateMap` also validates uniqueness defensively.

## Target validation

`CandidateSearchInput` requires:

- unique room IDs,
- exactly `hallway_room_count_range.maximum` hallway targets,
- enough grid nodes for all non-hallway rooms plus the maximum hallway count.

Use the helper to avoid manual target mistakes:

```python
targets = build_candidate_search_targets(prepared.generation_spec)
```

## Grid example

For:

```text
origin           = (0.5, 2.5)
search width     = 120
search length    = 78
grid spacing     = 6
```

Candidate Search creates:

```text
X nodes: 0.5, 6.5, ..., 120.5  -> 21 nodes
Y nodes: 2.5, 8.5, ..., 80.5   -> 14 nodes
Total: 294 nodes
```

## Incremental session API

```python
from fpg_core.candidate_search import CandidateSearchSession

session = CandidateSearchSession(search_input)

while session.has_remaining_trials:
    suggestion = session.ask_next_trial()
    score = evaluator(suggestion.candidate)
    result = session.record_score(suggestion, score)

best = session.best_result()
```

Only one trial may be pending at a time.

## Returned data

Production:

```python
execution.result.candidate
execution.result.score
execution.result.completed_trials
execution.result.hallway_room_count
execution.metadata
```

DEBUG additionally returns:

```python
execution.details.grid
execution.details.optuna_trial_count
execution.details.completed_trial_count
```

## Candidate-specific generation specification

The preprocessing generation template contains all possible hallway room IDs. After Candidate Search, create the exact specification for the selected candidate:

```python
candidate_spec = prepared.generation_spec_for_candidate(
    execution.result.candidate
)
```

Use `candidate_spec` for the solver or later room-generation stages.

## Migration

Remove these old Candidate Search settings:

```python
search_space_width
search_space_length
grid_spacing
min_hallway_hint_count
max_hallway_hint_count
```

Replace them with:

```python
search_space=prepared.candidate_search_space
hallway_room_count_range=prepared.hallway_room_count_range
```

The old behavior where one hallway target produced multiple indexed hint points has been removed.
