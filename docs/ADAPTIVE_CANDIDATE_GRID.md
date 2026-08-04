# Adaptive Candidate Grid

## Purpose

Candidate Search, Candidate Circulation, and Relationship Quality must reason about the same selectable and routable locations. Version 0.2.0 resolves one grid during Candidate Search and carries it with every candidate.

```text
Preprocessing -> integer FloorSpec
Candidate Search -> CandidateMap(grid, points)
Candidate Circulation -> CandidateMap(same grid, cleaned points)
Candidate Scoring -> Relationship Quality uses same grid
```

## Grid construction

`long_axis_node_count` means the number of selectable nodes on the longest floor axis, including both boundaries.

For a `93 x 124` floor and `long_axis_node_count=20`:

- Y has 20 nodes.
- X is assigned the closest node count that keeps cells approximately square: 15 nodes.
- The grid contains 300 nodes.
- X and Y gaps are balanced whole-unit gaps, normally differing by at most one project unit.
- The exact boundary remains `0..93 x 0..124`.

No floor dimension is shrunk for grid divisibility.

## Recommended research profile

```python
CandidateSearchConfig(
    long_axis_node_count=20,
    max_grid_node_count=250_000,
    max_internal_sampling_attempts=100,
    min_hallway_hint_count=1,
    max_hallway_hint_count=5,
)
```

Increasing `long_axis_node_count` gives denser location choices and a larger routing graph. It also increases Optuna search complexity and routing cost.

## Candidate Search example

```python
from fpg_core.candidate_search import (
    CandidateSearchInput,
    CandidateSearchSettings,
    CandidateSearchTarget,
    search_candidates,
)
from fpg_core.domain import ExecutionMode, RoomType

settings = CandidateSearchSettings(
    floor=generation_spec.floor,
    long_axis_node_count=20,
    max_grid_node_count=250_000,
    max_internal_sampling_attempts=100,
    trial_count=500,
    random_seed=42,
    min_hallway_hint_count=1,
    max_hallway_hint_count=5,
)

search_input = CandidateSearchInput(
    targets=targets,
    settings=settings,
    evaluator=lambda candidate: evaluate_pipeline_candidate(candidate),
)

execution = search_candidates(search_input, mode=ExecutionMode.DEBUG)
best_candidate = execution.result.candidate
```

The evaluator receives `CandidateMap`, not only points.

## Overlap behavior

Candidate Search samples node indexes. When two hints select the same node, the internal Optuna trial is marked failed and another trial is requested. The invalid candidate is not sent to the external evaluator, Circulation, or Scoring.

DEBUG details expose:

- `overlap_rejection_count`
- `optuna_trial_count`
- `completed_trial_count`
- `grid`

Optuna trial numbers can therefore contain gaps.

## Routing cost semantics

Version 0.2.0 keeps existing per-node-step movement costs. A move to an adjacent node counts as one routing step even when balanced adaptive gaps differ by one project unit. This isolates grid-contract migration from scoring-model retuning.

Physical-distance-weighted routing is intentionally deferred.

## Independent analysis grids

These settings are unrelated to Candidate Search locations:

- `zone_suitability.zone_count_per_axis`: relative zone subdivision.
- `spatial_distribution.sample_count_per_axis`: number of measurement probes per axis.

They cover the same floor boundary but do not define candidate nodes.
