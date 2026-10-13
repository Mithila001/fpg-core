from __future__ import annotations

from dataclasses import replace

from custom_test.full_flow.scenario import (
    build_candidate_circulation_config,
    build_candidate_scoring_config,
    build_candidate_search_config,
    build_preprocessing_config,
    build_preprocessing_request,
)

from fpg_core.candidate_circulation import (
    CandidateCirculationInput,
    refine_candidate_circulation,
)
from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.candidate_search import (
    CandidateSearchInput,
    build_candidate_search_targets,
    search_candidates,
)
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_preprocessing import (
    PreprocessingInput,
    prepare_generation_input,
)


def test_candidate_flow_public_contracts_connect() -> None:
    preprocessing = prepare_generation_input(
        PreprocessingInput(
            request=build_preprocessing_request(180.0, 160.0),
            config=build_preprocessing_config(),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert preprocessing.details is not None
    prepared = preprocessing.result

    search_config = replace(build_candidate_search_config(), trial_count=8)
    search = search_candidates(
        CandidateSearchInput(
            targets=build_candidate_search_targets(prepared.generation_spec),
            grid=prepared.candidate_grid,
            hallway_room_count_range=prepared.hallway_room_count_range,
            evaluator=lambda candidate: -sum(
                float(point.x) + float(point.y) for point in candidate.points
            ),
            config=search_config,
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert search.details is not None

    circulation = refine_candidate_circulation(
        CandidateCirculationInput(
            candidate=search.result.candidate,
            config=build_candidate_circulation_config(),
        ),
        mode=ExecutionMode.DEBUG,
    )
    assert circulation.details is not None

    candidate = circulation.result.candidate
    specification = prepared.generation_spec_for_candidate(candidate)
    scoring = evaluate_candidate(
        CandidateScoringInput(
            specification=specification,
            candidate=candidate,
            hallway_classifications=circulation.result.hallway_classifications,
        ),
        registry=create_default_registry(),
        config=build_candidate_scoring_config(),
        mode=ExecutionMode.DEBUG,
    )

    assert 0.0 <= scoring.total_score <= 100.0
    assert scoring.evaluator_results
