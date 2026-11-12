from fpg_core.domain.room_size_preferences import DEFAULT_ROOM_SIZE_PAIRS
from fpg_core.floor_plan_solver.constraints.s_room_size_relations import DEFAULT_RULES
from fpg_core.floor_plan_scoring import create_default_config, RoomAreaAggregation


def test_default_solver_and_scoring_relationships_match():
    scoring = next(rule.settings for rule in create_default_config().evaluators
                   if rule.key == 'room_size_consistency')
    assert len(scoring.relation_rules) == len(DEFAULT_RULES) == 12
    assert {(rule.compared_type, rule.reference_type) for rule in scoring.relation_rules} == set(DEFAULT_ROOM_SIZE_PAIRS)
    for solver, score in zip(DEFAULT_RULES, scoring.relation_rules):
        assert (solver['compared_type'], solver['reference_type'], solver['max_ratio']) == (score.compared_type, score.reference_type, score.max_ratio)
        assert score.reference_aggregation == RoomAreaAggregation.MIN
        assert score.compared_aggregation == RoomAreaAggregation.MAX
