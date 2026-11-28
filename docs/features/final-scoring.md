# Completed floor-plan scoring

Final scoring is distinct from candidate hint scoring. Call `score_floor_plan(FloorPlanScoringInput(floor_plan=..., specification=..., config=create_default_config()), mode=...)` from `fpg_core.floor_plan_scoring`. This returns `FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]` and does not mutate its inputs.

## Default scoring policy

- **Critical group:** geometry integrity, enclosed voids, and inward recess. Each default critical evaluator requires score `100`. Critical failure can stop later groups.
- **Functional group:** room-size consistency, [Room Relationship Quality](../feature_documentations/floor_plan_scoring.md#room-relationship-quality), living-room balance and bedroom quality. Solver adjacency stays in generation so functional scoring can assess the practical positioning of completed rooms.
- `total_score`, `passed_critical`, and `critical_failure` are production result fields; `DEBUG` gives group/evaluator results, weighted contributions, findings, metrics, and optional visualization data.

Default room-size preferences use the same 12 upper-bound relationships as the solver: bathrooms and attached bathrooms versus bedrooms, living rooms, dining rooms, kitchens and garages, plus bedrooms and kitchens versus living rooms. The largest compared room is measured against the smallest reference room, with a maximum ratio of 1.0. Bedroom largest/smallest spread is separately limited to 25% as a scoring preference.

**Feasibility-aware thresholds:** the room-size evaluator reads permitted area ranges from the supplied generation spec and relaxes impossible ratios to the closest achievable boundary. For example, if living is `200..250` and kitchen is `220..260`, a configured kitchen/living max of `0.80` is infeasible; the effective max becomes `220 / 250 = 0.88`. Penalization is gradual beyond effective thresholds, not a new hard constraint. `RoomAreaAggregation` supports `MIN`, `AVERAGE`, `MAX`, and `TOTAL`.

`LivingRoomBalanceEvaluator` and `BedroomQualityEvaluator` are enabled by default with weight 1 each; the former checks living-area balance and the latter bedroom area compliance and consistency. Bedroom spread also affects room-size consistency. `FloorPlanScoringConfig` defines groups/evaluators and `EvaluatorRegistry` provides custom evaluators. Keep stable evaluator keys and structured finding codes when evolving the feature.

The [inward recess contract](../feature_documentations/floor_plan_scoring.md#inward-recesses)
defines the opening, proportion, and topology rules. The sweep cuts the room
union at boundary coordinates and links empty slices over shared segments.
Using the room union removes internal room seams. The geometry pass returns
the regions and section graph independently of the score limits.

Sources: `floor_plan_scoring/defaults.py`, `manager.py`, `evaluators/room_size_consistency.py`, `types.py`.
