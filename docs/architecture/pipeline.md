# Floor-plan generation pipeline

This is an **integration flow**, not one package-level `generate_all()` function. Consumers coordinate the independently callable features. The [consumer guide](../API_GUIDE.md) supplies package-only examples; focused integration checks live in `tests/flows/`.

```text
land boundary + entry road + setback policy
  -> buildable_land: validate, normalize, classify sides, apply setbacks
  -> usable_land: find road-aligned inscribed rectangle
  -> floor_plan_preprocessing: select floor, normalize rooms/relations,
       prepare exact candidate grid and potential hallway rooms
  -> candidate_search (Optuna/TPE; multiple trials)
       trial: choose active hallway count and unique interior hint nodes
          -> candidate_circulation: weighted orthogonal routes,
             hallway classification/removal/consolidation
          -> candidate_scoring: assess the cleaned candidate
          -> return numeric score to Optuna
       select highest-scoring raw CandidateMap
  -> run circulation + scoring for selected candidate (diagnostics/inspection)
  -> prepared.generation_spec_for_candidate(cleaned_candidate)
  -> floor_plan_solver: initial CP-SAT placement
  -> floor_plan_solver: refinement A, then refinement B (existing-plan seeds)
  -> floor_plan_post_processing: geometry transformations
  -> floor_plan_openings: generate doors and windows
  -> floor_plan_scoring: final quality and critical checks
  -> consumer-owned validation, storage, presentation
```

## Crucial hand-offs

- `BuildableLandResult.normalized_land` supplies the road orientation needed by usable-land search; `buildable_land` supplies the allowed polygon.
- Preprocessing creates the *one* exact `ResolvedCandidateGrid`. Search, circulation, and relationship scoring must use it, not reconstruct their own coordinate grid.
- Candidate Search owns trial generation, **not** the scoring logic. Its evaluator callback is supplied by the caller; a consumer can call circulation and candidate scoring **inside every trial**.
- Search returns its selected **raw** hint map. Selected-candidate circulation and scoring run again to recover the cleaned map/diagnostics. Use `generation_spec_for_candidate()` on that cleaned map before the solver: the preprocessing template contains every *potential* hallway, not only those actually used.
- The solver cannot delete supplied rooms. Hallway-count reduction occurs before solving; compatible hallway geometries can be merged later during post-processing.
- Post-processing is intentionally before opening generation: moving geometry after placing openings would invalidate door/window positions.
- Final floor-plan scoring is independent of candidate scoring. Final validation and delivery remain consumer responsibilities.

## Boundaries and scope

Single-storey, 2D, residential rooms and convex parcels are the current targets. Architectural plausibility and configured local setback rules are not a guarantee of regulatory approval. Keep search/solver limits configurable and bounded, hard rules distinct from preferences, and external application concerns out of the core.

## Consumer policy consistency

A hard preprocessing room relation must be realizable under the consumer's opening policy. For example, a required kitchen/dining adjacency needs a compatible allowed opening pair if the consumer expects a connecting door. Keep these application-owned policies aligned; generation success does not replace final geometry and accessibility checks.
