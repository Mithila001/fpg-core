# Floor Plan Solver

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

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
    weight: float,
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
Each profile supplies a finite numeric `SoftConstraintUse.weight` from 0 to 10.
Extra digits round up to the next tenth (2.42 becomes 2.5). A zero weight skips
the constraint. Built-in profiles start at 1.0. `SolverConfig.max_time_seconds` must be
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
| `hallway_dimensions` | corridor width is `10..10`; long dimension is capped at half the non-hallway room span, configurable by orientation |
| `hallway_parallel_overlap` | projected overlap caps for same-orientation hallways: horizontal `40`, vertical `30` units, even when offset |
| `hallway_shared_wall` | hallway pairs may touch/connect, but their collinear shared-wall overlap may not exceed `maximum_shared_wall=12.0` project units; corner-only contact has zero shared-wall length |
| `exterior_wall_exposure` | Back exposure for at least one hallway or kitchen, full front and side exposure for garages, and full front exposure for verandas |
| `living_room_front` | Full front exposure for living rooms when no veranda is supplied |


The generic `boundary_placement` rule remains available for explicit boundary placement. `front_anchor` is no longer registered. Exterior exposure means an unobstructed perpendicular path to the generation boundary; contact with that boundary is not required. Only rooms obstruct these paths. The hard back rule and soft kitchen rule require one continuous exposed segment of at least 10 project units in the default profiles. Veranda and living-room rules require the entire front wall; the living-room rule applies only when there is no veranda. Garage exposure is limited to the projections of its own walls, so the old adjacent-front-corner restriction no longer applies. Openings and post-processing use separate behavior and may not preserve these solver-stage exposure results.

The generic `exterior_wall_exposure` hard and soft constraint accepts `settings.rules`: each rule has an `id`, `room_types`, a `match` mapping (`policy` is `all` or `at_least`, with a positive `count` for the latter), and a `requirement`. Requirements are nested `all`/`any` lists or leaves containing `side` (`front`, `back`, `left`, `right`), `coverage` (`full_wall` or `minimum_continuous_length`), and `minimum_length` for the latter. Soft rules contribute pass-or-fail checks to the combined exposure penalty. Room types are `RoomType` members in Core and strings in Lab JSON. The conditional `living_room_front` constraint uses the same required rule format.

