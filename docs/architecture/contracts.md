# Contracts and package boundaries

## Ownership

| Layer | Canonical source | Purpose |
| --- | --- | --- |
| Cross-feature types | `src/fpg_core/domain/` and its `__init__.py` | Land, geometry, candidate, floor-plan, opening, execution models |
| Feature entry points | `src/fpg_core/<feature>/__init__.py` and `api.py` | Supported operations and types |
| Feature policy | `src/fpg_core/<feature>/config.py` or `profiles.py` | Reusable settings, constraints, presets |
| Processing inputs/results | Feature `contracts.py` / typed public models | Request-independent computational hand-offs |
| Aggregate validation | `src/fpg_core/config.py` | `FpgCoreConfig`, schema version `2`, cross-feature validation |
| Public symbol inventory | `docs/_generated/public_api_manifest.json` | Generated index of `__all__`, not a replacement for code |

Do not redefine common `RoomType`, room IDs, `FloorPlan`, `FloorPlanGenerationSpec`, `CandidateMap`, `ResolvedCandidateGrid`, geometry, or execution types within a feature. Do not import sibling feature implementation modules. The root `fpg_core` package exposes selected configuration conveniences lazily; individual feature packages expose their own supported entry points.

## Units and coordinate ownership

Current convention: **10 project units = 1 metre** (1 unit = 10 cm). Geometry may use floats; preprocessing's chosen floor extents use whole project units and a centered candidate grid may start at half units. Solver/opening CP-SAT integer coordinate scales are internal **conversion settings**, not a new consumer unit system. Make every conversion explicit.

`FloorPlanGenerationSpec` owns the required rooms and relations for a solve. Room IDs, enum values, and relation strengths are identity/semantic contracts across stages. Changing any public type or default needs a compatibility review and a changelog entry.

## Return conventions and failure handling

Most entry points return `FeatureExecution(result, details, metadata)`. `details` is `None` in `ExecutionMode.PRODUCTION` and feature-specific in `DEBUG`; `metadata` supplies mode and duration. In particular, solver, post-processing, and openings have structured statuses in their **result** rather than guaranteeing a successful floor plan on every call. Validate status before reading optional plans.

**Exception:** `candidate_scoring.evaluate_candidate()` returns `ScoringResult` directly, with evaluator results/findings and `total_score`; it does **not** return `FeatureExecution`. This is the current API, even though it accepts `mode` for debug evaluator detail.

Candidate search returns a `CandidateMap` plus score/trial metadata inside its `FeatureExecution`. Its evaluator callback must produce a numeric score. The generation specification passed to solver must match the selected active hallway IDs.

## Compatibility rules

- Separate request-specific processing data from reusable feature configuration.
- Distinguish hard constraints (feasibility) from scoring/soft objectives (preference).
- Preserve public enums, statuses, exceptions, identity fields, and package exports unless deliberately breaking the contract.
- Keep Optuna, OR-Tools, Shapely, and other implementation details out of shared domain contracts unless intentionally public.
- For an export change, run `python tools/generate_public_api_manifest.py` and commit the generated JSON; the check mode must then pass.
- Consumer wiring, HTTP, persistence, progress transport, jobs, and deployment belong outside this package.
