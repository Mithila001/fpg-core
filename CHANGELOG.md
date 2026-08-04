# Changelog

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
