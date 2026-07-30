# Floor Plan Openings

`fpg_core.floor_plan_openings` places doors and windows on a finalized
`fpg_core.types.FloorPlan`. It is an independent algorithm stage intended to run
after floor-plan post-processing and before floor-plan scoring.

The package is not connected to the current application manager yet. It has no
dependency on API routes, persistence, job management, legacy opening payloads,
or the floor-plan solver's internal model.

## Contract

The input plan must contain canonical, grid-aligned, rectilinear room and floor
polygons, finalized standard rooms, unique room IDs, and no existing openings.
The input is never mutated. A successful result contains a deep-copied plan
whose geometry and metadata are unchanged and whose `openings` collection
contains the generated domain objects.

```python
from fpg_core.floor_plan_openings import (
    OpeningGenerationRequest,
    generate_openings,
)

result = generate_openings(OpeningGenerationRequest(floor_plan))
if result.solved:
    plan_with_openings = result.floor_plan
else:
    handle_failure(result.status, result.diagnostics)
```

Every opening uses `OpeningType` for its physical kind and `OpeningPurpose` for
its role. Interior openings reference two room IDs. Exterior doors and windows
reference one room ID; no synthetic `OUTSIDE` room is used.

## Shared solve

Analysis first nodes all room and floor edges into canonical physical walls.
Only room edges that overlap the floor boundary are exterior. Shared and
partially shared spans are discovered once and reused by every feature.

Interior doors, exterior doors, and windows then contribute optional placement
decisions to one CP-SAT model. The common model owns wall capacity, non-overlap,
window spacing, room door limits, the bounded lexicographic objective, solver
execution, and deterministic tie-breaking. Features do not run separate
solvers.

The default objective preserves the legacy priority order while allowing a
door to move along a wall so a lower-priority window can still fit. Because the
first clean version preserves legacy requiredness, every opening is optional.
Diagnostics distinguish openings with no geometric candidate from candidates
the shared model did not select.

## Configuration

`DEFAULT_OPENING_PROFILE` owns:

- numeric scale, tolerance, corner clearance, and window spacing;
- door/window widths and minimum shared-wall length;
- allowed room relationships, room door caps, eligible room types, and facade
  priorities;
- enabled features and constraints;
- objective tier order and deterministic CP-SAT settings.

Create a new immutable profile with `dataclasses.replace`; do not modify the
default profile or read global configuration from a feature.

## Adding a feature

Implement the `OpeningFeature` protocol with a unique `feature_id` and a
`build_demands` method. The method receives only prepared geometry and the
selected profile and returns typed demands with wall options. Register the
feature in an `OpeningFeatureRegistry` and enable its ID in a profile. Shared
placement constraints and extraction will then apply automatically.

A future feature that needs new cross-opening rules should add a cohesive
registered constraint rather than solving independently or editing another
feature's decisions.

## Tests

Run the package in isolation:

```text
python -m pytest test/algorithms/floor_plan_openings -q
```

The tests use small synthetic typed floor plans and require neither FastAPI nor
a database.

## Current limitations

- Existing-opening preservation and partial regeneration are unsupported.
- Only single-story axis-aligned rectilinear geometry is accepted.
- Door swings, structural analysis, accessibility, skylights, stairs, and
  construction detailing are outside this version.
- Exterior doors may shrink below the preferred width to preserve active legacy
  behavior; the result reports this explicitly.
- The module is not yet wired into the active runtime pipeline.
