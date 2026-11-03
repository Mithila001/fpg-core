# Completed floor-plan scoring

Final scoring is distinct from candidate hint scoring. Call `score_floor_plan(FloorPlanScoringInput(floor_plan=..., specification=..., config=create_default_config()), mode=...)` from `fpg_core.floor_plan_scoring`. This returns `FeatureExecution[FloorPlanScoringResult, FloorPlanScoringDetails]` and does not mutate its inputs.

## Default scoring policy

- **Critical group:** geometry integrity, required adjacency, enclosed voids, and inward recess. Each default critical evaluator requires score `100`. Critical failure can stop later groups.
- **Functional group:** room-size consistency and kitchen/dining relationship.
- `total_score`, `passed_critical`, and `critical_failure` are production result fields; `DEBUG` gives group/evaluator results, weighted contributions, findings, metrics, and optional visualization data.

Default room-size preferences are soft: largest kitchen at most 80% of largest living room; dining at most 100% of kitchen; largest bedroom at most 90% of largest living room; bedroom largest/smallest spread at most 25%.

**Feasibility-aware thresholds:** the room-size evaluator reads permitted area ranges from the supplied generation spec and relaxes impossible ratios to the closest achievable boundary. For example, if living is `200..250` and kitchen is `220..260`, a configured kitchen/living max of `0.80` is infeasible; the effective max becomes `220 / 250 = 0.88`. Penalization is gradual beyond effective thresholds, not a new hard constraint. `RoomAreaAggregation` supports `MIN`, `AVERAGE`, `MAX`, and `TOTAL`.

`LivingRoomBalanceEvaluator` and `BedroomQualityEvaluator` remain registered/exported for compatibility, but are **not enabled** in the default configuration. `FloorPlanScoringConfig` defines groups/evaluators and `EvaluatorRegistry` provides custom evaluators. Keep stable evaluator keys and structured finding codes when evolving the feature.

Sources: `floor_plan_scoring/defaults.py`, `manager.py`, `evaluators/room_size_consistency.py`, `types.py`.
