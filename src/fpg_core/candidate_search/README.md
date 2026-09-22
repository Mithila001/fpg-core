# Candidate Search

Candidate Search uses Optuna to place one hint point per active room on the exact grid prepared by Floor Plan Preprocessing.

## Guide

### Public API

Use imports from `fpg_core.candidate_search`:

```python
from fpg_core.candidate_search import (
    CandidateSearchConfig,
    CandidateSearchInput,
    CandidateSearchSession,
    build_candidate_search_targets,
    search_candidates,
)
```

`search_candidates()` is the normal complete-search entry point. `CandidateSearchSession` is available when the caller needs to evaluate trials incrementally.

### Inputs

Candidate Search now keeps processing input separate from configuration.

Processing input:

- `targets`: concrete room targets for this floor-plan operation.
- `grid`: the exact `ResolvedCandidateGrid` prepared by preprocessing.
- `hallway_room_count_range`: the `HallwayRoomCountRange` prepared for this floor plan.
- `evaluator`: callback that scores one generated `CandidateMap`.

Configuration:

```python
CandidateSearchConfig(
    trial_count=500,
    max_grid_node_count=250_000,
    random_seed=42,
)
```

- `trial_count`: number of Optuna trials to run. Defaults to `500` and must be at least `1`.
- `max_grid_node_count`: safety limit for the supplied grid. Defaults to `250_000` and must be at least `9`.
- `random_seed`: optional deterministic Optuna sampler seed.

Complete usage:

```python
from fpg_core.candidate_search import (
    CandidateSearchConfig,
    CandidateSearchInput,
    build_candidate_search_targets,
    search_candidates,
)
from fpg_core.domain import ExecutionMode

prepared = preprocessing_execution.result

targets = build_candidate_search_targets(prepared.generation_spec)

config = CandidateSearchConfig(
    trial_count=500,
    max_grid_node_count=250_000,
    random_seed=42,
)


def evaluator(candidate):
    return 100.0


search_input = CandidateSearchInput(
    targets=targets,
    grid=prepared.candidate_grid,
    hallway_room_count_range=prepared.hallway_room_count_range,
    evaluator=evaluator,
    config=config,
)

execution = search_candidates(
    search_input,
    mode=ExecutionMode.DEBUG,
)

best = execution.result
```

Candidate Search does not create or resolve a grid. The supplied `ResolvedCandidateGrid` is the source of truth.

Every active room receives exactly one point. One hallway target represents one hallway room. Each trial selects one global hallway count within the prepared range and activates that many hallway targets.

Outer grid nodes are not used as hint points. Points are sampled without replacement, so generated room points do not overlap.

`CandidateSearchInput` requires:

- unique room IDs,
- exactly `hallway_room_count_range.maximum` hallway targets,
- a grid within `config.max_grid_node_count`,
- enough non-edge grid nodes for all non-hallway rooms plus the maximum hallway count.

Use:

```python
targets = build_candidate_search_targets(prepared.generation_spec)
```

to create targets from the prepared generation specification.

### Outputs

`search_candidates()` returns:

```python
FeatureExecution[CandidateSearchResult, CandidateSearchDetails]
```

Production result:

```python
execution.result.candidate
execution.result.score
execution.result.completed_trials
execution.result.hallway_room_count
execution.metadata
```

In `ExecutionMode.DEBUG`, `execution.details` additionally contains:

```python
execution.details.grid
execution.details.optuna_trial_count
execution.details.completed_trial_count
```

After Candidate Search, the selected candidate can be converted into the exact solver specification through preprocessing:

```python
candidate_spec = prepared.generation_spec_for_candidate(
    execution.result.candidate
)
```

### Errors and Expected Behaviour

- Invalid input types or values raise `TypeError` or `ValueError` during contract validation.
- Invalid session state raises `CandidateSearchStateError`.
- A fixed `random_seed` makes the Optuna sampler reproducible for the same compatible inputs and environment.
- Candidate Search does not mutate the supplied targets, grid, hallway range, or configuration.

Incremental execution allows only one pending trial at a time:

```python
session = CandidateSearchSession(search_input)

while session.has_remaining_trials:
    suggestion = session.ask_next_trial()
    score = evaluator(suggestion.candidate)
    session.record_score(suggestion, score)

best = session.best_result()
```

### Extension Points

The evaluator callback is the intended scoring extension point. Candidate Search generates candidates; the caller decides how those candidates are scored.

## Migration

`CandidateSearchSettings` has been removed because it mixed floor-plan processing data with search configuration.

Old:

```python
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
```

New:

```python
config = CandidateSearchConfig(
    trial_count=500,
    max_grid_node_count=250_000,
    random_seed=42,
)

search_input = CandidateSearchInput(
    targets=targets,
    grid=prepared.candidate_grid,
    hallway_room_count_range=prepared.hallway_room_count_range,
    evaluator=evaluator,
    config=config,
)
```

`build_candidate_grid()` remains available for API compatibility, but it only validates and returns an already prepared grid. It does not generate X/Y positions.

## AI Instructions

- Keep this README synchronized with public behaviour.
- Keep processing input and reusable search configuration clearly separated.
- Update examples when public contracts change.
- Do not document private optimizer implementation as supported API.
- Do not import another feature's internal modules.
