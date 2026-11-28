from fpg_lab.services.p01a import compact_trial


def test_compact_trial_retains_analysis_and_removes_large_duplicates():
    source = {
        "trial_no": 2,
        "status": "completed",
        "final_score": 12.5,
        "duration_ms": 7,
        "error_data": None,
        "candidate_search_data": {
            "grid": {"x": [1]},
            "points": [{"x": 1}],
            "recorded_result": {"usable": True, "candidate": {"points": []}},
        },
        "circulation_data": {
            "result": {
                "candidate": {"grid": {}, "points": [{"x": 2}]},
                "final_circulation": {"routes": [{"nodes": [1]}]},
            },
            "details": {"passes": [1], "removed_hallway_points": [2]},
        },
        "candidate_scoring_data": {
            "evaluator_results": [
                {
                    "evaluator_key": "spatial_distribution",
                    "metrics": {"coverage_score": 9.5},
                    "details": {
                        "nearest_distances": [[1]],
                        "points": [1],
                        "ideal_point_distance": 2,
                    },
                }
            ]
        },
    }
    result = compact_trial(source)
    assert result["candidate_search_data"] == {
        "points": [{"x": 1}],
        "recorded_result": {"usable": True},
    }
    assert result["circulation_data"]["result"]["final_circulation"]["routes"] == [{"nodes": [1]}]
    assert result["circulation_data"]["details"] == {"removed_hallway_points": [2]}
    evaluation = result["candidate_scoring_data"]["evaluator_results"][0]
    assert evaluation["metrics"]["coverage_score"] == 9.5
    assert evaluation["details"] == {"ideal_point_distance": 2}
    assert source["candidate_scoring_data"]["evaluator_results"][0]["details"][
        "nearest_distances"
    ] == [[1]]
