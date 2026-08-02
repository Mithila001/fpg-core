# Candidate Scoring

Scores candidate room hint arrangements before floor-plan solving. Critical evaluators can reject a candidate; quality evaluators contribute to a normalized 0-100 score.

## Guide

### Public API

```python
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    evaluate_candidate,
)
from fpg_core.domain import ExecutionMode

result = evaluate_candidate(
    CandidateScoringInput(
        specification=generation_spec,
        candidate=circulation_execution.result.points,
        hallway_classifications=(
            circulation_execution.result.hallway_classifications
        ),
    ),
    registry=registry,
    config=config,
    mode=ExecutionMode.PRODUCTION,
)
```

### Inputs

- `CandidateScoringInput.specification`: shared `FloorPlanGenerationSpec`.
- `CandidateScoringInput.candidate`: supported candidate object or point collection.
- `CandidateScoringInput.hallway_classifications`: optional shared hallway tags. Empty means no hallway traffic restriction.
- `EvaluatorRegistry`, `ScoringConfig`, and optional `ScoringContextFactory` configure the evaluator pipeline.

### Zone suitability configuration

The built-in 3x3 rules remain available as `DEFAULT_VALID_ZONES`. A caller can replace them through the typed `ZoneSuitabilityConfig`:

```python
from fpg_core.candidate_scoring import (
    ZoneSuitabilityConfig,
    create_default_config,
)
from fpg_core.domain import RoomType

zone_config = ZoneSuitabilityConfig(
    grid_size=3,
    falloff_multiplier=1.5,
    valid_zones={
        RoomType.KITCHEN: ((1, 3), (2, 3), (3, 3)),
        RoomType.LIVING_ROOM: ((1, 1), (2, 1), (3, 1)),
        RoomType.BEDROOM: ((1, 2), (2, 2), (3, 2)),
    },
)

config = create_default_config(
    zone_suitability_config=zone_config,
)
```

For a custom `ScoringConfig`, pass the same object through the zone evaluator rule as `settings={"zone_config": zone_config}`.

### Relationship quality

Relationship quality performs one orthogonal grid-routing pass. It does not invoke Candidate Circulation and does not import that feature.

Configure it with:

```python
from fpg_core.candidate_scoring import RelationshipQualityConfig
from fpg_core.domain import (
    CirculationGrid,
    CirculationRouteRule,
    CirculationTrafficClass,
    DestinationSelection,
    GridRoutingCostProfile,
    RoomType,
)

routing_config = RelationshipQualityConfig(
    grid=CirculationGrid(width=100, length=80, scale=10),
    costs=GridRoutingCostProfile(
        empty_node_cost=2,
        traversable_hint_node_cost=1,
        turn_cost=0.25,
        perimeter_bias_max_cost=0.2,
    ),
    route_rules=(
        CirculationRouteRule(
            id=1,
            name="Living to bedrooms",
            source_room_type=RoomType.LIVING_ROOM,
            destination_room_type=RoomType.BEDROOM,
            destination_selection=DestinationSelection.ALL_MATCHING,
            traffic_class=CirculationTrafficClass.PRIVATE,
            allowed_transit_room_types=(),
            importance_weight=1,
        ),
    ),
)

settings = {"routing_config": routing_config}
```

Hallway restrictions apply only when a matching hallway classification is provided:

- public routes may use `PUBLIC`, `MIXED`, `UNCLASSIFIED`, or untagged hallways;
- private routes may use `PRIVATE`, `MIXED`, `UNCLASSIFIED`, or untagged hallways;
- `UNUSED` hallways are blocked.

Each route receives:

```text
path_efficiency_score = Manhattan reference cost / routed cost x 100
```

The evaluator score is the importance-weighted average across expected routes. Missing routes contribute zero and produce `RELATION_PATH_MISSING` findings.

### Outputs

`PRODUCTION` returns evaluator scores and findings. Evaluator `metrics` remain empty and evaluator `details` is `None`.

`DEBUG` additionally returns metrics and typed evaluator details for diagnostics, R&D, reports, and visualization:

- `ZoneSuitabilityDetails`
- `SpatialDistributionDetails`
- `ExteriorClearanceDetails`
- `RelationshipQualityDetails`

### Errors and Expected Behaviour

Configuration, input, registry, and evaluator-contract problems use Candidate Scoring errors. By default evaluator failures are converted into evaluator results; `raise_on_evaluator_error=True` propagates them.

Relationship quality remains opt-in and is not added to the default registry/config because its grid, costs, and route rules are project-specific.

## AI Instructions

- Keep Candidate Scoring independent from Candidate Circulation implementation.
- Share only reusable contracts through `fpg_core.domain`.
- Preserve the evaluator result contract and 0-100 score scale.
- Keep evaluator metrics and details DEBUG-only; production keeps scores and findings.
