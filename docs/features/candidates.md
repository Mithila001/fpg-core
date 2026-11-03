# Candidate search, circulation, and scoring

These are **three independent features** composed by the caller. In the current full flow, candidate circulation and candidate scoring run **inside every Optuna trial**, and their numeric score is returned to the search evaluator.

## Candidate Search (`fpg_core.candidate_search`)

```python
search_input = CandidateSearchInput(
    targets=build_candidate_search_targets(prepared.generation_spec),
    grid=prepared.candidate_grid,
    hallway_room_count_range=prepared.hallway_room_count_range,
    evaluator=score_one_trial,
    config=CandidateSearchConfig(trial_count=500, random_seed=42),
)
search_execution = search_candidates(search_input)
```

- Optuna/TPE chooses one global hallway count per trial and one **unique interior grid node** for each active room; no overlapping or outer-edge hint points.
- Inputs must have unique room IDs, exactly the configured maximum of hallway targets, a grid under `max_grid_node_count` (default `250_000`), and enough interior nodes.
- `CandidateSearchConfig.trial_count` defaults to `500`; `random_seed` controls sampler reproducibility, subject to compatible inputs/environment.
- Returns the best **raw** candidate, its score, and completed-trial count via `FeatureExecution`. It does not itself know how to route or score.
- `CandidateSearchSession` exposes `ask_next_trial()` / `record_score()` when incremental orchestration is needed; only one trial may be pending at once.

## Candidate Circulation (`fpg_core.candidate_circulation`)

`refine_candidate_circulation(CandidateCirculationInput(candidate=..., config=...), mode=...)` uses the candidate's **existing** grid to route configured room relationships along orthogonal neighbors. `CirculationRouteRule` may specify allowed and **required** intermediate room types; a required transit room must actually occur between endpoints. Traffic classification is recalculated across bounded routing passes (`max_routing_passes`, default `3`).

Unused hallway hints are removed first. If `HallwayConsolidationConfig.enabled`, nearby retained hallway hints can be removed only when all required routes still exist and cost growth is within `max_route_cost_increase_ratio` (default `0.15` from the post-unused-removal baseline). `minimum_separation_grid_steps` defaults to `2.0`. The returned cleaned `CandidateMap` retains the same grid and includes hallway classifications. `DEBUG` adds routes, classifications, removal reasons, and consolidation attempts.

## Candidate Scoring (`fpg_core.candidate_scoring`)

`evaluate_candidate(CandidateScoringInput(specification=..., candidate=..., hallway_classifications=...), registry=..., config=..., mode=...)` returns **`ScoringResult` directly**, not `FeatureExecution`. Its `total_score` is the trial evaluator's numeric feedback. It can report critical failures, structured findings, and evaluator details.

The default registry contains Zone Suitability, Exterior Clearance, Relationship Quality, and Spatial Distribution. **The default config enables Zone Suitability, Exterior Clearance, and Spatial Distribution only**; Relationship Quality is registered but must be explicitly configured if wanted. Relationship Quality routes over `candidate.grid`; Zone Suitability uses a relative overlay (`zone_count_per_axis`); Spatial Distribution uses measurement density (`sample_count_per_axis`). Do not add separate fixed-scale route grids.

## Integration evaluator

```python
def score_one_trial(raw_candidate):
    circulation = refine_candidate_circulation(
        CandidateCirculationInput(candidate=raw_candidate, config=circulation_config)
    )
    cleaned = circulation.result
    active_spec = prepared.generation_spec_for_candidate(cleaned.candidate)
    result = evaluate_candidate(
        CandidateScoringInput(
            specification=active_spec,
            candidate=cleaned.candidate,
            hallway_classifications=cleaned.hallway_classifications,
        ),
        registry=candidate_registry,
        config=candidate_scoring_config,
    )
    return result.total_score
```

The experiment handles per-trial evaluation failures as rejected/zero-scored trials; that is an **orchestration choice**, not a promise of the feature APIs. After search, rerun circulation for the selected raw candidate to obtain the cleaned candidate for solver preparation.

Sources: `candidate_search/optimizer.py`, `candidate_circulation/pipeline.py`, `candidate_circulation/consolidation.py`, `candidate_scoring/defaults.py`, `candidate_scoring/manager.py`.
