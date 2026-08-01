# Candidate Search

Uses Optuna to explore room hint-point positions before deterministic floor-plan solving. Non-hallway rooms receive one point; hallway targets may receive a configured number of points.

## Guide

### Public API

The one-shot operation is exposed from `fpg_core.candidate_search.api`:

```python
from fpg_core.candidate_search import (
    CandidateSearchInput,
    CandidateSearchSettings,
    CandidateSearchTarget,
)
from fpg_core.candidate_search.api import search_candidates
from fpg_core.domain import ExecutionMode

search_input = CandidateSearchInput(
    targets=(CandidateSearchTarget("living"),),
    settings=CandidateSearchSettings(
        min_x=0,
        max_x=100,
        min_y=0,
        max_y=80,
        grid_resolution=1,
        trial_count=25,
        random_seed=7,
    ),
    evaluator=lambda points: 100.0,
)
execution = search_candidates(
    search_input,
    mode=ExecutionMode.PRODUCTION,
)
result = execution.result
```

Incremental orchestration remains available through `CandidateSearchSession`:

```python
from fpg_core.candidate_search.api import CandidateSearchSession

session = CandidateSearchSession(search_input)
suggestion = session.ask_next_trial()
trial_result = session.record_score(suggestion, score=82.5)
best = session.best_result()
```

Use `fail_pending_trial()` when external scoring or solving fails after a suggestion is created.

### Inputs

- `CandidateSearchTarget`: room ID and optional `RoomType`. Hallway type enables multiple hints.
- `CandidateSearchSettings`: bounds, grid resolution, trial count, optional random seed, and hallway hint-count range.
- `CandidateSearchInput`: targets, settings, and a callable returning a finite numeric score.
- `ExecutionMode`: optional keyword-only mode for `search_candidates()`. It defaults to `PRODUCTION`.

`PRODUCTION` and `DEBUG` currently execute the same search. Candidate-search-specific debug/R&D inputs and details have not been added yet.

### Outputs

`search_candidates()` returns `FeatureExecution[CandidateSearchResult, None]`:

- `result`: highest-scoring points, score, and completed-trial count.
- `details`: currently `None` in all execution modes.
- `metadata`: selected execution mode and total duration in seconds.

Incremental session methods continue to return their lifecycle contracts directly:

- `CandidateSuggestion`: one unscored trial.
- `CandidateTrialResult`: scored trial and completed-trial count.
- `CandidateSearchResult`: current highest-scoring completed result.

### Errors and Expected Behaviour

Data-contract construction raises `TypeError` or `ValueError` for invalid fields. Invalid session call order raises `CandidateSearchStateError`. Evaluator exceptions propagate after the pending Optuna trial is marked failed. Passing anything other than `ExecutionMode` as the one-shot mode raises `TypeError`.

A fixed random seed makes the Optuna sampler reproducible for the same environment and call sequence.

## AI Instructions

- Keep public operations in `api.py`; `optimizer.py` is internal.
- Do not couple search to candidate scoring or the solver. Accept scoring through the evaluator callback or incremental session API.
- Keep the one-shot operation wrapped in `FeatureExecution`.
- Do not invent candidate-search details until useful `DEBUG` data for diagnostics or R&D is deliberately designed.
- Update this README when trial lifecycle, point identity, hallway behaviour, settings, outputs, or execution modes change.
- Keep feature tests under `tests/candidate_search/test_end_to_end.py` unless extra tests are explicitly justified.
