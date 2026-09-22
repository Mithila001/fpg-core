# Floor Plan Solver

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Internal feature `README.md` files are development notes and are not the consumer contract. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Builds and solves a CP-SAT floor-plan model from request-specific generation data and
an explicit reusable solver configuration. Every room supplied by the generation
specification remains mandatory; the solver may move/resize a hallway but does not
remove a hallway room that upstream stages supplied.

## Public API

```python
generate_floor_plan(
    request: FloorPlanSolveRequest,
    *,
    registry: ConstraintRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution

FloorPlanSolver(registry: ConstraintRegistry | None = None)
FloorPlanSolver.solve(
    request: FloorPlanSolveRequest,
    *,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> FloorPlanSolveExecution
```

Preferred imports are from `fpg_core.floor_plan_solver`. `GenerationProfile` remains
a compatibility alias of `FloorPlanSolverConfig`.

## Inputs

```python
FloorPlanSolveRequest(
    specification: FloorPlanGenerationSpec,
    config: FloorPlanSolverConfig,
    candidate_hints: tuple[RoomPlacementHint, ...] = (),
    existing_floor_plan: FloorPlan | None = None,
)

RoomPlacementHint(
    room_id: RoomId,
    x: float,
    y: float,
    width: float | None = None,
    length: float | None = None,
)
```

`specification` defines the floor and every room that must be placed. Candidate hints
are optional seed geometry. `existing_floor_plan` is optional unless the selected seed
policy requires it. Unknown/duplicate hint room IDs are invalid; hint sizes, when
provided, must be positive. Prepared hints are clamped to feasible floor/room bounds.
Existing-plan rooms absent from the specification are ignored as seed inputs.

## Structural rules that are always active

These are solver-model invariants rather than selectable registry constraints:

- every `FloorPlanGenerationSpec.rooms` entry is present in the result;
- every room stays inside the floor boundary;
- every room satisfies its prepared dimension and area bounds;
- rooms do not overlap.

Therefore hallway-count/removal decisions belong upstream. The solver cannot label a
supplied hallway “unnecessary” and delete it.

## Configuration

```python
HardConstraintUse(
    key: str,
    settings: Mapping[str, Any] = {},
)

SoftConstraintUse(
    key: str,
    weight: int,
    settings: Mapping[str, Any] = {},
)

SolverConfig(
    max_time_seconds: float = 30.0,
    num_search_workers: int = 0,
    random_seed: int | None = None,
    log_search_progress: bool = False,
    relative_gap_limit: float | None = None,
    cp_model_presolve: bool = True,
)

PreparationConfig(
    coordinate_scale: int = 10,
)

SeedPolicy(
    source: SeedSource = SeedSource.NONE,
    require_source: bool = False,
    apply_hints: bool = True,
    position_tolerance: float | None = None,
    size_tolerance: float | None = None,
)

FloorPlanSolverConfig(
    name: str,
    hard_constraints: tuple[HardConstraintUse, ...],
    soft_constraints: tuple[SoftConstraintUse, ...],
    solver: SolverConfig = SolverConfig(),
    preparation: PreparationConfig = PreparationConfig(),
    seed: SeedPolicy = SeedPolicy(),
)
```

`SeedSource` values are `NONE='none'`, `CANDIDATE_HINTS='candidate_hints'`, and
`EXISTING_FLOOR_PLAN='existing_floor_plan'`. Seed tolerances use project units;
`None` leaves that dimension unbounded and uses hints only, `0` fixes the seeded
value, and positive values bound movement or size.

`FloorPlanSolverConfig` requires a non-empty name and unique hard/soft constraint keys.
`SoftConstraintUse.weight` must be positive. `SolverConfig.max_time_seconds` must be
positive; workers, random seed, and relative gap cannot be negative.
`PreparationConfig.coordinate_scale` must be at least `1`.

Immutable helper methods return modified configs:

```python
config.without_constraints(*keys)
config.with_hard_constraints(*uses)
config.with_soft_constraints(*uses)
```

## Built-in hard constraints

The shipped default profiles enable:

| Key | Exact built-in settings / behavior |
|---|---|
| `aspect_ratio` | min `0.60`, max `1.80`; hallways excluded from this rule; garage override `0.45..0.70`; veranda override `1.20..3.50` |
| `room_relations` | enforces `HARD` specification relations; `minimum_overlap=10` |
| `attached_bathroom_pairing` | minimum shared wall `10`; attached-bathroom type paired with bedroom type |
| `minimum_coverage` | `ratio=0.6` |
| `hallway_connectivity` | `minimum_overlap=10`; hallway type must touch an anchor type and a non-hallway/non-anchor destination; default anchor is living room |
| `hallway_dimensions` | hallway corridor width is constrained to `8..10`; the other dimension may extend as needed |
| `front_anchor` | veranda, living room, bedroom, garage |
| `back_exposure` | hallway and kitchen; minimum exposure `10.0` |
| `garage_placement` | garage type |
| `boundary_placement` | veranda on `front` with offset `0.0` |

