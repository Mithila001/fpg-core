# Candidate Search

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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


## Warnings / diagnostics

Candidate Search has no structured warning collection. In `DEBUG`, `CandidateSearchDetails` exposes the exact resolved grid, total Optuna trial count, and completed trial count. Invalid session state raises `CandidateSearchStateError`, and exceptions raised by the consumer-supplied evaluator propagate instead of being converted into warnings.

## Public Export Inventory

### `fpg_core.candidate_search` exports (17)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `CandidateEvaluator` | constant/type alias | `_CallableGenericAlias instance` | Documented in the corresponding feature/shared section. |
| `CandidateSearchConfig` | dataclass/contract | `(trial_count: 'int' = 500, max_grid_node_count: 'int' = 250000, random_seed: 'int \| None' = None) -> None` | Reusable controls for how Candidate Search performs a search. |
| `CandidateSearchDetails` | dataclass/contract | `(grid: 'ResolvedCandidateGrid', optuna_trial_count: 'int', completed_trial_count: 'int') -> None` | DEBUG-only grid and Optuna trial information. |
| `CandidateSearchError` | exception | `constructor has no separately inspectable signature` | Base exception for candidate-search execution failures. |
| `CandidateSearchInput` | dataclass/contract | `(targets: 'tuple[CandidateSearchTarget, ...]', grid: 'ResolvedCandidateGrid', hallway_room_count_range: 'HallwayRoomCountRange', evaluator: 'CandidateEvaluator', config: 'CandidateSearchConfig') -> None` | Processing input and execution dependency for one Candidate Search. |
| `CandidateSearchResult` | dataclass/contract | `(candidate: 'CandidateMap', score: 'float', completed_trials: 'int') -> None` | Best candidate arrangement discovered by a completed search. |
| `CandidateSearchSession` | class/interface/registry | `(search_input: 'CandidateSearchInput') -> 'None'` | Incremental Optuna-backed uniform-grid candidate search. |
| `CandidateSearchSpace` | dataclass/contract | `(origin_x: 'Coordinate', origin_y: 'Coordinate', width: 'int', length: 'int', grid_spacing: 'int') -> None` | Centered, divisible Candidate Search rectangle in floor coordinates. |
| `CandidateSearchStateError` | exception | `constructor has no separately inspectable signature` | Raised when session methods are called in an invalid order or state. |
| `CandidateSearchTarget` | dataclass/contract | `(room_id: 'RoomId', room_type: 'RoomType \| None' = None) -> None` | Identifies one concrete room that may receive one candidate point. |
| `CandidateSuggestion` | dataclass/contract | `(trial_number: 'int', candidate: 'CandidateMap') -> None` | One valid, non-overlapping candidate produced by an Optuna trial. |
| `CandidateTrialResult` | dataclass/contract | `(trial_number: 'int', candidate: 'CandidateMap', score: 'float', completed_trials: 'int') -> None` | Candidate and score produced by one completed search trial. |
| `HallwayRoomCountRange` | dataclass/contract | `(maximum: 'int', minimum: 'int' = 1) -> None` | Allowed number of distinct hallway rooms in one candidate trial. |
| `ResolvedCandidateGrid` | dataclass/contract | `(x_positions: 'tuple[Coordinate, ...]', y_positions: 'tuple[Coordinate, ...]') -> None` | Exact uniform candidate-location and orthogonal-routing grid. |
| `build_candidate_grid` | function | `build_candidate_grid(*, grid: 'ResolvedCandidateGrid', max_grid_node_count: 'int') -> 'ResolvedCandidateGrid'` | Validate and return the exact grid prepared by preprocessing. |
| `build_candidate_search_targets` | function | `build_candidate_search_targets(specification: fpg_core.domain.floor_plan_spec.FloorPlanGenerationSpec) -> tuple[fpg_core.candidate_search.models.CandidateSearchTarget, ...]` | Create one concrete Candidate Search target for every prepared room. |
| `search_candidates` | function | `search_candidates(search_input: 'CandidateSearchInput', *, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FeatureExecution[CandidateSearchResult, CandidateSearchDetails]'` | Run the complete uniform-grid candidate search. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
