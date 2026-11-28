# Changelog

- Breaking: exposure constraints require explicit `rules`. Replace old named exposure keys with `exterior_wall_exposure` and replace saved Lab profiles with current configuration; `living_room_front` remains conditional and requires explicit rules. Old snapshots are not migrated.

- Breaking: solver defaults use room-facing clearance; replace saved profiles using `front_anchor` and veranda boundary placement with the current exposure rules. Garage placement now uses room clearance.

## Unreleased

- Breaking: candidate scoring uses shared room footprints, spatial occupancy,
  physical proximity, footprint clearance, and group compactness. Supply the full
  preprocessed specification to scoring. Lab schema 9/revision 12 replaces old
  grid-step scoring settings; migrate saved profiles and review the initial physical
  distances. Historical snapshots are preserved.
- Lab candidate-derived solver hints now identify coordinates as room centers;
  direct Core callers may opt in with `position_reference="center"`. Existing
  lower-left hints and refinement seeds retain their previous interpretation.
- Breaking: assigned-relation circulation rules require prepared room relations;
  the Lab adapter now requires `prepared` when running circulation. Lab profiles
  require revision 11/schema 8 migration. Candidate Search observations can be
  marked unusable, and unusable observations cannot become best results.
- Added per-rule global transit control and an optional route-step distance policy
  applied once to circulation quality. Lab's attached-bathroom starter rule uses
  the prepared one-to-one pairing and a strong experimental two-step penalty.
- Breaking: Candidate Circulation rejects hint points on the outer grid boundary and
  routes exclusively through interior nodes. Consumers supplying manual hints must
  move them to interior nodes; previously reachable routes may now be blocked.

- Breaking: candidate scoring replaces relationship quality with circulation quality
  and functional group purity, uses equal weights, and excludes not-applicable
  evaluators. Pass the final circulation result into scoring. Migrate Lab profiles
  to revision 10; historical snapshots are not recalculated.

- Breaking: candidate evaluator errors now raise `EvaluatorExecutionError` instead
  of being omitted from the score. Consumers must fail the pending search trial.

- Breaking: non-empty opening-generation plans now require a full-width secondary
  entrance connected to the main entrance. Ensure an eligible kitchen or hallway
  has an exterior wall long enough for the configured width and clearances.
  Exterior exposure is determined from the room footprint, excluding enclosed voids.
- Breaking: windows use room-specific policies, including bathroom defaults, and
  normal room connections and duplicate room pairs are limited. Migrate Lab
  profiles to revision 9 and review their opening policies before generating plans.

- Breaking: interior door widths and corner clearances now use `interior_doors`
  policies, rather than exterior dimensions and geometry clearance. Configure the
  default and room overrides explicitly; Lab revision 8 carries existing standard
  dimensions forward and adds bathroom overrides. Historical snapshots are unchanged.

- Breaking behavior change: opening generation defaults to a 5-unit corner
  clearance instead of zero. Set an explicit clearance to retain a custom policy.
  Lab revision 7 migrates zero-clearance profiles to 0.5 metres in their own
  units, leaving nonzero settings and historical snapshots intact.

- Re-enabled living room balance and bedroom quality as default functional
  scoring evaluators. Lab revision 6 enables both in saved profiles, preserving
  existing custom settings and historical run snapshots. Final score weighting
  changes when these evaluators are applicable.

- Breaking: removed `room_size_hierarchy` and the `room_size_relations.rules`
  setting. Migrate saved solver profiles to `cross_type_rules` and
  `same_type_rules`, or use the current seed. Empty settings now include a
  bedroom spread preference. Historical snapshots are not modified.

- Added the general `front_wall_setback` hard constraint to built-in solver
  profiles and the Lab baseline, with conditional room-type rules and
  geometry-repair protection. Revision 5 adds missing rules to saved Lab
  profiles without changing the database schema or historical snapshots.
  The tighter default placement requirements can affect feasibility.

- Breaking: wall extension now requires the final solver configuration and room
  specification for opportunistic repair; its old selection fields have been
  replaced. The default processor order changed and veranda adjustment is removed
  from the default registry. Migrate Lab profiles with revision 4 maintenance;
  downstream consumers including `fpg-server` must update their wall-extension
  configuration mapping and pass the actual final solver configuration. Historical
  run snapshots retain their original format.

- Breaking. Room Relationship Quality replaces the shared-wall adjacency gate
  and the former kitchen/dining evaluator. Replace obsolete scoring rules with
  `room_relationship_quality` and use the [Lab profile migration](../../fpg-lab/docs/DEVELOPMENT.md#revision-3-scoring-profile-migration)
  for existing databases.

- Breaking: `inward_recess` replaces `maximum_length` with
  `max_depth_to_width_ratio` (default 1.0) and `max_recess_levels` (default 1).
  Update Python settings and saved Lab profiles or use the current seed.
  DEBUG payloads and finding codes now describe sweep regions and sections.
  Review custom tools that consume the older metrics or payload.

- Breaking: each solver soft constraint returns one 0?100 penalty through `build_penalty`. Profiles supply weights from 0 to 10, with built-in defaults of 1. Replace saved solver profiles and retune custom weights. Debug objective values use weighted points.

- Breaking: back exposure no longer requires boundary contact, and garage side exposure no longer restricts space beyond its own wall projection. Review saved solver profiles that relied on the previous geometry.


- Hallways now require at least 10 project units; default door width is 10.
  Custom profiles below the hallway minimum must be updated.


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

- Lab P01B now accepts saved cleaned-candidate presets and iteration controls;
  its former manual-hint input and A/B/openings workflow are retired. Export a
  new debug P01A trial and save it as a P01B preset to run the replacement.
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