`room_size_hierarchy` is registered for custom configurations but is not enabled by
the built-in profiles.

## Built-in soft constraints

The default registry provides:

- `room_relations`
- `floor_cluster_position`
- `dead_space`
- `hallway_efficiency`
- `bathroom_depth`
- `kitchen_back_exposure`
- `seed_stability`

The solver minimizes the weighted sum of enabled soft-constraint penalties. Hard
constraints always determine feasibility.

### Hallway efficiency

`hallway_efficiency` treats all configured hallway rooms as one circulation-geometry
cost. It does not decide whether an individual hallway is semantically necessary.

The objective components are:

```text
hallway efficiency cost =
    total hallway area * area_penalty_multiplier
  + total excess hallway length * excess_length_penalty_multiplier
```

The complete penalty is then multiplied by the ordinary `SoftConstraintUse.weight`.

For each hallway:

```text
longest_side = max(width, length)
excess_length = max(0, longest_side - preferred_max_length)
```

`preferred_max_length` is a soft threshold, not a hard maximum. A longer hallway is
still legal when hard constraints require it; it simply contributes more objective
cost. Penalizing total hallway area also encourages the solver to shrink hallway
geometry toward the smallest dimensions compatible with hard constraints and the
other objective terms. It never removes the hallway room.

Supported settings:

| Setting | Type | Default | Validation / meaning |
|---|---|---:|---|
| `hallway_room_types` | iterable of `RoomType` | `(RoomType.HALLWAY,)` | room types included in the hallway-efficiency objective |
| `area_penalty_multiplier` | `int` | `1` | must be `>= 0`; `0` disables the area component |
| `preferred_max_length` | `float | None` | `40.0` | positive finite project-unit length; `None` disables excess-length threshold calculation |
| `excess_length_penalty_multiplier` | `int` | `5` | must be `>= 0`; `0` disables the excess-length component |
| `SoftConstraintUse.weight` | `int` | profile-defined | must be `> 0`; weights the whole hallway-efficiency penalty |

With the project convention `10` units = `1 m`, the built-in
`preferred_max_length=40.0` corresponds to `4 m`.

To disable hallway efficiency completely:

```python
config = INITIAL_GENERATION_PROFILE.without_constraints("hallway_efficiency")
```

## Built-in profile construction

```python
DefaultProfileSettings(
    coordinate_scale: int = 1,
    minimum_coverage_ratio: float = 0.6,
    minimum_adjacency_overlap: float = 10,
    attached_bathroom_minimum_shared_wall: float = 10.0,
    initial_max_time_seconds: float = 5.0,
    refinement_max_time_seconds: float = 2.0,
    refinement_position_tolerance: float = 10,
    refinement_size_tolerance: float = 10,
    hallway_efficiency_weight: int = 1,
    hallway_area_penalty_multiplier: int = 1,
    hallway_preferred_max_length: float | None = 40.0,
    hallway_excess_length_penalty_multiplier: int = 5,
)

build_default_profiles(
    settings: DefaultProfileSettings | None = None,
) -> ProfileCatalog
```

The returned `ProfileCatalog` contains `initial`, `refinement_a`, and `refinement_b`.
The public constants `DEFAULT_PROFILES`, `INITIAL_GENERATION_PROFILE`,
`REFINEMENT_A_PROFILE`, and `REFINEMENT_B_PROFILE` are created from the default
settings above.

Exact built-in soft uses:

