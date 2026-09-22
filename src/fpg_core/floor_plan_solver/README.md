# Floor Plan Solver

Builds and solves a CP-SAT floor-plan model from request-specific generation data and an explicit reusable solver configuration.

## Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_solver.api import (
    FloorPlanSolveRequest,
    INITIAL_GENERATION_PROFILE,
    generate_floor_plan,
)

execution = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=generation_spec,
        candidate_hints=room_hints,
        config=INITIAL_GENERATION_PROFILE,
    ),
    mode=ExecutionMode.DEBUG,
)

floor_plan = execution.result.floor_plan
```

`FloorPlanSolver` is public when a caller needs to reuse a custom `ConstraintRegistry`.

## Inputs

`FloorPlanSolveRequest` keeps processing data separate from configuration:

```text
FloorPlanSolveRequest
├── specification        # processing input
├── candidate_hints      # processing input
├── existing_floor_plan  # processing input
└── config               # solver configuration
```

Processing input:

- `specification: FloorPlanGenerationSpec` describes the floor and every room that the solver must place.
- `candidate_hints: tuple[RoomPlacementHint, ...]` optionally provides candidate-search seed geometry.
- `existing_floor_plan: FloorPlan | None` optionally provides existing geometry for refinement configurations.

Configuration:

- `config: FloorPlanSolverConfig` controls how solving is performed.
- `config.hard_constraints` selects mandatory constraints and their settings.
- `config.soft_constraints` selects objective preferences, weights, and settings.
- `config.solver` controls OR-Tools runtime limits, workers, random seed, logging, presolve, and relative gap.
- `config.preparation` controls conversion into CP-SAT integer units.
- `config.seed` controls which optional processing input is used as seed geometry and how strongly it constrains the solve.

Built-in profiles `INITIAL_GENERATION_PROFILE`, `REFINEMENT_A_PROFILE`, and `REFINEMENT_B_PROFILE` are ready-made `FloorPlanSolverConfig` values. `GenerationProfile` remains a backward-compatible alias of `FloorPlanSolverConfig`.

`ExecutionMode.PRODUCTION` is the default. `ExecutionMode.DEBUG` enables solver diagnostics.

## Structural Rules That Are Always Active

These are model invariants rather than selectable constraints:

- Every room supplied in `FloorPlanGenerationSpec.rooms` is present in the result. The solver currently cannot remove a supplied hallway or any other supplied room.
- Every room must stay inside the floor boundary.
- Every room must satisfy its prepared minimum/maximum dimension and area ranges.
- Rooms may not overlap each other.

This matters for hallways: upstream features decide how many hallway rooms reach the solver. The solver can change their position and size, but it does not decide that a hallway room is unnecessary and delete it.

## Built-in Hard Constraints

The default profiles currently enable these hard constraints:

| Key | Behaviour |
|---|---|
| `aspect_ratio` | Enforces configured room aspect-ratio ranges. Default profiles exclude hallway rooms and provide garage/veranda overrides. |
| `room_relations` | Enforces `HARD` room relations from the generation specification using a minimum shared-wall overlap. |
| `attached_bathroom_pairing` | Enforces one-to-one attached-bathroom/bedroom wall pairing with a configurable minimum shared wall. |
| `minimum_coverage` | Requires total room area to cover at least the configured fraction of the floor. |
| `hallway_connectivity` | Requires each hallway to touch at least one configured anchor room and at least one non-hallway/non-anchor destination room. |
| `hallway_dimensions` | Forces one hallway dimension to stay inside the configured corridor-width range. The other dimension may extend as required. |
| `hallway_shared_wall` | Caps the wall length shared by any two hallway rooms. The built-in default is `12` project units. |
| `front_anchor` | Restricts the front-most floor edge to configured room types. |
| `back_exposure` | Requires an eligible configured room type to provide sufficient back-boundary exposure. |
| `garage_placement` | Places present garages at a front-left or front-right floor corner. |
| `boundary_placement` | Applies configured room-type boundary placement rules; the default profile anchors verandas to the front. |

`room_size_hierarchy` is registered and available to custom configurations, but it is not enabled in the built-in default profiles.

Hard constraints determine feasibility. The objective is never allowed to violate them merely to obtain a better score.

## Built-in Soft Constraints

The solver minimizes the weighted sum of all enabled soft-constraint penalties.

| Key | Behaviour |
|---|---|
| `room_relations` | Penalizes unsatisfied `SOFT` room relations. |
| `floor_cluster_position` | Prefers the overall room cluster to be horizontally centered and biased toward the front. |
| `dead_space` | Penalizes unused area inside the overall bounding rectangle of the rooms. |
| `hallway_efficiency` | Penalizes total hallway area and excessive hallway length so supplied hallway rooms tend to become compact. |
| `bathroom_depth` | Prefers bathrooms farther from the front boundary. |
| `kitchen_back_exposure` | Prefers a qualifying kitchen wall on the back boundary. |
| `seed_stability` | Refinement preference that penalizes movement/resizing away from seed geometry. |

The three built-in profiles enable `hallway_efficiency`. Refinement profiles also enable `seed_stability`, so hallway compaction competes normally with the configured preference to preserve the existing layout.

## Hallway Behaviour

### Hard hallway rules

The default profile uses:

```python
HardConstraintUse(
    "hallway_connectivity",
    settings={
        "minimum_overlap": 10,
        "hallway_room_types": (RoomType.HALLWAY,),
        "anchor_room_types": (RoomType.LIVING_ROOM,),
    },
)

