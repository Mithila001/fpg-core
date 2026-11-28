# Floor Plan Openings

> **Consumer documentation.** Package-wide conventions, shared domain contracts, execution envelopes, units, and versioning are defined in [API_GUIDE.md](../API_GUIDE.md). Implementation rationale is maintained in the internal architecture and feature notes. Examples that reference `example_*` values use the [reusable example fixtures](../API_GUIDE.md#reusable-example-fixtures).

## Purpose

Analyzes a finalized floor plan and uses CP-SAT to place interior doors, exterior
doors, and windows without mutating the source plan. Interior room-type compatibility,
required door-network access, and door placement priorities are consumer-configurable.

## Public API

```python
generate_openings(
    request: OpeningGenerationRequest,
    *,
    registry: OpeningFeatureRegistry | None = None,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> OpeningGenerationExecution
```

Preferred imports are from `fpg_core.floor_plan_openings` or its public `api` module.
`OpeningGenerationProfile` and `DEFAULT_OPENING_PROFILE` remain compatibility names
for `FloorPlanOpeningsConfig` and `DEFAULT_OPENING_CONFIG`.

## Inputs

```python
OpeningGenerationRequest(
    floor_plan: FloorPlan,
    config: FloorPlanOpeningsConfig,
)
```

The source plan must have valid finite rectilinear floor/room geometry, positive room
area, unique room IDs, standard rooms inside the floor without area overlap, and **no
existing openings**. The source plan is never mutated. Exterior walls are taken from
the outside boundary of the union of room geometries, including recesses and steps;
boundaries of enclosed voids are excluded.

## Configuration

```python
GeometryConfig(
    coordinate_scale: int = 10,
    tolerance: float = 1e-6,
    corner_clearance: float = 5.0,
    window_spacing: float = 5.0,
)

DimensionConfig(
    door_width: float = 10.0,
    window_width: float = 16.0,
    minimum_shared_wall: float = 10.0,
)

SolverConfig(
    max_time_seconds: float = 10.0,
    num_search_workers: int = 1,
    random_seed: int = 0,
    cp_model_presolve: bool = True,
    log_search_progress: bool = False,
)
```

`coordinate_scale` must be at least `1`; geometry tolerance and dimensions must be
positive; corner/window clearances cannot be negative. Solver time and workers must
be positive and the random seed cannot be negative. Window policies specify their
own widths and minimum and preferred clearances.
Main-entrance fallback retains its existing behavior. Secondary entrances require the
full configured door width. Interior doors use the policy below.

### Interior door policy

```python
InteriorDoorPolicy(
    door_width=10.0, preferred_clearance=5.0, minimum_clearance=0.0,
    minimum_shared_wall=10.0, placement_preference="wall_end",
)
InteriorDoorConfig(
    default=InteriorDoorPolicy(),
    overrides=(
        (RoomType.BATHROOM, InteriorDoorPolicy(8.0, 2.0, 0.0, 8.0, "center")),
        (RoomType.ATTACHED_BATHROOM, InteriorDoorPolicy(8.0, 2.0, 0.0, 8.0, "center")),
    ),
)
```

`FloorPlanOpeningsConfig.interior_doors` holds the default and ordered room-type
policy overrides. The first matching override wins regardless of wall direction;
room types may occur once. Dimensions are project units, positive and finite;
clearances are finite and nonnegative, and preferred clearance must be at least
minimum clearance. `placement_preference` is `wall_end` or `center`.

The minimum shared-wall length, exact door width and clearance at both wall ends
are hard constraints. Preferred clearance is a soft target applied independently at
both ends. The solver first minimizes total selected interior-door clearance deficits,
then maximizes opening selection and placement preferences without increasing that
minimum; both searches share the configured time budget. If the minimum cannot be
proven in time, a feasible result may not optimize optional openings. Short walls
can therefore have less corner space, but door width is never reduced. Standard
interior doors prefer a wall end; bathroom overrides prefer the center. The existing
`geometry.corner_clearance` and `dimensions.door_width` govern exterior doors;
interior and window policies are configured separately.

### Window policy

`WindowPolicy(width=16.0, target_count=1, preferred_clearance=5.0,
minimum_clearance=0.0)` describes an eligible room type. Bathroom and attached
bathroom defaults are width 5 and preferred clearance 2. Width and clearances are
in project units; width and count must be positive, and preferred clearance must
be at least the non-negative minimum. The target is optional, so a missing window
does not make a plan infeasible. The first window in each room has higher selection
priority than additional targets. Placement favors preferred clearance and the
wall center, subject to opening spacing and other constraints.

`FeaturePolicy.window_room_types` selects eligible types; `window_policies` maps
types to `WindowPolicy` values. An eligible type without an override uses
`dimensions.window_width`, `geometry.corner_clearance`, one window and zero
minimum clearance. Add the type to `window_room_types` to enable it.

### FeaturePolicy

```python
FeaturePolicy(
    allowed_room_pairs: tuple[tuple[RoomType, RoomType], ...] = DEFAULT_PAIRS,
    room_door_caps: tuple[tuple[RoomType, int], ...] = DEFAULT_CAPS,
    secondary_room_priority: tuple[RoomType, ...] = (
        RoomType.KITCHEN,
        RoomType.HALLWAY,
    ),
    window_room_types: tuple[RoomType, ...] = (
        RoomType.BEDROOM,
        RoomType.LIVING_ROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.BATHROOM,
        RoomType.ATTACHED_BATHROOM,
    ),
    window_policies: tuple[tuple[RoomType, WindowPolicy], ...] = DEFAULT_WINDOW_POLICIES,
    normal_connection_caps: tuple[tuple[RoomType, int], ...] = DEFAULT_NORMAL_CAPS,
    prevent_duplicate_connections: bool = True,
    main_side_priority: tuple[str, ...] = ("south", "east", "north", "west"),
    secondary_side_priority: tuple[str, ...] = ("north", "west", "east", "south"),
    window_side_priority: tuple[str, ...] = ("east", "north", "south", "west"),
    required_access_room_types: tuple[RoomType, ...] = DEFAULT_REQUIRED_ACCESS,
    door_placement_priority: tuple[tuple[RoomType, int], ...] = DEFAULT_DOOR_PRIORITY,
)
```

Exact default `allowed_room_pairs`:

```python
(
    (RoomType.BEDROOM, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.LIVING_ROOM),
    (RoomType.KITCHEN, RoomType.DINING_ROOM),
    (RoomType.BATHROOM, RoomType.LIVING_ROOM),
    (RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM),
    (RoomType.VERANDA, RoomType.LIVING_ROOM),
    (RoomType.GARAGE, RoomType.LIVING_ROOM),
    (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
    (RoomType.BEDROOM, RoomType.HALLWAY),
    (RoomType.BATHROOM, RoomType.HALLWAY),
    (RoomType.LIVING_ROOM, RoomType.HALLWAY),
    (RoomType.KITCHEN, RoomType.HALLWAY),
    (RoomType.DINING_ROOM, RoomType.HALLWAY),
    (RoomType.VERANDA, RoomType.HALLWAY),
    (RoomType.GARAGE, RoomType.HALLWAY),
    (RoomType.HALLWAY, RoomType.HALLWAY),
)
```

This tuple is authoritative. Pair order does not matter, duplicate logical pairs are
rejected. Attached bathrooms connect only to bedrooms, even if another pair is configured.

Exact default door caps:

```python
(
    (RoomType.BEDROOM, 2),
    (RoomType.BATHROOM, 1),
    (RoomType.LIVING_ROOM, 10),
    (RoomType.HALLWAY, 10),
    (RoomType.KITCHEN, 1),
    (RoomType.ATTACHED_BATHROOM, 1),
    (RoomType.VERANDA, 1),
    (RoomType.GARAGE, 1),
    (RoomType.DINING_ROOM, 2),
)
```

Caps must be positive and each room type may appear only once. Normal connection
caps default to one for bedrooms, kitchens, bathrooms and attached bathrooms.
One bedroom-to-attached-bathroom or kitchen-to-dining connection is allowed in
addition to the bedroom or kitchen's normal and total cap. Other rooms' caps still
apply. Duplicate connections between the same room instances are prevented by
default, with shared wall segments treated as alternative placements.
Normal connections without a specific preference are selected when needed for
access, rather than rewarded solely to increase the door count. Kitchen-dining
and preferred hallway connections can receive an optional selection reward.

Exact default required-access room types:

```python
(
    RoomType.BEDROOM,
    RoomType.BATHROOM,
    RoomType.ATTACHED_BATHROOM,
    RoomType.LIVING_ROOM,
    RoomType.KITCHEN,
    RoomType.DINING_ROOM,
    RoomType.HALLWAY,
    RoomType.VERANDA,
    RoomType.GARAGE,
)
```

The tuple must contain unique room types.

Exact default door-placement priorities:

```python
(
    (RoomType.BEDROOM, 100),
    (RoomType.BATHROOM, 100),
    (RoomType.ATTACHED_BATHROOM, 100),
    (RoomType.KITCHEN, 80),
    (RoomType.DINING_ROOM, 60),
    (RoomType.GARAGE, 60),
    (RoomType.VERANDA, 40),
    (RoomType.LIVING_ROOM, 20),
    (RoomType.HALLWAY, 10),
)
```

Priorities must be non-negative and each room type may appear only once. Higher values
mean that room's nearest usable corner/wall end dominates the choice of which end of a
shared wall the door should favor. If the higher-priority room is tied, the other room
acts as the tie-breaker. The selected door is then optimized as close as possible to
that preferred end while still satisfying corner clearance, width, wall bounds,
non-overlap, window spacing, and other hard constraints. This applies to **doors**;
windows retain center-oriented placement behavior.

Every side-priority tuple must contain exactly `south`, `east`, `north`, and `west`
once each.

### FloorPlanOpeningsConfig

```python
FloorPlanOpeningsConfig(
    name: str,
    enabled_features: tuple[str, ...] = (
        "interior_doors",
        "exterior_doors",
        "windows",
    ),
    enabled_constraints: tuple[str, ...] = (
        "shared_placement",
        "room_door_limits",
        "required_room_access",
    ),
    geometry: GeometryConfig = GeometryConfig(),
    dimensions: DimensionConfig = DimensionConfig(),
    interior_doors: InteriorDoorConfig = InteriorDoorConfig(),
    policy: FeaturePolicy = FeaturePolicy(),
    objective: ObjectiveConfig = ObjectiveConfig(),
    solver: SolverConfig = SolverConfig(),
)
```

The config name must be non-empty; feature and constraint IDs must be unique.
`shared_placement` **and** `required_room_access` are structural constraints and cannot
be disabled. `room_door_limits` remains selectable.

`ObjectiveConfig.tier_order` defaults to:

```python
(
    "other_interior",
    "preferred_hallway",
    "bathroom_hallway",
    "attached_bathroom",
    "window",
    "secondary_entrance",
    "main_entrance",
)
```

Tier IDs must be unique.

## Required room access behavior

For a non-empty floor plan, `required_room_access` enforces exactly one selected main
entrance and exactly one full-width secondary entrance on an eligible exterior wall.
The secondary entrance room must be reachable from the main entrance. Secondary wall
direction is preferred before room type. Every room whose type is in `required_access_room_types` must be reachable
from that entrance through selected doors. A local isolated pair of rooms does not
satisfy this rule merely because those two rooms have a door between them.

This is a **hard feasibility condition**, not an objective preference. If the
combination of `allowed_room_pairs`, door caps, room geometry, available walls, or
other hard constraints cannot produce a connected required-access network, the solve
returns `INFEASIBLE`.

Windows and other non-required optional opening demands may still remain unselected.

## Recommended values

Start with `DEFAULT_OPENING_CONFIG` unless the project's access policy requires
different room pairs/caps. Keep the built-in `required_room_access` constraint enabled.
For reproducible tests, the shipped opening solver already uses one worker and seed
`0`.

## Outputs

```python
OpeningGenerationResult(
    status: OpeningGenerationStatus,
    floor_plan: FloorPlan | None,
    profile_name: str,
    message: str,
)
```

Status values are:

- `OPTIMAL='optimal'`
- `FEASIBLE='feasible'`
- `INFEASIBLE='infeasible'`
- `MODEL_INVALID='model_invalid'`
- `UNKNOWN='unknown'`
- `INVALID_INPUT='invalid_input'`

`.solved` requires a solution status and a non-`None` floor plan.

`OpeningGenerationExecution` is
`FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`. `details=None` in
PRODUCTION. DEBUG diagnostics include raw solver status/timing/objective statistics,
wall count, demand/candidate/selected counts, applied constraint IDs, objective terms,
and structured `OpeningIssue` values.

DEBUG issues can identify conditions such as no main-entrance or secondary-entrance candidate, a
required-access room with no door candidate, an optional demand with no candidate, an
unselected optional demand, an undersized exterior door, or `reduced_preferred_clearance`
with requested and actual clearance at each end.

The solved result contains a **copy** of the source floor plan with generated
`FloorPlanOpening` objects.

## Errors / failure conditions

Invalid source floor geometry is returned as `INVALID_INPUT`, with no plan and, in
DEBUG, an `invalid_input` issue. Infeasibility/model/unknown outcomes are returned
statuses. Invalid configurations, duplicate/unknown feature registrations, unknown
constraint IDs, and other generation contract failures raise the
`OpeningGenerationError` family. `OpeningConfigurationError` is exported directly.

## Usage example

This example uses the shared `rectangle` helper and a three-room plan with sufficient
wall lengths for the default opening policy.

```python
from fpg_core.domain import FloorPlan, FloorPlanRoom, RoomId, RoomType
from fpg_core.floor_plan_openings import (
    DEFAULT_OPENING_CONFIG,
    OpeningGenerationRequest,
    generate_openings,
)

opening_source = FloorPlan(
    boundary=rectangle(0, 0, 60, 20),
    rooms=[
        FloorPlanRoom(RoomId("living"), RoomType.LIVING_ROOM, "Living",
                      rectangle(20, 0, 40, 20)),
        FloorPlanRoom(RoomId("bedroom"), RoomType.BEDROOM, "Bedroom",
                      rectangle(0, 0, 20, 20)),
        FloorPlanRoom(RoomId("kitchen"), RoomType.KITCHEN, "Kitchen",
                      rectangle(40, 0, 60, 20)),
    ],
)
execution = generate_openings(
    OpeningGenerationRequest(
        floor_plan=opening_source,
        config=DEFAULT_OPENING_CONFIG,
    )
)
if not execution.result.solved:
    raise RuntimeError(execution.result.message)
plan_with_openings = execution.result.floor_plan
```

## Important behavioral notes

The source plan is never mutated. `allowed_room_pairs` fully owns interior connection
compatibility. Required door access is now mandatory in valid configurations. Door
placement uses the resolved interior policy; wall-end placement uses room-type priority
and bathroom doors default to centered placement. Windows remain center-oriented. Run opening generation after geometry-changing post-processing if the
openings must remain aligned with the final room boundaries.


## Warnings / diagnostics

Expected generation outcomes are represented by `OpeningGenerationStatus` and `OpeningGenerationResult.message`. In `DEBUG`, `OpeningDiagnostics.issues` contains structured `OpeningIssue(code, message, feature_id, demand_id, wall_id)` records together with solver/search counts, selected counts, applied constraints, objective terms, and CP-SAT diagnostics. `PRODUCTION` omits diagnostics. Configuration/input exceptions remain raised errors.

## Public Export Inventory

### `fpg_core.floor_plan_openings` exports (23)

| Export | Kind | Exact contract/value | Coverage |
|---|---|---|---|
| `generate_openings` | function | `generate_openings(request: 'OpeningGenerationRequest', *, registry: 'OpeningFeatureRegistry \| None' = None, mode: 'ExecutionMode' = <ExecutionMode.PRODUCTION: 'production'>) -> 'OpeningGenerationExecution'` | Generate openings on a finalized floor plan without mutating it. |
| `DimensionConfig` | dataclass/contract | `(door_width: 'float' = 10.0, window_width: 'float' = 16.0, minimum_shared_wall: 'float' = 10.0) -> None` | DimensionConfig(door_width: 'float' = 10.0, window_width: 'float' = 16.0, minimum_shared_wall: 'float' = 10.0) |
| `FeaturePolicy` | dataclass/contract | Room pairs, connection limits, room-specific window policies, and priorities. | See FeaturePolicy above. |
| `FloorPlanOpeningsConfig` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits', 'required_room_access'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>, interior_doors: 'InteriorDoorConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
| `InteriorDoorConfig` | dataclass/contract | Default policy and ordered room-type overrides. | See interior door policy above. |
| `InteriorDoorPolicy` | dataclass/contract | Width, preferred and minimum clearances, minimum wall and placement preference. | See interior door policy above. |
| `WindowPolicy` | dataclass/contract | Width, target count, preferred and minimum corner clearances. | See window policy above. |
| `GeometryConfig` | dataclass/contract | `(coordinate_scale: 'int' = 10, tolerance: 'float' = 1e-06, corner_clearance: 'float' = 5.0, window_spacing: 'float' = 5.0) -> None` | GeometryConfig(coordinate_scale: 'int' = 10, tolerance: 'float' = 1e-06, corner_clearance: 'float' = 5.0, window_spacing: 'float' = 5.0) |
| `ObjectiveConfig` | dataclass/contract | Ordered objective tier IDs. | See FloorPlanOpeningsConfig above. |
| `SolverConfig` | dataclass/contract | `(max_time_seconds: 'float' = 10.0, num_search_workers: 'int' = 1, random_seed: 'int' = 0, cp_model_presolve: 'bool' = True, log_search_progress: 'bool' = False) -> None` | SolverConfig(max_time_seconds: 'float' = 10.0, num_search_workers: 'int' = 1, random_seed: 'int' = 0, cp_model_presolve: 'bool' = True, log_search_progress: 'bool' = False) |
| `OpeningDiagnostics` | dataclass/contract | `(raw_status: 'str', wall_time_seconds: 'float' = 0.0, objective_value: 'float \| None' = None, best_objective_bound: 'float \| None' = None, conflicts: 'int' = 0, branches: 'int' = 0, analyzed_wall_count: 'int' = 0, demand_counts: 'Mapping[str, int]' = <factory>, candidate_counts: 'Mapping[str, int]' = <factory>, selected_counts: 'Mapping[str, int]' = <factory>, applied_constraints: 'tuple[str, ...]' = (), objective_terms: 'tuple[str, ...]' = (), issues: 'tuple[OpeningIssue, ...]' = ()) -> None` | OpeningDiagnostics(raw_status: 'str', wall_time_seconds: 'float' = 0.0, objective_value: 'float \| None' = None, best_objective_bound: 'float \| None' = None, conflicts: 'int' = 0, branches: 'int' = 0, analyzed_wall_count: 'int' = 0, demand_counts: 'Mapping[str, int]' = <factory>, candidate_counts: 'Mapping[str, int]' = <factory>, selected_counts: 'Mapping[str, int]' = <factory>, applied_constraints: 'tuple[str, ...]' = (), objective_terms: 'tuple[str, ...]' = (), issues: 'tuple[OpeningIssue, ...]' = ()) |
| `OpeningGenerationExecution` | constant/type alias | `_GenericAlias instance` | Documented in the corresponding feature/shared section. |
| `OpeningGenerationRequest` | dataclass/contract | `(floor_plan: 'FloorPlan', config: 'FloorPlanOpeningsConfig') -> None` | OpeningGenerationRequest(floor_plan: 'FloorPlan', config: 'FloorPlanOpeningsConfig') |
| `OpeningGenerationResult` | dataclass/contract | `(status: 'OpeningGenerationStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') -> None` | OpeningGenerationResult(status: 'OpeningGenerationStatus', floor_plan: 'FloorPlan \| None', profile_name: 'str', message: 'str') |
| `OpeningGenerationStatus` | enum | `OPTIMAL='optimal'; FEASIBLE='feasible'; INFEASIBLE='infeasible'; MODEL_INVALID='model_invalid'; UNKNOWN='unknown'; INVALID_INPUT='invalid_input'` | Documented in the corresponding feature/shared section. |
| `OpeningIssue` | dataclass/contract | `(code: 'str', message: 'str', feature_id: 'str \| None' = None, demand_id: 'str \| None' = None, wall_id: 'str \| None' = None) -> None` | OpeningIssue(code: 'str', message: 'str', feature_id: 'str \| None' = None, demand_id: 'str \| None' = None, wall_id: 'str \| None' = None) |
| `DEFAULT_OPENING_CONFIG` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling opening generation behavior. |
| `DEFAULT_OPENING_PROFILE` | dataclass/contract | `constructor has no separately inspectable signature` | Reusable configuration controlling opening generation behavior. |
| `OpeningGenerationProfile` | dataclass/contract | `(name: 'str', enabled_features: 'tuple[str, ...]' = ('interior_doors', 'exterior_doors', 'windows'), enabled_constraints: 'tuple[str, ...]' = ('shared_placement', 'room_door_limits', 'required_room_access'), geometry: 'GeometryConfig' = <factory>, dimensions: 'DimensionConfig' = <factory>, policy: 'FeaturePolicy' = <factory>, objective: 'ObjectiveConfig' = <factory>, solver: 'SolverConfig' = <factory>, interior_doors: 'InteriorDoorConfig' = <factory>) -> None` | Reusable configuration controlling opening generation behavior. |
| `OpeningFeatureRegistry` | class/interface/registry | `() -> 'None'` | Documented in the corresponding feature/shared section. |
| `create_default_registry` | function | `create_default_registry() -> 'OpeningFeatureRegistry'` | Documented in the corresponding feature/shared section. |
| `OpeningConfigurationError` | exception | `constructor has no separately inspectable signature` | Raised for programmer-facing configuration or registry errors. |
| `OpeningGenerationError` | exception | `constructor has no separately inspectable signature` | Base class for opening-generation failures. |

## API Compatibility

This document targets the current repository source tree, including entries listed as `Unreleased` in `CHANGELOG.md`. Package-wide release/version rules and the current metadata state are documented in [API_GUIDE.md](../API_GUIDE.md#api-versioning-and-compatibility).
