# Floor Plan Solver

Builds and solves a CP-SAT floor-plan model from request-specific generation data and an explicit reusable solver configuration.

## Guide

### Public API

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

### Inputs

`FloorPlanSolveRequest` keeps processing data separate from configuration:

```text
FloorPlanSolveRequest
├── specification        # processing input
├── candidate_hints      # processing input
├── existing_floor_plan  # processing input
└── config               # solver configuration
```

Processing input:

- `specification: FloorPlanGenerationSpec` describes the floor and rooms that must be solved.
- `candidate_hints: tuple[RoomPlacementHint, ...]` optionally provides candidate-search seed geometry.
- `existing_floor_plan: FloorPlan | None` optionally provides an existing layout for refinement configurations.

Configuration:

- `config: FloorPlanSolverConfig` controls how solving is performed.
- `config.hard_constraints` selects mandatory solver constraints and their settings.
- `config.soft_constraints` selects objective preferences, weights, and settings.
- `config.solver` controls OR-Tools runtime limits, workers, random seed, logging, presolve, and relative gap.
- `config.preparation` controls conversion into CP-SAT integer units.
- `config.seed` controls which optional processing input is used as solver seed geometry and how strongly it constrains the solve.

Built-in named profiles such as `INITIAL_GENERATION_PROFILE`, `REFINEMENT_A_PROFILE`, and `REFINEMENT_B_PROFILE` are ready-made `FloorPlanSolverConfig` values. A profile is therefore a configuration preset, not processing input.

`GenerationProfile` remains available as a backward-compatible alias of `FloorPlanSolverConfig`. New code should prefer `FloorPlanSolverConfig`.

`ExecutionMode.PRODUCTION` is the default. `ExecutionMode.DEBUG` enables solver diagnostics.

### Outputs

The API returns `FloorPlanSolveExecution`, an alias of `FeatureExecution[FloorPlanSolveResult, SolverDiagnostics]`.

- `result` always contains the status, optional floor plan, configuration/profile name, and status message.
- `details` is `None` in `PRODUCTION`.
- In `DEBUG`, `details` contains raw solver status, timing, objective information, search statistics, applied constraints, and penalty terms.
- `metadata` contains the execution mode and total duration.

`FloorPlanSolveResult.profile_name` is intentionally retained for public/serialized compatibility even though the selected profile is now passed through the explicit `config` field.

### Errors and Expected Behaviour

Invalid specifications, configurations, required seeds, or constraint IDs raise `FloorPlanSolverError` subclasses before solving. Infeasible and interrupted solver outcomes are returned as statuses. Randomness is controlled by `config.solver.random_seed`.

Changing from the old request contract requires replacing:

```python
FloorPlanSolveRequest(..., profile=my_profile)
```

with:

```python
FloorPlanSolveRequest(..., config=my_profile)
```

### Extension Points

- Create a custom `FloorPlanSolverConfig` to select constraints and runtime settings.
- `HardConstraintUse` and `SoftConstraintUse` configure registered constraints.
- `ConstraintRegistry` supports custom hard and soft constraint registrations.
- `build_default_profiles()` constructs the built-in configuration presets.

## AI Instructions

- Keep processing input and solver configuration clearly separate in the public contract.
- Keep OR-Tools objects and implementation modules private.
- Keep hard constraints separate from soft objective preferences.
- Keep this README synchronized with public contracts and DEBUG details.
- Do not import another feature's internal modules.
