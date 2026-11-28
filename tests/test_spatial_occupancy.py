from fpg_core.candidate_scoring import (
    CandidateScoringInput,
    EvaluatorCategory,
    EvaluatorKey,
    EvaluatorRule,
    ScoringConfig,
    create_default_registry,
    evaluate_candidate,
)
from fpg_core.domain import (
    CandidateMap,
    CandidatePoint,
    ExecutionMode,
    FloorPlanGenerationSpec,
    FloorSpec,
    ResolvedCandidateGrid,
    RoomId,
    RoomSizeSpec,
    RoomSpec,
    RoomType,
)


def _score(points, *, area=400):
    grid = ResolvedCandidateGrid(
        x_positions=tuple(range(0, 101, 10)), y_positions=tuple(range(0, 101, 10))
    )
    rooms = tuple(
        RoomSpec(
            RoomId(f"r{i}"),
            RoomType.BEDROOM,
            f"Room {i}",
            RoomSizeSpec(1, 30, area, area),
        )
        for i in range(len(points))
    )
    spec = FloorPlanGenerationSpec(FloorSpec(100, 100), rooms, ())
    candidate = CandidateMap(
        grid,
        tuple(
            CandidatePoint(room.id, x, y, room.room_type)
            for room, (x, y) in zip(rooms, points, strict=True)
        ),
    )
    config = ScoringConfig(
        (EvaluatorRule(EvaluatorKey("spatial_occupancy"), EvaluatorCategory.QUALITY),)
    )
    result = evaluate_candidate(
        CandidateScoringInput(spec, candidate),
        registry=create_default_registry(),
        config=config,
        mode=ExecutionMode.DEBUG,
    )
    return result.evaluator_results[0]


def test_occupancy_distinguishes_clear_overlap_and_boundary_overflow():
    clear = _score([(20, 20), (80, 80)]).raw_score
    overlap = _score([(20, 20), (30, 20)]).raw_score
    overflow = _score([(10, 50)]).raw_score
    assert clear == 100
    assert 0 < overlap < clear
    assert 0 < overflow < clear


def test_overlap_union_does_not_double_count_neighbors():
    pair = _score([(50, 50), (40, 50)]).details["score"]
    triple = _score([(50, 50), (40, 50), (60, 50)]).details["rooms"][0]["score"]
    assert triple <= pair
    assert triple >= 0