HardConstraintUse(
    "hallway_dimensions",
    settings={
        "hallway_room_types": (RoomType.HALLWAY,),
        "minimum_width": 8,
        "maximum_width": 10,
    },
)

HardConstraintUse(
    "hallway_shared_wall",
    settings={
        "hallway_room_types": (RoomType.HALLWAY,),
        "maximum_shared_wall": 12.0,
    },
)
```

`hallway_dimensions` constrains the corridor width, not the corridor length. Therefore a `9 x 20` hallway and a `9 x 70` hallway can both satisfy the hard dimension rule when other constraints allow them.

`hallway_shared_wall` measures the actual collinear overlap of touching hallway walls. Two hallways may touch or connect, but the shared segment cannot exceed `maximum_shared_wall`. Corner-only contact has zero shared-wall length. The built-in maximum is `12` project units.

### Hallway efficiency objective

`hallway_efficiency` treats the supplied hallway set as one circulation geometry cost. It does **not** attempt to label individual hallways as necessary or unnecessary.

Its objective is:

```text
hallway efficiency cost =
    total hallway area * area_penalty_multiplier
  + total excess hallway length * excess_length_penalty_multiplier
```

The complete result is then multiplied by the normal `SoftConstraintUse.weight` through the solver's standard objective assembly.

#### Total hallway area

For every configured hallway room, the existing CP-SAT `area = width * length` variable is included in the total hallway-area penalty.

Consequences:

- A longer hallway costs more than an otherwise-equivalent shorter hallway.
- A wider hallway costs more than a narrower hallway.
- Because `hallway_dimensions` still enforces corridor width/connectivity as hard rules, the solver tends to find the smallest hallway geometry that can satisfy the rest of the model.
- This does not remove hallway rooms. It only influences their geometry.

#### Excess hallway length

For each hallway:

```text
longest_side = max(width, length)
excess_length = max(0, longest_side - preferred_max_length)
```

All `excess_length` values are summed and penalized. `preferred_max_length` is therefore a **soft threshold**, not a maximum allowed hallway length. A longer hallway remains legal when hard constraints require it; it simply becomes more expensive in the objective.

### Default hallway-efficiency settings

The built-in profiles are generated from these `DefaultProfileSettings` values:

```python
DefaultProfileSettings(
    max_hallway_shared_wall=12.0,
    hallway_efficiency_weight=1,
    hallway_area_penalty_multiplier=1,
    hallway_preferred_max_length=40.0,
    hallway_excess_length_penalty_multiplier=5,
)
```

Length values use the same project units as `FloorPlanGenerationSpec`. In the current project convention, `10` project units = `1 m`, so the default preferred maximum length of `40` represents `4 m`.

These are starter values. Consumer projects should calibrate them against their own room-relation weights, floor sizes, and generation profiles.

### Consumer configuration

A consumer can tune the built-in profiles without changing `fpg-core`:

```python
from fpg_core.floor_plan_solver import DefaultProfileSettings, build_default_profiles

