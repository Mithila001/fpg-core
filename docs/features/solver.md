# CP-SAT floor-plan solver

Call `generate_floor_plan(FloorPlanSolveRequest(specification=..., config=..., candidate_hints=..., existing_floor_plan=...), mode=...)` through `fpg_core.floor_plan_solver`. The `FloorPlanSolver` class accepts an optional custom `ConstraintRegistry`.

## Fundamental model invariants

Every room supplied in `FloorPlanGenerationSpec.rooms` must be placed. The solver enforces the floor boundary, room-specific size/area limits, and non-overlap **regardless of optional constraint selection**. No hallway or other supplied room can be removed by solver optimization. Filter the preprocessing template through `generation_spec_for_candidate()` before building the request.

`FloorPlanSolverConfig` separates `hard_constraints`, `soft_constraints`, solver limits, coordinate preparation, and seed policy. Do not expose raw OR-Tools objects in the domain layer.

## Registered constraints and built-in profiles

| Hard constraints used by defaults | Meaning |
| --- | --- |
| `aspect_ratio`, `room_relations` | Per-type shape limits; enforce `HARD` relationships with wall overlap |
| `attached_bathroom_pairing` | One-to-one bedroom/attached-bathroom wall pairing |
| `minimum_coverage` | Required total covered fraction of floor |
| `hallway_connectivity`, `hallway_dimensions`, `hallway_parallel_overlap`, `hallway_shared_wall` | Hallway anchors, corridor width, and hallway-to-hallway wall overlap cap |
| `exterior_wall_exposure`, `living_room_front` | Configured exterior exposure and conditional living-room front exposure |

`room_size_hierarchy` is registered for custom configurations but not enabled by the defaults. Hard constraints determine feasibility and may not be relaxed to improve the objective.

The [solver contract](../feature_documentations/floor_plan_solver.md#authoring-a-soft-constraint) defines the 0?100 combined penalty and 0?10 weight. The soft objective combines weighted penalties: `room_relations`, `room_size_relations`, `floor_cluster_position`, `dead_space`, `hallway_efficiency`, `bathroom_depth`, `exterior_wall_exposure`, and (in refinement) `seed_stability`. Exterior exposure uses unobstructed paths from room walls toward the generation boundary, which need not coincide with the wall. A minimum-length requirement refers to one continuous segment. Only rooms block these paths; FULL_SPAN clearance, openings, and post-processing are separate concerns. Shared CP-SAT geometry allows room policies to compose exposure while keeping their settings configurable. `hallway_efficiency` measures perimeter minus shared walls, a different quantity.

## Exterior-wall exposure design rationale

The generation boundary is the allowed placement envelope, not a claim that every part of its perimeter is an actual building wall. A room set back inside that envelope can still have an outward-facing wall: empty space between it and the boundary does not obstruct exposure. The model therefore traces perpendicular paths outward from the wall, without requiring contact with the boundary. Other rooms are the blockers because the solver models room geometry; empty space is not a room and this rule makes no assumptions about features outside that model.

A whole wall need not be clear to provide useful exterior access. A minimum continuous segment allows partial exposure while preventing disconnected gaps from being added together to meet a threshold. `full_wall` covers only the projection of the selected room wall. A possible `FULL_SPAN` concept would impose clearance across a wider span; it is deferred and is not an alias for `full_wall`.

A single explicit `rules` format avoids hidden translation and makes the active policy visible in each profile. Direct use of the generic constraint removes duplicate delegating classes; invalid old settings and retired keys fail rather than being silently rewritten. Saved development configurations must be replaced with current configurations.

The shared geometry produces reified CP-SAT literals without knowing room types or policy. The rule layer selects rooms, combines conditions and counts matches; configuration defines most of the current behavior. The existing registered hard/soft constraints and objective use those literals, preserving the solver's established feasibility and penalty machinery without a separate constraint engine. This separation permits future room-specific adapters to add behavioral conditions while reusing geometry, but does not implement a new policy framework. The living-room adapter already gates its rules on the absence of a veranda.

The earlier exposure implementations were replaced by shared geometry and configurable rules so the same exposure semantics can be reused. Two intentional behavior changes matter when migrating profiles: back exposure no longer requires boundary contact, and garage side clearance no longer extends beyond the garage wall projection. The former named wrappers have been removed; existing profiles must use the canonical rules. See the [consumer contract](../feature_documentations/floor_plan_solver.md) for migration and rule details.

Opening placement and post-processing are separate stages: solver exposure is neither an opening guarantee nor a guarantee after room geometry changes. Renaming the generation boundary is also outside this implementation; its existing name and containment role remain. These concerns can evolve separately from the solver's exposure predicate.

The solver checks projected room obstructions in the outward direction. Full walls use a pairwise test; a minimum segment starts at the wall edge or the end of a blocker projection, requiring quadratic checks in room count. Per-model caches share repeated exposure and blocker requests. `hallway_efficiency` measures a different quantity: perimeter minus shared walls.

Internally, `constraints.exposure.exposure_literal(context, room, side, minimum)`
returns an exact Boolean for a full wall when `minimum` is `None`, or a segment
of at least the scaled integer length otherwise. `constraints.exposure_rules`
composes literals and selects matching rooms; `exposure_config` validates profile settings without loading OR-Tools. New room requirements can
usually use the generic registered `exterior_wall_exposure` constraint; retain a
room-specific adapter only when it has an additional condition such as the
living-room/veranda rule. Run `tests/floor_plan_solver/test_exposure.py`, the
room-facing tests, the Lab E02A tests, and the Lab Core verifier after changes.

Built-in profiles: `INITIAL_GENERATION_PROFILE` (candidate hints), `REFINEMENT_A_PROFILE` and `REFINEMENT_B_PROFILE` (existing floor-plan seed, with tighter stabilization). Construct tuned versions using `build_default_profiles(DefaultProfileSettings(...))`; default time limits are 5 seconds initial, 2 seconds per refinement. Maintain bounded solves and configurable seeds.

## Hallway rules that are easy to misunderstand

- A hallway corridor width is constrained to `8..10` project units by default; its *length* is not hard-capped.
- `hallway_shared_wall` limits touching hallway wall overlap to `12` project units by default, not contact at corners.
- `hallway_dimensions` caps each hallway?s long dimension at half the matching span of non-hallway rooms by default.
- `hallway_parallel_overlap` caps projected overlap between same-orientation hallway pairs at 40 horizontal and 30 vertical project units, including pairs separated by a gap.
- `hallway_shared_wall` separately limits actual shared wall between touching hallways to 12 units.
- `hallway_efficiency` penalizes total hallway area and exposed hallway wall; the length threshold is no longer part of its objective.

## Results and failures

`execution.result` contains `status`, optional `floor_plan`, `profile_name`, and `message`. Check the status and existence of the plan; infeasible/unknown solver outcomes are returned as statuses, while invalid input/configuration may raise `FloorPlanSolverError` subclasses. `DEBUG` details include raw status, timing, bounds, conflicts, branches, applied constraint IDs, and penalty terms.

Sources: `floor_plan_solver/api.py`, `profiles.py`, `preparation.py`, `builder.py`, `constraints/`, `runner.py`.
