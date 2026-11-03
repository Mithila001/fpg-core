# Door and window generation

Call `generate_openings(OpeningGenerationRequest(floor_plan=..., config=...), mode=...)` from `fpg_core.floor_plan_openings`. The supplied finalized plan **must not already contain openings**. The source is not mutated; a successful result contains a copied plan with interior doors, exterior doors, and windows.

## Model rules

- `FloorPlanOpeningsConfig.policy.allowed_room_pairs` is the **sole authority** for interior room-type connections. The algorithm does not silently allow all hallway pairs or special attached-bathroom pairs.
- The default allowed pairs include bedroom/attached-bathroom and several explicit hallway combinations. It does **not** include every logically imaginable pair (for example, kitchen/dining); consumers must align opening policy with hard adjacency requirements.
- `shared_placement` and `required_room_access` are **structural** constraints and cannot be disabled. `required_room_access` requires exactly one selected main entrance for non-empty plans and a connected door path from that entrance to every required-access room. A separate connected island is not sufficient.
- `room_door_caps` applies per room type without hidden exceptions. Door positions favor usable shared-wall ends/corners, prioritized by `door_placement_priority`; windows remain more center-oriented. Hard bounds, clearances, and non-overlap take precedence.
- Defaults: door width `8`, window width `16`, minimum shared wall `10`, window spacing `5` project units. All are policy/configuration, not universal regulations.

## Outcomes

`OpeningGenerationResult` contains `status`, optional `floor_plan`, `profile_name`, and message. Statuses include `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`, `INVALID_INPUT`. Invalid geometry can produce `INVALID_INPUT` without raising; check result status and plan presence. Configuration problems can raise opening-specific errors.

`ExecutionMode.DEBUG` includes analyzed walls, candidate/demand counts, constraints/objectives, and issue diagnostics. `OpeningFeatureRegistry` extends opening-demand features, not the shared domain schema. Legacy `OpeningGenerationProfile` / `DEFAULT_OPENING_PROFILE` are compatibility names for explicit config presets.

Sources: `floor_plan_openings/config.py`, `analysis.py`, `model.py`, `runner.py`, `features/`, `constraints/`.
