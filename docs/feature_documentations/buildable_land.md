# Buildable Land

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Validates and normalizes one convex parcel with one entry-road attachment, classifies
its sides relative to that road, applies setbacks, and returns the legal/build-policy
envelope. Processing data and reusable policy are separated in `BuildableLandInput`.

## Public API

```python
calculate_buildable_land(
    buildable_input: BuildableLandInput,
    *, mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FeatureExecution[BuildableLandResult, BuildableLandDetails]
```

Import `BuildableLandInput`, `BuildableLandConfig`, result/detail contracts,
`BuildableLandError`, and the operation from `fpg_core.buildable_land`. Shared land
contracts and `ExecutionMode` come from `fpg_core.domain`.

## Inputs

- `BuildableSpaceRequestData.land_boundary: Polygon` is an ordered boundary of
  `Point(x, y)` values. A repeated closing point is accepted and removed. Effective
  point count must fall within `ValidationLimits`; points must be unique, finite,
  within `maximum_absolute_coordinate`, non-collinear at every intermediate vertex,
  non-self-intersecting, positive-area, and convex. Clockwise input is accepted.
- `roads: tuple[RoadAttachment, ...]` must contain exactly one item. Its
  `boundary_edge_index` refers to the original boundary edge; its `road_type` must
  exist in the active profile's adjustments. Current `RoadRole` supports
  `MAIN_ENTRY`.
- `BuildableLandInput(request, config)` requires exact
  `BuildableSpaceRequestData` and `BuildableLandConfig` instances.
- `SetbackProfile` contains `name`, `status`, `description`, calculation mode,
  `base_setbacks: Mapping[LandSide, int]`, and nested road adjustments. Current
  calculation mode is `BASE_PLUS_ROAD_ADJUSTMENT`. Setbacks are lengths in project
  units.

## Configuration

- `BuildableLandConfig(setback_profile, validation_limits)` contains only reusable
  behavior controls. `ValidationLimits.minimum_vertex_count`, `maximum_vertex_count`, and
  `maximum_absolute_coordinate` control accepted parcel complexity and coordinate
  bounds.
- `base_setbacks` sets the inward distance for front/back/left/right edges.
- `road_adjustments[road_type][side]` is added only on the attached road edge.

## Recommended values

The implementation provides no universal setback or validation profile. Use values
from the consumer's jurisdiction/reference dataset; all four `LandSide` values and
each accepted `RoadType` need mapping entries.

## Outputs

The return envelope always contains `BuildableLandResult(buildable_land,
normalized_land)`. `NormalizedLand` has a counter-clockwise boundary, normalized
`LandEdge`s retaining `source_edge_index`, and `main_entry_road`. `BuildableLand`
has `boundary`, `area`, and one `EdgeSetback` per source edge. DEBUG adds
`BuildableLandDetails(edge_classifications)`; PRODUCTION sets `details=None`.

## Warnings / diagnostics

This feature has no separate production warning collection. Invalid or unusable geometry is reported by raised exceptions rather than warning strings. In `DEBUG`, `execution.details.edge_classifications` exposes the road-relative edge classification used to calculate setbacks; `PRODUCTION` omits these details.

## Errors / failure conditions

Invalid contract types raise `TypeError`/`ValueError`. Geometry/domain failures raise
`BuildableLandError`; inspect `.code: BuildableSpaceErrorCode` and
`.message`. Codes cover invalid/non-convex/self-intersecting boundaries, bad or
unsupported road attachments, setbacks that eliminate the parcel, and final geometry
failure. Road edge indexes must be in `0..vertex_count-1`.

## Usage example

```python
from fpg_core.buildable_land import (
    BuildableLandConfig, BuildableLandInput, calculate_buildable_land,
)
from fpg_core.domain import (
    BuildableSpaceRequestData, ExecutionMode, LandSide, Point, Polygon, RoadAttachment,
    RoadRole, RoadType, SetbackCalculationMode, SetbackProfile,
    ValidationLimits,
)

profile = SetbackProfile(
    name="residential", status="active", description="Local residential rules",
    calculation_mode=SetbackCalculationMode.BASE_PLUS_ROAD_ADJUSTMENT,
    base_setbacks={side: 5 for side in LandSide},
    road_adjustments={RoadType.MAIN_ROAD: {side: 0 for side in LandSide}},
)
config = BuildableLandConfig(
    setback_profile=profile,
    validation_limits=ValidationLimits(4, 12, 100_000),
)
request = BuildableSpaceRequestData(
    land_boundary=Polygon((Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))),
    roads=(RoadAttachment(0, RoadRole.MAIN_ENTRY, RoadType.MAIN_ROAD),),
)
execution = calculate_buildable_land(
    BuildableLandInput(request=request, config=config),
    mode=ExecutionMode.DEBUG,
)
buildable_land = execution.result.buildable_land
normalized_land = execution.result.normalized_land
```

## Important behavioral notes

Inputs are not mutated. The normalized boundary may reverse orientation while source
edge identity remains stable. Side meaning is road-relative, not a global compass
direction. The operation is deterministic for fixed input/configuration.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.buildable_land`. Its current exported symbols are:

- `BuildableLandConfig`
- `BuildableLandDetails`
- `BuildableLandError`
- `BuildableLandInput`
- `BuildableLandResult`
- `calculate_buildable_land`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
