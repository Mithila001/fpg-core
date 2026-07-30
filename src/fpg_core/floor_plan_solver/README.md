# Floor Plan Solver

`src/fpg_core/floor_plan_solver` is the CP-SAT-only part of the floor-plan
pipeline. It intentionally does not own Candidate Search, Candidate Scoring,
post-processing, openings, API validation, persistence, or job management.

## Public flow

```text
FloorPlanGenerationSpec
+ GenerationProfile
+ optional Candidate Search hints
+ optional existing FloorPlan
        ↓
FloorPlanSolver
        ↓
FloorPlanSolveResult
```

The solver uses the shared application types through `domain.py`. If the shared
types are exported from a different module, only that import seam should need to
change.

## Structural invariants

The following rules are always applied and cannot be disabled by profiles:

- room variables remain inside the floor bounds,
- every supplied room is present,
- width, length, and area stay within each `RoomSpec`,
- rooms do not overlap.

These are model invariants rather than profile-level business constraints.

## Profiles

Profiles select:

- optional hard constraints,
- soft constraints and their weights,
- integer coordinate scale,
- OR-Tools runtime settings,
- Candidate Search or existing-layout seed behavior.

Built-in profiles:

- `INITIAL_GENERATION_PROFILE`
- `REFINEMENT_A_PROFILE`
- `REFINEMENT_B_PROFILE`

The default numerical values are starting values and should be calibrated for
the project. They are centralized in `DefaultProfileSettings`.

## Basic usage

```python
from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    INITIAL_GENERATION_PROFILE,
    RoomPlacementHint,
    generate_floor_plan,
)

result = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=generation_spec,
        profile=INITIAL_GENERATION_PROFILE,
        candidate_hints=(
            RoomPlacementHint(room_id=bedroom_id, x=2.0, y=4.0),
        ),
    )
)

if result.solved:
    floor_plan = result.floor_plan
else:
    # The surrounding pipeline decides whether to retry or preserve a previous
    # layout. The solver does not silently substitute fallback geometry.
    handle_unsolved_result(result)
```

Refinement uses the same entry point:

```python
from fpg_core.floor_plan_solver import (
    FloorPlanSolveRequest,
    REFINEMENT_A_PROFILE,
    generate_floor_plan,
)

refined = generate_floor_plan(
    FloorPlanSolveRequest(
        specification=generation_spec,
        profile=REFINEMENT_A_PROFILE,
        existing_floor_plan=initial_floor_plan,
    )
)
```

## Custom profile

```python
from fpg_core.floor_plan_solver import (
    HardConstraintUse,
    REFINEMENT_A_PROFILE,
    SoftConstraintUse,
)

custom_refinement = (
    REFINEMENT_A_PROFILE
    .without_constraints("center_proximity")
    .with_hard_constraints(
        HardConstraintUse(
            "room_size_hierarchy",
            {
                "anchor_room_types": ("living_room",),
                "ratios_by_room_type": {
                    "bedroom": {"min_ratio": 0.35, "max_ratio": 0.8},
                },
            },
        )
    )
    .with_soft_constraints(
        SoftConstraintUse("dead_space", weight=8),
    )
)
```

## Adding a hard constraint

```python
class MyHardConstraint:
    key = "my_hard_constraint"

    def apply(self, context, settings) -> None:
        # Add mandatory CP-SAT rules only.
        ...
```

Register it once:

```python
registry = build_default_registry()
registry.register_hard(MyHardConstraint())
```

Then reference its key from a profile. Hard constraints must not run the solver,
change the objective, read global configuration, or convert project-domain
data.

## Adding a soft constraint

```python
class MySoftConstraint:
    key = "my_soft_constraint"

    def build_penalties(self, context, settings):
        return (
            PenaltyTerm(name="my_penalty", expression=non_negative_var),
        )
```

Soft constraints return non-negative penalty terms. The model builder is the
only component that applies profile weights and calls `Minimize`.

## Business-rule boundary

The specification-building layer should decide which rooms exist and which
room relationships are hard or soft. The solver expresses those decisions as
CP-SAT rules. It does not automatically create living rooms, hallways,
verandas, extenders, or auxiliary outdoor rooms.

## Included constraints

Hard:

- aspect ratio,
- hard room relations,
- minimum floor coverage,
- hallway connectivity,
- front-anchor ordering,
- generic boundary placement,
- configurable room-size hierarchy.

Soft:

- soft room relations,
- center/front proximity,
- internal dead space,
- seed stability,
- bathroom depth,
- mandatory room presence.

Legacy extender rules, auxiliary veranda geometry, envelope staircase logic,
shared-wall-count rules, and specialized facade penalties are deliberately not
copied into this first clean implementation. They can be added independently
through the same constraint contracts after their desired behavior is
confirmed.
