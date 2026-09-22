# Floor Plan Openings

Analyzes a finalized floor plan and uses CP-SAT to place interior doors, exterior doors, and windows without mutating the source plan.

## Public API

```python
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_openings.api import (
    DEFAULT_OPENING_CONFIG,
    OpeningGenerationRequest,
    generate_openings,
)

execution = generate_openings(
    OpeningGenerationRequest(
        floor_plan=floor_plan,
        config=DEFAULT_OPENING_CONFIG,
    ),
    mode=ExecutionMode.DEBUG,
)

floor_plan_with_openings = execution.result.floor_plan
```

The supported operation is `generate_openings(...)` from `fpg_core.floor_plan_openings.api`.

## Inputs

`OpeningGenerationRequest` separates request-specific processing input from reusable configuration:

```python
OpeningGenerationRequest(
    floor_plan=floor_plan,
    config=DEFAULT_OPENING_CONFIG,
)
```

- `floor_plan: FloorPlan`: finalized floor plan. It must not already contain openings.
- `config: FloorPlanOpeningsConfig`: reusable opening-generation configuration.
- `registry: OpeningFeatureRegistry | None`: optional extension registry passed to `generate_openings(...)`.
- `mode: ExecutionMode`: production or debug execution.

## Configuration

`FloorPlanOpeningsConfig` contains:

- `name`: configuration/preset name.
- `enabled_features`: opening-demand feature IDs.
- `enabled_constraints`: model constraint IDs. `shared_placement` and `required_room_access` are structural and cannot be disabled.
- `geometry: GeometryConfig`: coordinate scaling, tolerance, corner clearance, and window spacing.
- `dimensions: DimensionConfig`: door width, window width, and minimum shared-wall length.
- `policy: FeaturePolicy`: architectural connection/access/placement policy.
- `objective: ObjectiveConfig`: CP-SAT objective tier ordering.
- `solver: SolverConfig`: solver limits and deterministic settings.

### Interior door connection policy

`FeaturePolicy.allowed_room_pairs` is authoritative. The feature does not silently allow hallway connections or impose a special attached-bathroom pairing rule.

The default configuration explicitly contains the legacy-compatible allowed pairs, including:

```python
(RoomType.BEDROOM, RoomType.ATTACHED_BATHROOM)
(RoomType.BEDROOM, RoomType.HALLWAY)
(RoomType.BATHROOM, RoomType.HALLWAY)
# ...other configured pairs
```

A consumer can allow a different attached-bathroom relation directly:

```python
from dataclasses import replace
from fpg_core.domain import RoomType
from fpg_core.floor_plan_openings.api import DEFAULT_OPENING_CONFIG

policy = DEFAULT_OPENING_CONFIG.policy
custom_policy = replace(
    policy,
    allowed_room_pairs=policy.allowed_room_pairs
    + ((RoomType.ATTACHED_BATHROOM, RoomType.HALLWAY),),
)
custom_config = replace(
    DEFAULT_OPENING_CONFIG,
    name="custom_openings",
    policy=custom_policy,
)
```

Pair order does not matter. Duplicate logical pairs are rejected.

### Required room access

`FeaturePolicy.required_access_room_types` defines which room types must be reachable through the generated door network.

By default all built-in room types are required-access types.

The `required_room_access` hard constraint enforces:

1. A non-empty floor plan has exactly one selected main entrance.
2. Every configured required-access room must be connected to that entrance through selected doors.
3. A local isolated pair of rooms does not satisfy access merely because the two rooms have a door between them.

Therefore required door accessibility is a feasibility condition, not an objective preference. If the configured room-pair policy, door caps, geometry, or available walls cannot produce a connected access network, the result is `INFEASIBLE`.

Windows and non-required secondary/extra openings can still remain optional objective choices.

### Door placement priority

Doors prefer room corners/wall ends instead of wall centers.

`FeaturePolicy.door_placement_priority` assigns a non-negative priority to room types. Higher values mean that room's usable corner preference dominates the other connected room when choosing which end of a shared wall to favor.

Default examples:

```python
(RoomType.BEDROOM, 100)
(RoomType.BATHROOM, 100)
(RoomType.KITCHEN, 80)
(RoomType.LIVING_ROOM, 20)
(RoomType.HALLWAY, 10)
```

For a Bedroom-Living shared wall, the solver first chooses the wall end nearest a Bedroom corner. If both ends are equivalent for the Bedroom, the Living Room corner distance is used as the tie-breaker. The opening is then optimized as close as practical to that selected end while respecting:

- `GeometryConfig.corner_clearance`,
- opening width,
- wall bounds,
- no-overlap constraints,
- window spacing,
- other hard model constraints.

This rule applies to doors. Windows retain center-oriented placement behavior.

### Door caps

`FeaturePolicy.room_door_caps` limits selected shared-wall doors incident to each room type.

There is no longer a Bedroom/Attached-Bathroom-specific cap implementation. The configured cap is applied uniformly by room type.

### Other policy fields

`FeaturePolicy` also provides:

- `secondary_room_priority`
- `window_room_types`
- `main_side_priority`
- `secondary_side_priority`
- `window_side_priority`

## Execution modes

- `ExecutionMode.PRODUCTION`: normal result only.
- `ExecutionMode.DEBUG`: also returns wall, demand, candidate, solver, constraint, objective, and issue diagnostics.

DEBUG issues can identify cases such as:

- no main-entrance candidate,
- a required-access room with no door candidate,
- an optional demand with no candidate,
- an unselected optional demand,
- an undersized exterior door.

## Outputs

The API returns `OpeningGenerationExecution`, an alias of `FeatureExecution[OpeningGenerationResult, OpeningDiagnostics]`.

- `result`: status, optional generated floor plan, configuration name in `profile_name`, and message.
- `details`: `None` in production; `OpeningDiagnostics` in debug.
- `metadata`: execution mode and duration.

`OpeningGenerationStatus` can be `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`, or `INVALID_INPUT`.

The source `FloorPlan` is not mutated. A solved result contains a copied floor plan with generated openings.

## Compatibility note

This update intentionally changes opening feasibility:

- `required_room_access` must now be present in `enabled_constraints`.
- Required rooms must be connected to one main entrance.
- `allowed_room_pairs` now fully controls interior room-type compatibility; hallway and attached-bathroom exceptions are no longer hidden in implementation code.
- Door placement is edge/corner-oriented instead of center-oriented.
- Room door caps are applied uniformly rather than using Bedroom/Attached-Bathroom special handling.

Consumers that explicitly construct `enabled_constraints` or `FeaturePolicy` should update those configurations accordingly.

## Extension Points

`OpeningFeatureRegistry` supports custom opening-demand features. Configuration selects feature IDs and built-in constraint IDs; callers should register custom features before enabling their IDs.

## AI Instructions

- Keep this README synchronized with the public API and contracts.
- Keep request input and reusable configuration separate.
- Keep wall analysis, OR-Tools models, and extraction private.
- Preserve the non-mutating API and structured statuses.
- Document changes to inputs, outputs, configuration, and DEBUG details.
- Do not document private implementation as supported API.
- Do not import another feature's internal modules.
