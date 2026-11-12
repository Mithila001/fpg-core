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
| `hallway_connectivity`, `hallway_dimensions`, `hallway_shared_wall` | Hallway anchors, corridor width, and hallway-to-hallway wall overlap cap |
| `front_anchor`, `back_exposure` | Allowed front placement and eligible back-side exposure |
| `garage_placement`, `boundary_placement` | Garage corners and selected boundary rules (veranda front) |

`room_size_hierarchy` is registered for custom configurations but not enabled by the defaults. Hard constraints determine feasibility and may not be relaxed to improve the objective.

The soft objective combines weighted penalties: `room_relations`, `room_size_relations`, `floor_cluster_position`, `dead_space`, `hallway_efficiency`, `bathroom_depth`, `kitchen_back_exposure`, and (in refinement) `seed_stability`.

Built-in profiles: `INITIAL_GENERATION_PROFILE` (candidate hints), `REFINEMENT_A_PROFILE` and `REFINEMENT_B_PROFILE` (existing floor-plan seed, with tighter stabilization). Construct tuned versions using `build_default_profiles(DefaultProfileSettings(...))`; default time limits are 5 seconds initial, 2 seconds per refinement. Maintain bounded solves and configurable seeds.

## Hallway rules that are easy to misunderstand

- A hallway corridor width is constrained to `8..10` project units by default; its *length* is not hard-capped.
- `hallway_shared_wall` limits touching hallway wall overlap to `12` project units by default, not contact at corners.
- `hallway_efficiency` is a **soft penalty**, not a hallway-count/removal mechanism:

```text
cost = (sum hallway area * area_penalty_multiplier)
     + (sum max(0, longest_side - preferred_max_length)
        * excess_length_penalty_multiplier)
```

This cost is multiplied by the `SoftConstraintUse.weight`. Defaults are multipliers `1` and `5`, preferred maximum length `40` project units (4 m), and overall weight `1`. Length above 40 remains legal if hard rules require it. Compatible hallways can be merged later by post-processing; removing entire hallway rooms belongs upstream.

## Results and failures

`execution.result` contains `status`, optional `floor_plan`, `profile_name`, and `message`. Check the status and existence of the plan; infeasible/unknown solver outcomes are returned as statuses, while invalid input/configuration may raise `FloorPlanSolverError` subclasses. `DEBUG` details include raw status, timing, bounds, conflicts, branches, applied constraint IDs, and penalty terms.

Sources: `floor_plan_solver/api.py`, `profiles.py`, `preparation.py`, `builder.py`, `constraints/`, `runner.py`.
