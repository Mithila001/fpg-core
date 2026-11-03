# Changelog

## Unreleased

### Repository and Lab integration

- Added FPG Lab under `fpg-lab/` as an experimental consumer of this checkout's
  public Core APIs. Core distributions and development dependencies exclude Lab.
- Use root `.venv` for Core and `fpg-lab/.venv` for Lab. Lab setup derives Core
  from the parent directory; `CorePath` / `--core-path` overrides are removed.
- Lab accepts its current profile schema 6 only (distinct from Core aggregate
  schema 2). Legacy upgrades and the embedded older profile were removed. Stop
  Lab, review `.env`, reset with the explicit fresh setup option, and reseed to
  replace old local records. No sibling database is imported.
- The tracked Lab seed is the single starter source. The export command validates
  and normalizes it; it does not automatically regenerate policy from Core defaults.
- Retired root manual experiment runners/viewers. Use Core public Markdown examples
  and focused flow tests, or Lab UI/headless experiments for research.
- Consolidated public documentation into `API_GUIDE.md` and per-feature documents;
  public export/contract checks now target those documents. Replaced the monolithic
  reference, duplicate documentation policy and duplicate testing guide.
- Added scoped agent instructions, P01 family guidance, repository-local skills,
  distribution isolation checks and a separate impact-scoped Lab workflow.
- Core version and public algorithms/contracts are unchanged by this integration.

### Documentation

- Consolidated agent-oriented architecture and feature guidance under `docs/`, with root `AGENTS.md` as the concise task router.
- Added mandatory documentation update policy, verification guidance, a personal scratch area, and a standard-library documentation checker.
- Replaced duplicated feature-local README manuals and repaired links to missing documentation.

### Breaking

- Floor-plan solver, scoring, post-processing, and openings entry points now return mode-aware `FeatureExecution` values; normal results are available through `execution.result`.
- Solver and opening diagnostics, scoring evaluator/group analysis, and post-processing execution records are now DEBUG-only `execution.details`.
- `score_floor_plan` now accepts one `FloorPlanScoringInput` instead of separate floor plan, specification, and profile arguments.

### Added

- Shared `ExecutionMode` support and execution metadata for all four final floor-plan features.
- Typed execution aliases and feature-specific DEBUG details contracts.
- Server integration guidance for the new execution contracts.

## 0.2.0 - 2026-08-04

### Breaking

- Replaced fixed Candidate Search coordinate bounds and `grid_resolution` with `FloorSpec`, `long_axis_node_count`, grid-node safety limits, and bounded internal sampling attempts.
- Candidate Search evaluators now receive `CandidateMap` instead of `tuple[CandidatePoint, ...]`.
- Candidate Search suggestion/result contracts now store `candidate: CandidateMap`; `.points` and `.grid` remain convenience properties.
- Candidate Circulation input/result now store `candidate: CandidateMap`.
- Removed request-specific `CirculationGrid` from `CandidateCirculationConfig`.
- Candidate Scoring now requires `CandidateMap`.
- Removed `CirculationGrid` from `RelationshipQualityConfig`.
- Renamed `ZoneSuitabilityConfig.grid_size` to `zone_count_per_axis`.
- Renamed Spatial Distribution setting `grid_size` to `sample_count_per_axis`.
- Added required preprocessing setting `max_aspect_residual_units`.
- Package configuration schema version is now `2`.

### Added

- `ResolvedCandidateGrid` and `CandidateMap` shared domain contracts.
- Exact-boundary adaptive grid construction using balanced integer axis positions.
- Internal Candidate Search rejection of overlapping hint points.
- Candidate Search DEBUG details for resolved grid and internal Optuna rejection counts.
- Whole-project-unit floor-limit normalization and expanded floor-selection diagnostics.

### Changed

- Preprocessing floors request maximum dimensions before floor selection.
- Preprocessing selects integer floor dimensions within the configured aspect residual.
- Candidate Circulation and Relationship Quality route over the exact Candidate Search grid.
- Relationship Quality no longer reconstructs a separate fixed-scale grid.
- Default candidate-scoring registry now registers Relationship Quality.

### Compatibility

- `CandidateSuggestion.points`, `CandidateSearchResult.points`, and equivalent Circulation result properties remain read-only conveniences.
- `ZoneSuitabilityConfig.grid_size` and scoring DEBUG detail `grid_size` remain read-only aliases only; constructors must use the new names.
- Legacy `fpg_core.domain.CirculationGrid` remains exported for unrelated external code, but is no longer accepted by the migrated Candidate Circulation or Relationship Quality configurations.
