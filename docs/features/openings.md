# Door and window generation

Call `generate_openings(OpeningGenerationRequest(floor_plan=..., config=...), mode=...)` from `fpg_core.floor_plan_openings`. The supplied finalized plan **must not already contain openings**. The source is not mutated; a successful result contains a copied plan with interior doors, exterior doors, and windows.

## Model rules

- Room union exterior rings determine outdoor exposure; shared spans are interior walls and enclosed voids are excluded. Room-type pairs are configurable, with attached bathrooms restricted to bedrooms.
- `shared_placement` and `required_room_access` are structural. Non-empty plans require one main entrance, one full-width secondary entrance and paths from the main entrance to the secondary entrance and required rooms.
- Normal connection caps apply independently of the extra bedroom/attached-bathroom and kitchen/dining connections. Multiple shared spans between the same rooms are alternatives by default.
- Interior door minimum clearances are hard; preferred clearance deficits are minimized before optional selections. Window coverage is preferred, with room-specific width and clearance policies. See the [consumer contract](../feature_documentations/floor_plan_openings.md) for defaults and configuration.

## Outcomes

`OpeningGenerationResult` contains `status`, optional `floor_plan`, `profile_name`, and message. Statuses include `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`, `INVALID_INPUT`. Invalid geometry can produce `INVALID_INPUT` without raising; check result status and plan presence. Configuration problems can raise opening-specific errors.

`ExecutionMode.DEBUG` includes analyzed walls, candidate/demand counts, constraints/objectives, and issue diagnostics. `OpeningFeatureRegistry` extends opening-demand features, not the shared domain schema. Legacy `OpeningGenerationProfile` / `DEFAULT_OPENING_PROFILE` are compatibility names for explicit config presets.

Sources: `floor_plan_openings/config.py`, `analysis.py`, `model.py`, `runner.py`, `features/`, `constraints/`.
