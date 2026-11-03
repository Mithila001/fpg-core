# Floor-plan preprocessing

Public entry point: `prepare_generation_input(PreprocessingInput(request=..., config=...), mode=...)` from `fpg_core.floor_plan_preprocessing`.

## Responsibilities

- Normalize room requests and names, enforce configured mandatory/count/size/relation policies, and select a whole-project-unit floor inside the supplied limits.
- Build `FloorPlanGenerationSpec`, the exact centered `ResolvedCandidateGrid`, and `HallwayRoomCountRange`.
- Return `FeatureExecution[PreparedGenerationInput, PreprocessingReport]`; use `execution.result` for downstream processing, and `DEBUG` for decision/normalization reports.

`PreprocessingRequest` contains `floor_limits`, `aspect_ratio`, and requested rooms. `PreprocessingConfig` is consumer-provided reference/policy data; key inputs include `room_count_rules`, `room_sizes`, `room_relations`, `mandatory_room_types`, `floor_area_buffer`, `hallway_area_buffer`, `hallway_min_width`, `candidate_search_grid_spacing`, `max_hallway_room_count`, and `max_aspect_residual_units`.

## Grid contract

The grid comes from the selected floor, not from Candidate Search:

```text
grid_width  = floor_width  - floor_width  % spacing
grid_length = floor_length - floor_length % spacing
origin_x    = (floor_width  - grid_width)  / 2
origin_y    = (floor_length - grid_length) / 2
```

Spacing is a positive **even** integer; the floor must accommodate at least two spacing intervals per axis. For a 121 x 83 floor with spacing 6, the grid covers 120 x 78 from origin `(0.5, 2.5)`. The outer grid nodes exist for routing but **cannot host room hints**. Search receives precisely this grid; do not reconstruct it in downstream modules.

## Hallway identity is decided in two stages

Preprocessing reserves concrete hallway IDs (for example `hallway_1`, `hallway_2`, `hallway_3`) up to the configured maximum. The allowed count is `1..max_hallway_room_count`. Each search trial activates a subset by choosing a single hallway count; circulation may subsequently remove unused/redundant hallway hints.

**Never send `prepared.generation_spec` directly to the solver after search**: it still contains all potential hallway rooms. First call:

```python
active_spec = prepared.generation_spec_for_candidate(cleaned_candidate)
```

This validates grid/room IDs, retains all requested non-hallway rooms, includes only candidate-selected hallways, and removes relations to inactive rooms. `candidate_search_space` is a compatibility view; `candidate_grid` is authoritative.

Sources: `floor_plan_preprocessing/preparation.py`, `contracts.py`, `config.py`, `business_rules.py`, `normalization.py`.
