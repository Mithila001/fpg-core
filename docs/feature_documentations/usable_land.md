# Usable Land

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Finds the highest-ranked integer-coordinate, road-aligned rectangle inside a
`BuildableLand` polygon that satisfies floor minimum dimensions. Use it when a
consumer needs a simple rectangular floor envelope from an already calculated
buildable polygon.

## Public API

```python
from fpg_core.usable_land import UsableLandError, find_usable_land

find_usable_land(
    usable_input: UsableLandInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[UsableLand, UsableLandDetails]
```

## Inputs

- `UsableLandInput(buildable_land, land, config)` requires a `BuildableLand`, its
  corresponding `NormalizedLand`, and `UsableLandConfig`.
- `UsableLandConfig(minimum_width, minimum_length, search_resolution,
  maximum_sweep_lines)` requires positive integers. Distances use project units.
  `UsableLandConfig.from_constraints(UsableLandConstraints(minimum_width,
  minimum_length, search_resolution, maximum_sweep_lines))` is the supported
  compatibility conversion. Width is defined
  relative to the selected road alignment; both parallel and perpendicular
  alignments are considered.

## Configuration

- Minimum width/length reject smaller rectangles.
- `search_resolution` is the vertical search step in road-aligned coordinates;
  smaller values inspect more positions and may find a larger rectangle.
- `maximum_sweep_lines` caps synchronous search work; exceeding it is a returned
  error rather than partial output.

## Recommended values

No universal dimensions are built in. Use project minimum floor dimensions. Use the
coarsest resolution acceptable for the project's coordinate precision and size
`maximum_sweep_lines` above the expected road-aligned height divided by resolution.

## Outputs

The result is `UsableLand` with world-coordinate `boundary`, integer `width`,
`length`, and `area`, alignment (`PARALLEL_TO_ENTRY_ROAD` or
`PERPENDICULAR_TO_ENTRY_ROAD`), and original `entry_road_edge_index`. DEBUG adds
`UsableLandDetails`: evaluated pair count, local buildable/selected boundaries, and
the road-aligned transform origin and axes. PRODUCTION sets `details=None`.

## Warnings / diagnostics

This feature has no separate warning channel. Search-limit and no-solution cases are represented by `UsableLandError`, not partial output. In `DEBUG`, `UsableLandDetails` exposes evaluated-pair counts, road-aligned local geometry, the selected local rectangle, and transform axes/origin for diagnosis.

## Errors / failure conditions

Invalid input/config types raise `TypeError`/`ValueError`. `UsableLandError` exposes
`.code`, `.message`, and `.details`. Handle
`NO_USABLE_LAND_FOUND`, `SEARCH_LIMIT_EXCEEDED`, and
`USABLE_LAND_CALCULATION_FAILED`.

## Usage example

```python
from fpg_core.domain import ExecutionMode
from fpg_core.usable_land import UsableLandConfig, UsableLandInput, find_usable_land

execution = find_usable_land(UsableLandInput(
    buildable_land=buildable_land,
    land=normalized_land,
    config=UsableLandConfig(30, 40, 1, 1000),
), mode=ExecutionMode.DEBUG)
usable = execution.result
```

## Important behavioral notes

The call is deterministic and non-mutating. Ranking favors area, then the smaller
dimension, then parallel-to-road alignment, followed by stable coordinate tie-breaks.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.usable_land`. Its current exported symbols are:

- `UsableLandConfig`
- `UsableLandDetails`
- `UsableLandError`
- `UsableLandInput`
- `find_usable_land`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