| Profile | Exact soft uses (`key: weight`; important settings) | Runtime / seed |
|---|---|---|
| `initial_generation` | `room_relations:40` (overlap 10), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:3`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:2`, `kitchen_back_exposure:10` (exposure 10) | 5 s; candidate hints optional; coordinate scale 1 |
| `refinement_a` | `room_relations:50`, `seed_stability:20` (position 2/size 1), `floor_cluster_position:1` (horizontal 1/front 2), `dead_space:4`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:3`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 10; coordinate scale 1 |
| `refinement_b` | `room_relations:60`, `seed_stability:35` (position 2/size 2), `dead_space:6`, `hallway_efficiency:1` (area 1, preferred max length 40, excess multiplier 5), `bathroom_depth:4`, `kitchen_back_exposure:10` | 2 s; existing plan required; position/size tolerance 5; coordinate scale 1 |

## Recommended values

**Built-in profile values** are starter settings, not universal architectural
standards. For hallway efficiency, begin with the shipped weight/multipliers and tune
them against actual generated plans rather than adding a hallway-count penalty. For
repeatable solver tests, set a fixed `random_seed` and use
`num_search_workers=1`.

## Outputs

```python
FloorPlanSolveResult(
    status: SolverStatus,
    floor_plan: FloorPlan | None,
    profile_name: str,
    message: str,
)
```

`SolverStatus` values are `OPTIMAL='optimal'`, `FEASIBLE='feasible'`,
`INFEASIBLE='infeasible'`, `MODEL_INVALID='model_invalid'`, and
`UNKNOWN='unknown'`. `.solved` is true only when the status has a solution and
`floor_plan` is not `None`.

`FloorPlanSolveExecution` is
`FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`. In PRODUCTION,
`details=None`. DEBUG diagnostics are:

```python
SolverDiagnostics(
    raw_status: str,
    wall_time_seconds: float,
    objective_value: float | None,
    best_objective_bound: float | None,
    conflicts: int,
    branches: int,
    applied_hard_constraints: tuple[str, ...],
    applied_soft_constraints: tuple[str, ...],
    penalty_terms: tuple[str, ...],
)
```

With hallway efficiency enabled, `penalty_terms` can contain
`'hallway_efficiency:total_area'` and `'hallway_efficiency:excess_length'`.
`FloorPlanSolveResult.profile_name` is retained for serialized/public compatibility
even though the request field is named `config`.

## Warnings / diagnostics

The solver does not expose a separate warning collection. Expected solver outcomes are represented by `SolverStatus` and `FloorPlanSolveResult.message`; a non-solution status is not automatically an exception. In `DEBUG`, `SolverDiagnostics` contains raw solver status, wall time, objective/bound information, conflicts, branches, applied hard/soft constraint IDs, and penalty terms. `PRODUCTION` omits diagnostics.

## Errors / failure conditions

Invalid specifications, configs, constraint IDs, or required seed data raise the
`FloorPlanSolverError` family before or during model construction. Specific subclasses
remain available from `fpg_core.floor_plan_solver.exceptions`.
`INFEASIBLE`, `MODEL_INVALID`, and `UNKNOWN` are normal result statuses, not
exceptions merely because solving did not produce a plan.

## Usage example

```python
from fpg_core.domain import ExecutionMode, RoomId
from fpg_core.floor_plan_solver import (
    INITIAL_GENERATION_PROFILE,
    FloorPlanSolveRequest,
    RoomPlacementHint,
    generate_floor_plan,
)

execution = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=example_specification,
        config=INITIAL_GENERATION_PROFILE,
        candidate_hints=(RoomPlacementHint(RoomId("living"), 20, 10),),
    ),
    mode=ExecutionMode.DEBUG,
)
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
floor_plan = execution.result.floor_plan
```

## Important behavioral notes

Upstream search/circulation decides which hallway rooms reach the solver. The solver
keeps every supplied hallway and can make its geometry smaller through the soft
hallway-efficiency objective while still satisfying hard width/connectivity rules.
Connected hallways may later be merged by `floor_plan_post_processing`; that is a
separate responsibility from solver-side compaction.

## Public Export Inventory

The supported feature-root import surface is `fpg_core.floor_plan_solver`. Its current exported symbols are:

- `DEFAULT_PROFILES`
- `DefaultProfileSettings`
- `ConstraintRegistry`
- `FloorPlanSolveExecution`
- `FloorPlanSolveRequest`
- `FloorPlanSolveResult`
- `FloorPlanSolver`
- `FloorPlanSolverConfig`
- `FloorPlanSolverError`
- `GenerationProfile`
- `HardConstraintUse`
- `INITIAL_GENERATION_PROFILE`
- `PreparationConfig`
- `ProfileCatalog`
- `REFINEMENT_A_PROFILE`
- `REFINEMENT_B_PROFILE`
- `RoomPlacementHint`
- `SeedPolicy`
- `SeedSource`
- `SoftConstraintUse`
- `SolverConfig`
- `SolverDiagnostics`
- `SolverStatus`
- `build_default_profiles`
- `generate_floor_plan`

Consumers should prefer the feature-root import surface shown above and `fpg_core.domain` for canonical shared contracts. Implementation submodules are not part of the supported consumer surface unless explicitly documented.

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