profiles = build_default_profiles(
    DefaultProfileSettings(
        max_hallway_shared_wall=12.0,
        hallway_efficiency_weight=2,
        hallway_area_penalty_multiplier=1,
        hallway_preferred_max_length=50.0,
        hallway_excess_length_penalty_multiplier=8,
    )
)

config = profiles.initial
```

Or replace only this soft constraint on an existing configuration:

```python
from fpg_core.domain import RoomType
from fpg_core.floor_plan_solver import SoftConstraintUse

config = INITIAL_GENERATION_PROFILE.with_soft_constraints(
    SoftConstraintUse(
        "hallway_efficiency",
        weight=2,
        settings={
            "hallway_room_types": (RoomType.HALLWAY,),
            "area_penalty_multiplier": 1,
            "preferred_max_length": 50.0,
            "excess_length_penalty_multiplier": 8,
        },
    )
)
```

Settings:

- `hallway_room_types: iterable[RoomType]` — room types treated as hallways. Default: `(RoomType.HALLWAY,)`.
- `area_penalty_multiplier: int >= 0` — multiplier for total hallway area. Default: `1`. Set to `0` to disable only the area component.
- `preferred_max_length: float | None` — soft preferred maximum for a hallway's longest side. Default: `40.0`. Set to `None` to disable the excess-length component's threshold calculation.
- `excess_length_penalty_multiplier: int >= 0` — multiplier for total length beyond `preferred_max_length`. Default: `5`. Set to `0` to disable only this component.
- `SoftConstraintUse.weight: int > 0` — overall weight applied after the component multipliers.

To disable hallway efficiency completely:

```python
config = INITIAL_GENERATION_PROFILE.without_constraints("hallway_efficiency")
```

### Why there is no hallway-count penalty

The solver receives an already-decided set of room specifications and forces every supplied room to exist. Hallway-point cleanup/count decisions happen upstream. Therefore this feature does not guess which hallway should have been removed and does not penalize hallway count.

If connected hallway rooms remain in the solved plan, `floor_plan_post_processing` can still merge them later. Solver-side hallway efficiency and post-processing merging have separate responsibilities:

```text
upstream search/circulation
    decides supplied hallway rooms
            ↓
floor_plan_solver
    keeps every supplied hallway
    satisfies hard connectivity/dimensions
    prefers compact hallway geometry
            ↓
floor_plan_post_processing
    may merge compatible connected hallways
```

## Outputs

The API returns `FloorPlanSolveExecution`, an alias of `FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`.

- `result` always contains the status, optional floor plan, configuration/profile name, and status message.
- `details` is `None` in `PRODUCTION`.
- In `DEBUG`, `details` contains raw solver status, timing, objective information, search statistics, applied constraints, and penalty-term names.
- With hallway efficiency enabled, DEBUG penalty terms can include `hallway_efficiency:total_area` and `hallway_efficiency:excess_length`.
- `metadata` contains the execution mode and total duration.

`FloorPlanSolveResult.profile_name` is retained for public/serialized compatibility even though the selected profile is passed through the explicit `config` field.

## Errors and Expected Behaviour

Invalid specifications, configurations, required seeds, or constraint IDs raise `FloorPlanSolverError` subclasses before/during model construction. Infeasible and interrupted solver outcomes are returned as statuses. Randomness is controlled by `config.solver.random_seed`.

Changing from the old request contract requires replacing:

```python
FloorPlanSolveRequest(..., profile=my_profile)
```

with:

```python
FloorPlanSolveRequest(..., config=my_profile)
```

## Extension Points

- Create a custom `FloorPlanSolverConfig` to select constraints and runtime settings.
- `HardConstraintUse` and `SoftConstraintUse` configure registered constraints.
- `ConstraintRegistry` supports custom hard and soft constraint registrations.
- `build_default_profiles()` constructs the built-in configuration presets.

## AI Instructions

- Keep processing input and solver configuration clearly separate in the public contract.
- Keep OR-Tools objects and implementation modules private.
- Keep hard constraints separate from soft objective preferences.
- Do not add hallway-count/removal logic to the solver while supplied rooms remain mandatory.
- Keep this README synchronized with public contracts, built-in profile defaults, constraint behaviour, and DEBUG details.
- Do not import another feature's internal modules.
