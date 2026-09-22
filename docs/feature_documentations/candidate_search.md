# Candidate Search

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Uses Optuna to sample non-overlapping, non-edge grid points for every active room and
returns the candidate with the highest consumer-supplied score. Use it when room
placement hints need exploration on a prepared discrete grid.

## Public API

```python
build_candidate_grid(*, grid: ResolvedCandidateGrid,
                     max_grid_node_count: int) -> ResolvedCandidateGrid
build_candidate_search_targets(specification: FloorPlanGenerationSpec
                              ) -> tuple[CandidateSearchTarget, ...]
search_candidates(search_input: CandidateSearchInput, *,
                  mode: ExecutionMode = ExecutionMode.PRODUCTION
                 ) -> FeatureExecution[CandidateSearchResult, CandidateSearchDetails]
CandidateSearchSession(search_input: CandidateSearchInput)
```

All are exported from `fpg_core.candidate_search`. The session exposes
`has_remaining_trials: bool`, `has_pending_trial: bool`, `remaining_trials: int`,
`completed_trials: int`, `optuna_trial_count: int`, `grid`, and `search_input`
properties, plus `ask_next_trial() -> CandidateSuggestion`,
`record_score(suggestion: CandidateSuggestion, score: float) -> CandidateTrialResult`,
`run_next_trial() -> CandidateTrialResult`, `fail_pending_trial() -> None`,
`best_result() -> CandidateSearchResult`, and
`debug_details() -> CandidateSearchDetails` for incremental evaluation.

## Inputs

- `CandidateSearchInput(targets, grid, hallway_room_count_range, evaluator, config)`
  requires unique targets and a callable `CandidateMap -> float` returning a finite
  score. The grid and hallway range are processing input; `config` controls search.
- `CandidateSearchTarget(room_id, room_type=None)` uses a non-empty string ID.
- `CandidateSearchConfig(trial_count=500, max_grid_node_count=250_000,
  random_seed=None)`: counts are positive integers; max nodes is at least 9; the
  prepared node count may not exceed it; at least one interior node is needed.
- Exactly `hallway_room_count_range.maximum` targets must be hallways, and the grid
  must have enough interior nodes for all non-hallways plus that maximum. The shared
  range always has `minimum=1`.

## Configuration

`trial_count` controls completed evaluations; larger values increase exploration and
runtime. `random_seed` makes Optuna sampling repeatable for a fixed environment.
`max_grid_node_count` is a safety cap, not a grid generator. `build_candidate_grid`
only validates and returns the supplied resolved grid.

## Recommended values

Use `build_candidate_search_targets(spec)` to avoid identity mistakes. Set a seed in
tests. No universal trial count exists; increase it only after measuring evaluator
cost and search quality. The only implementation-backed grid-node minimum is 9.

## Outputs

The production result has `candidate`, finite `score`, `completed_trials`, plus
convenience `points`, `grid`, and `hallway_room_count`. DEBUG details add the grid,
Optuna trial count, and completed count. Incremental calls return
`CandidateSuggestion` and `CandidateTrialResult` with trial number/candidate/score.

## Warnings / diagnostics

Candidate Search has no structured warning collection. In `DEBUG`, `CandidateSearchDetails` exposes the exact resolved grid, total Optuna trial count, and completed trial count. Invalid session state raises `CandidateSearchStateError`, and exceptions raised by the consumer-supplied evaluator propagate instead of being converted into warnings.

## Errors / failure conditions

Constructors raise `TypeError`/`ValueError` for bad types, duplicate targets,
impossible capacity, edge/misaligned points, or non-finite scores. Session misuse
(asking with a pending trial, recording the wrong/already recorded suggestion, or
requesting a best result too early) raises `CandidateSearchStateError`. Evaluator
exceptions propagate.

## Usage example

```python
from fpg_core.candidate_search import (
    CandidateSearchConfig, CandidateSearchInput,
    build_candidate_search_targets, search_candidates,
)

execution = search_candidates(CandidateSearchInput(
    targets=build_candidate_search_targets(example_specification),
    grid=example_grid,
    hallway_room_count_range=example_hallway_range,
    config=CandidateSearchConfig(
        max_grid_node_count=250_000,
        trial_count=100,
        random_seed=42,
    ),
    evaluator=lambda candidate: -sum(point.x + point.y for point in candidate.points),
))
best_candidate = execution.result.candidate
```

## Important behavioral notes

One point represents one room, including hallways. Points are sampled without
replacement and never use the outer grid rows. Higher evaluator scores win. Only one
incremental suggestion may be pending.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.candidate_search`. Its current exported symbols are:

- `CandidateEvaluator`
- `CandidateSearchConfig`
- `CandidateSearchDetails`
- `CandidateSearchError`
- `CandidateSearchInput`
- `CandidateSearchResult`
- `CandidateSearchSession`
- `CandidateSearchSpace`
- `CandidateSearchStateError`
- `CandidateSearchTarget`
- `CandidateSuggestion`
- `CandidateTrialResult`
- `HallwayRoomCountRange`
- `ResolvedCandidateGrid`
- `build_candidate_grid`
- `build_candidate_search_targets`
- `search_candidates`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