Validation requires a nonempty rule list, unique nonblank IDs, nonempty room-type lists, and exactly the fields described above. Each `all` or `any` node has a nonempty list of child requirements; leaves cannot contain extra fields. Lengths must be finite positive numbers, and counts positive integers (booleans are rejected). An `all` match applies the requirement to every matching room; `at_least` counts rooms satisfying the complete requirement, not individual matching leaves. Each applicable soft rule counts once in the combined exposure penalty, regardless of how many rooms fail. See the [design rationale](../features/solver.md#exterior-wall-exposure-design-rationale) for the geometry and scope.

To add or change a rule, edit the relevant hard or soft constraint use in the profile, adding another uniquely identified rule to its `rules` list when needed. Use the generic key for ordinary policies; `living_room_front` retains its veranda condition. Core validates settings when constructing constraint uses and checks scaled minimum lengths against the floor span during model construction. Lab JSON maps room-type strings to Core enums and rejects unknown configuration fields.

For example, to require two bedrooms to have at least 10 continuous project units
of front or back exposure, add this use to a configuration's hard constraints:

```python
from fpg_core.domain import RoomType
from fpg_core.floor_plan_solver import HardConstraintUse

bedroom_exposure = HardConstraintUse("exterior_wall_exposure", {
    "rules": [{
        "id": "two_bedrooms",
        "room_types": [RoomType.BEDROOM],
        "match": {"policy": "at_least", "count": 2},
        "requirement": {"any": [
            {"side": "front", "coverage": "minimum_continuous_length", "minimum_length": 10},
            {"side": "back", "coverage": "minimum_continuous_length", "minimum_length": 10},
        ]},
    }],
})
```

Use `SoftConstraintUse` with the same settings and a positive weight for a
preference. `all` applies to each matching room and is satisfied when none
match. A hard `at_least` rule is infeasible when too few rooms qualify; a soft
rule has no penalty if there are no matching rooms. The existing hard back rule
is infeasible with no eligible rooms; the soft kitchen preference is skipped
when no kitchen matches. Supplied rooms are required by the solver. Invalid
rule structure and lengths raise `InvalidProfileError`; minimum lengths larger
than the corresponding floor span are rejected during model construction.
Lengths are project units and are rounded upward using the configured integer
coordinate scale. A given constraint key occurs once per hard or soft list;
put multiple identified rules in its `rules` list. Defaults use 10 units per
metre in examples, but applications own unit conversion.

Exposure settings must use `rules`; legacy settings and retired constraint keys are not supported. Replace saved profiles or development database configurations with the current seed configuration before running them. Historical snapshots are not migrated and may not be executable with current Core. Unknown constraint keys are rejected when the solver validates its registry.

`room_size_hierarchy` is registered for custom configurations but is not enabled by
the built-in profiles.

`bathroom_hallway_shared_wall` is a registered hard constraint enabled in the
built-in profiles. Custom profiles must include its key explicitly. Settings:
`maximum_shared_sides` is an integer from 0 to 4 (default 1), and
`additional_shared_length` is a finite non-negative project-unit length (default
10). All hallway rooms are aggregated by bathroom side; the selected number of
sides may share freely, and total sharing on the other sides is capped by the
extra length. Only regular bathrooms are affected. Existing saved Lab profiles
must add this hard-constraint entry to enable it. Existing experiment snapshots
are preserved.

## Built-in soft constraints

The default registry provides:

- `room_relations`
- `room_size_relations`
- `floor_cluster_position`
- `room_center_line` (prefers each room center near the floor width midpoint; optional, not enabled by built-in profiles)
- `dead_space`
- `hallway_efficiency`
- `bathroom_depth`
- `exterior_wall_exposure`
- `seed_stability`

The solver minimizes the sum of each combined penalty multiplied by its profile
weight. Hard constraints determine feasibility.

| Constraint | Combined penalty in points |
|---|---|
| `room_relations` | Percentage of missed soft relationships. Each AND group passes if all targets qualify, and each OR group passes if any target qualifies. |
| `room_size_relations` | For each applicable ratio bound, divide positive excess or shortfall by the reference area's maximum capacity, convert to points and cap at 100. Average the bounds using their optional relative rule multipliers. Upper bounds compare the largest compared room with the smallest reference room. Lower bounds reverse the extrema. |
| `floor_cluster_position` | Divide the absolute side-margin difference by floor width and front setback by floor length. Average the resulting percentages using the enabled component multipliers. |
| `dead_space` | Empty area inside the rooms' bounding rectangle as a percentage of that rectangle. |
| `hallway_efficiency` | Average hallway area as a percentage of floor area and unshared hallway wall as a percentage of total hallway perimeter. Use `area_penalty_multiplier` (default 1) for area and 1 for wall. A zero area multiplier disables the area component. |
| `bathroom_depth` | Average the selected room centres' distance from the back as a percentage of floor length. |
| `exterior_wall_exposure` | Percentage of applicable rules missed. Each rule passes or fails as a whole. |
| `room_center_line` | Average the room centres' distance from the floor centre line as a percentage of half the floor width. |
| `seed_stability` | Divide absolute changes by the matching floor span. Average the available axes in each component, combine position and size with their respective multipliers, then average across matched rooms. |

Room-size rules accept `compared_type`, `reference_type`, `min_ratio` and/or
`max_ratio`, and an optional positive integer `penalty_multiplier`. Ratios
mean compared area divided by reference area. `precision` defaults to 1000.
Rules with absent room types are skipped. Final scoring has separate settings.

Seed stability's `position_multiplier` and `size_multiplier` accept finite,
non-negative numbers, including decimals. They set the relative balance
between position and size. For example, 0.1 and 0.1 give the same balance as
1 and 1. Use the profile's soft constraint weight to control its overall
contribution. Zero disables a component. The solver rejects ratios too
precise to represent with safe integer coefficients.

### Authoring a soft constraint

Implement `build_penalty(context, settings)` to return one bounded CP-SAT
integer expression in hundredths of a point (0 to 10,000). Validate the settings
in the constraint, define what it measures and explain the endpoints and
aggregation. Return zero when the preference is met or nothing applies. Round
positive fractions upward to keep small misses visible. The profile supplies the
weight. The solver applies it once and reports the objective and its bound in
weighted points. Debug penalty term names are the constraint keys.

Custom constraints using `build_penalties` must migrate to the new method.
Replace saved profiles with the current defaults and retune custom weights on
the new scale. Legacy objective values and new weighted points use different
scales.

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
    max_hallway_shared_wall: float = 12.0,
    hallway_efficiency_weight: float = 1.0,
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

The shipped weights are all 1.0. Initial generation enables the seven core
preferences from `room_relations` through `exterior_wall_exposure` in the table
above. Refinement A adds `seed_stability`, and Refinement B also drops
`floor_cluster_position`. The optional `room_center_line` is off in all three.

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

With hallway efficiency enabled and applicable, `penalty_terms` can contain
`'hallway_efficiency'`.
`FloorPlanSolveResult.profile_name` is retained for serialized/public compatibility
even though the request field is named `config`.

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


## Warnings / diagnostics

The solver does not expose a separate warning collection. Expected solver outcomes are represented by `SolverStatus` and `FloorPlanSolveResult.message`; a non-solution status is not automatically an exception. In `DEBUG`, `SolverDiagnostics` contains raw solver status, wall time, objective/bound information, conflicts, branches, applied hard/soft constraint IDs, and penalty terms. `PRODUCTION` omits diagnostics.

## Public Export Inventory

### `fpg_core.floor_plan_solver` exports (25)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `DEFAULT_PROFILES` | dataclass/contract | `constructor has no separately inspectable signature` | ProfileCatalog(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') |
| `DefaultProfileSettings` | dataclass/contract | `(coordinate_scale: 'int' = 1, minimum_coverage_ratio: 'float' = 0.6, minimum_adjacency_overlap: 'float' = 10, attached_bathroom_minimum_shared_wall: 'float' = 10.0, initial_max_time_seconds: 'float' = 5.0, refinement_max_time_seconds: 'float' = 2.0, refinement_position_tolerance: 'float' = 10, refinement_size_tolerance: 'float' = 10, max_hallway_shared_wall: 'float' = 12.0, hallway_efficiency_weight: 'float' = 1.0, hallway_area_penalty_multiplier: 'int' = 1, hallway_preferred_max_length: 'float | None' = 40.0, hallway_excess_length_penalty_multiplier: 'int' = 5) -> None` | Central tuning values used to construct the built-in profiles, including hallway compactness weights. |
| `ConstraintRegistry` | dataclass/contract | `(hard: 'dict[str, HardConstraint]' = <factory>, soft: 'dict[str, SoftConstraint]' = <factory>) -> None` | Runtime collection of available hard and soft constraints. |
| `FloorPlanSolveExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `FloorPlanSolveRequest` | dataclass/contract | `(specification: 'FloorPlanGenerationSpec', config: 'FloorPlanSolverConfig', candidate_hints: 'tuple[RoomPlacementHint, ...]' = (), existing_floor_plan: 'FloorPlan \| None' = None) -> None` | Processing input for one floor-plan solve. |
| `FloorPlanSolveResult` | dataclass/contract | `(status: 'SolverStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') -> None` | FloorPlanSolveResult(status: 'SolverStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') |
| `FloorPlanSolver` | class/interface/registry | `(registry: 'ConstraintRegistry \| None' = None) -> 'None'` | Small application service that owns one generic CP-SAT pipeline. |
| `FloorPlanSolverConfig` | dataclass/contract | `(name: 'str', hard_constraints: 'tuple[HardConstraintUse, ...]', soft_constraints: 'tuple[SoftConstraintUse, ...]', solver: 'SolverConfig' = <factory>, preparation: 'PreparationConfig' = <factory>, seed: 'SeedPolicy' = <factory>) -> None` | Complete reusable configuration for one CP-SAT generation stage. |
| `FloorPlanSolverError` | exception | `constructor has no separately inspectable signature` | Base exception for invalid solver input or configuration. |
| `GenerationProfile` | dataclass/contract | `(name: 'str', hard_constraints: 'tuple[HardConstraintUse, ...]', soft_constraints: 'tuple[SoftConstraintUse, ...]', solver: 'SolverConfig' = <factory>, preparation: 'PreparationConfig' = <factory>, seed: 'SeedPolicy' = <factory>) -> None` | Complete reusable configuration for one CP-SAT generation stage. |
| `HardConstraintUse` | dataclass/contract | `(key: 'str', settings: 'Mapping[str, Any]' = <factory>) -> None` | Configuration for one enabled hard constraint. |
| `INITIAL_GENERATION_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `PreparationConfig` | dataclass/contract | `(coordinate_scale: 'int' = 10) -> None` | Conversion settings between project units and CP-SAT integer units. |
| `ProfileCatalog` | dataclass/contract | `(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') -> None` | ProfileCatalog(initial: 'GenerationProfile', refinement_a: 'GenerationProfile', refinement_b: 'GenerationProfile') |
| `REFINEMENT_A_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `REFINEMENT_B_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Complete reusable configuration for one CP-SAT generation stage. |
| `RoomPlacementHint` | dataclass/contract | `(room_id: 'RoomId', x: 'float', y: 'float', width: 'float \| None' = None, length: 'float \| None' = None) -> None` | Candidate-search hint for a room's lower-left position and optional size. |
| `SeedPolicy` | dataclass/contract | `(source: 'SeedSource' = <SeedSource.NONE: 'none'>, require_source: 'bool' = False, apply_hints: 'bool' = True, position_tolerance: 'float \| None' = None, size_tolerance: 'float \| None' = None) -> None` | Controls how candidate or existing-layout geometry is used as a seed. |
| `SeedSource` | enum | `NONE='none'; CANDIDATE_HINTS='candidate_hints'; EXISTING_FLOOR_PLAN='existing_floor_plan'` | Documented in the corresponding feature/shared section. |
| `SoftConstraintUse` | dataclass/contract | `(key: 'str', weight: 'float', settings: 'Mapping[str, Any]' = <factory>) -> None` | Configuration for one enabled soft constraint and its objective weight. |
| `SolverConfig` | dataclass/contract | `(max_time_seconds: 'float' = 30.0, num_search_workers: 'int' = 0, random_seed: 'int \| None' = None, log_search_progress: 'bool' = False, relative_gap_limit: 'float \| None' = None, cp_model_presolve: 'bool' = True) -> None` | OR-Tools runtime settings for one solve. |
| `SolverDiagnostics` | dataclass/contract | `(raw_status: 'str', wall_time_seconds: 'float', objective_value: 'float \| None', best_objective_bound: 'float \| None', conflicts: 'int', branches: 'int', applied_hard_constraints: 'tuple[str, ...]', applied_soft_constraints: 'tuple[str, ...]', penalty_terms: 'tuple[str, ...]') -> None` | SolverDiagnostics(raw_status: 'str', wall_time_seconds: 'float', objective_value: 'float \| None', best_objective_bound: 'float \| None', conflicts: 'int', branches: 'int', applied_hard_constraints: 'tuple[str, ...]', applied_soft_constraints: 'tuple[str, ...]', penalty_terms: 'tuple[str, ...]') |
| `SolverStatus` | enum | `OPTIMAL='optimal'; FEASIBLE='feasible'; INFEASIBLE='infeasible'; MODEL_INVALID='model_invalid'; UNKNOWN='unknown'` | Documented in the corresponding feature/shared section. |
| `build_default_profiles` | function | `build_default_profiles(settings: 'DefaultProfileSettings \| None' = None) -> 'ProfileCatalog'` | Documented in the corresponding feature/shared section. |
| `generate_floor_plan` | function | `generate_floor_plan(request: 'FloorPlanSolveRequest', *, registry: 'ConstraintRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'FloorPlanSolveExecution'` | Documented in the corresponding feature/shared section. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
