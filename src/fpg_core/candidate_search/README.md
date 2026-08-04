# Candidate Search

Candidate Search builds one adaptive grid from the preprocessed integer `FloorSpec`, then uses Optuna to select grid node indexes.

```python
settings = CandidateSearchSettings(
    floor=spec.floor,
    long_axis_node_count=20,
    max_grid_node_count=250_000,
    max_internal_sampling_attempts=100,
    trial_count=500,
    random_seed=42,
)

search_input = CandidateSearchInput(
    targets=targets,
    settings=settings,
    evaluator=lambda candidate: score(candidate),
)

execution = search_candidates(search_input, mode=ExecutionMode.DEBUG)
candidate = execution.result.candidate
```

Returned candidates contain:

- `candidate.grid`: exact `ResolvedCandidateGrid`.
- `candidate.points`: unique points aligned to that grid.

Overlapping internal Optuna samples are failed and retried before the evaluator is called. DEBUG details expose rejection and trial counts.
