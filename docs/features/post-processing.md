# Floor-plan post-processing

`post_process_floor_plan(PostProcessingRequest(floor_plan=..., config=..., specification=...), mode=...)` runs a configured sequence of geometry processors. Unlike several other features, the supplied `FloorPlan` is the **working mutable object**.

## Pipeline and defaults

`INITIAL_GENERATION_PROFILE` runs processors in this order:

1. `remove_placeholder_rooms` (required, validate after)
2. `grid_snap` (required, validate after)
3. `wall_extension`
4. `hallway_merge`
5. `rectilinear_simplification`

The order matters; do not reorder processors based only on names. Each `ProcessorUse` specifies its typed config, `required` status, and `validate_after`. The profile also owns numeric tolerance/grid policy and whether existing openings are rejected. Geometry-changing profiles normally reject input plans with openings, so use post-processing **before** opening generation.

Wall extension identifies unacceptable footprint conditions first, generates bounded
rectangular additions and accepts only measured improvements with hard protections.
The solver configuration and original room specifications are required. Unknown
hard constraints cause conservative rejection. See the [consumer contract](../feature_documentations/floor_plan_post_processing.md).

## Mutation, rollback, and identity

- Successful processors can mutate the source plan. The pipeline snapshots before each processor, restoring on failure.
- Required failure stops the pipeline; optional failure may let later processors continue. The result contains a structured `PipelineStatus`, floor plan, and optional failure.
- `DEBUG` captures per-processor execution, timing, affected room IDs, identity redirects, failure, and rollback. Preserve identity redirects when merging hallways and removing placeholders.
- `PostProcessingProfile` is a compatibility alias for `FloorPlanPostProcessingConfig`; prefer `config=` on requests.

Custom `FloorPlanProcessor` implementations register through `ProcessorRegistry` and declare IDs, typed config, and prerequisites. Keep validators and rollback behavior aligned with every geometry-changing processor.

Sources: `floor_plan_post_processing/profiles.py`, `pipeline.py`, `processors/`, `registry.py`, `validation.py`.
