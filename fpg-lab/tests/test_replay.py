from __future__ import annotations

from pathlib import Path

import pytest
from test_lab import create_profile, payload

from fpg_lab.core.exceptions import NotFoundError
from fpg_lab.database.models import P01CandidateTrial
from fpg_lab.inputs import P01AInput
from fpg_lab.runtime import LabRuntime
from fpg_lab.services.p01a import P01AService
from fpg_lab.visualization import figures, replay


def test_single_and_multiple_room_selection() -> None:
    selected = {"kitchen", "living"}
    assert replay.select_rooms(selected, "bedroom", True, single=True) == {"bedroom"}
    assert replay.select_rooms(selected, "bedroom", True, single=False) == {
        "kitchen",
        "living",
        "bedroom",
    }
    assert replay.select_rooms({"kitchen"}, "kitchen", False, single=True) == set()
    assert replay.select_rooms(selected, "kitchen", False, single=False) == {"living"}
    assert selected == {"kitchen", "living"}


def test_frames_and_scores() -> None:
    trials = [
        dict(trial_no=i + 1, final_score=score)
        for i, score in enumerate([None, 0, 20, 20, None, 10, 30])
    ]
    frames = replay.frames(list(reversed(trials)))
    assert [f["trial_no"] for f in frames] == list(range(1, 8))
    assert [f["best_score"] for f in frames] == [None, 0, 20, 20, 20, 20, 30]
    assert [f["trial_no"] for f in replay.frames(trials, improvements=True)] == [2, 3, 7]
    assert frames[4]["score_change"] is None
    assert frames[5]["score_change"] == -10
    history = figures.score_history(frames, trial_no=6)
    assert list(history.data[1].y) == [None, 0, 20, 20, 20, 20, 30]
    assert history.layout.shapes[0].x0 == 6
    assert replay.frames([trials[0]], improvements=True) == []
    scoring = {
        "details": {"unrelated": True},
        "evaluator_results": [
            {"evaluator_key": "zones", "raw_score": 80, "contribution": 20},
            {"evaluator_key": "skipped", "raw_score": None, "contribution": 0},
        ],
    }
    chart = figures.score_breakdown(scoring)
    assert list(chart.data[0].y) == [80, None]
    assert list(chart.data[1].y) == [20, 0]


def test_geometry_identity_and_onion_skins() -> None:
    rooms = [
        {"id": f"bed{i}", "room_type": "bedroom", "name": f"Bedroom {i}"} for i in range(8)
    ] + [{"id": "hall", "room_type": "hallway"}]
    styles = replay.room_styles(rooms)
    assert len({s["color"] for s in styles.values()}) == len(rooms)
    assert styles == replay.room_styles(rooms)
    assert styles["bed0"]["label"] == "BED1"
    assert styles["bed1"]["label"] == "BED2"
    prepared = {
        "candidate_grid": {"x_positions": [1, 2, 3], "y_positions": [1, 2, 3]},
        "generation_spec": {"floor": {"width": 4, "length": 5}, "rooms": rooms},
    }
    trials = []
    for i in range(6):
        points = [{"room_id": "bed0", "x": i, "y": 2}]
        if i % 2:
            points.append({"room_id": "hall", "x": 2, "y": 3})
        trials.append(
            {
                "trial_no": i + 1,
                "candidate_search_data": {"points": points},
                "circulation_data": {"result": {"candidate": {"points": points[:1]}}},
            }
        )
    chart = replay.replay_map(trials, 5, prepared=prepared, styles=styles)
    beds = list(chart.data[2:])
    assert [t.x[0] for t in beds] == [1, 2, 3, 4, 5]
    assert [t.opacity for t in beds] == sorted(t.opacity for t in beds)
    assert beds[0].opacity >= 0.08 and beds[-1].opacity == 1
    assert all(t.marker.color[0] == styles["bed0"]["color"] for t in beds)
    assert sum(len(t.x) == 2 for t in beds) == 3
    assert list(chart.data[1].x) == [0, 4, 4, 0, 0]
    assert chart.layout.yaxis.scaleanchor == "x"
    assert chart.layout.xaxis.autorange is False
    cleaned = replay.replay_map(
        trials, 5, prepared=prepared, styles=styles, cleaned=True, previous_frames=0
    )
    assert len(cleaned.data[2:]) == 1
    assert chart.layout.xaxis.showgrid is False and chart.layout.yaxis.showgrid is False
    subset = replay.replay_map(
        trials, 5, prepared=prepared, styles=styles, previous_frames=5, selected_rooms={"hall"}
    )
    assert len(subset.data[2:]) == 3
    assert all(list(t.customdata) == ["hall (hall)"] for t in subset.data[2:])
    empty = replay.replay_map(trials, 5, prepared=prepared, styles=styles, selected_rooms=set())
    assert len(empty.data) == 2
    trials[5]["circulation_data"] = None
    missing = replay.replay_map(trials, 5, prepared=prepared, styles=styles, cleaned=True)
    assert len(missing.data) == 2  # Grid and boundary only, never stale dots.
    assert missing.layout.annotations[0].text == "Cleaned geometry unavailable"
    trials[5]["candidate_search_data"] = None
    assert replay.geometry(trials[5], False) is None


def test_accumulating_heatmap() -> None:
    def candidate(x: float) -> dict:
        return {"points": [{"room_id": "room", "x": x, "y": 1}]}

    trials = [
        {"trial_no": 1, "candidate_search_data": None},
        {"trial_no": 2, "status": "failed", "candidate_search_data": candidate(1)},
        {
            "trial_no": 3,
            "candidate_search_data": candidate(1),
            "circulation_data": {"result": {"candidate": candidate(2)}},
        },
        {"trial_no": 4, "candidate_search_data": candidate(2)},
    ]
    history = replay.placement_history(trials, "room")
    assert replay.placement_counts(history, 1) == {}
    assert replay.placement_counts(history, 4) == {(1, 1): 2, (2, 1): 1}
    assert replay.placement_counts(history, 2) == {(1, 1): 1}
    assert replay.placement_counts(replay.placement_history(trials, "room", cleaned=True), 4) == {
        (2, 1): 1
    }
    assert replay.placement_history(trials, "absent") == {}
    prepared = {
        "candidate_grid": {"x_positions": [0.1, 1, 2], "y_positions": [0.1, 1, 2]},
        "generation_spec": {"floor": {"width": 2.1, "length": 2.1}},
    }
    styles = replay.room_styles([{"id": "room"}])
    chart = replay.replay_map(
        trials,
        3,
        prepared=prepared,
        styles=styles,
        heatmap_counts=replay.placement_counts(history, 4),
        selected_rooms={"room"},
    )
    heatmap = chart.data[0]
    assert heatmap.type == "heatmap" and list(heatmap.z[1]) == [0, 2, 1]
    assert heatmap.zmin == 0 and heatmap.zmax == 2 and heatmap.zsmooth is False
    assert heatmap.x[0] == 0 and heatmap.x[-1] == 2.1
    assert len(heatmap.colorscale) > 2
    assert heatmap.customdata[1][1] == [1, 1, 200 / 3]
    assert len(chart.data) == 4  # Heatmap, grid, boundary, current marker; no trails.
    early = replay.replay_map(trials, 0, prepared=prepared, styles=styles, heatmap_counts={})
    assert "No placements" in early.layout.annotations[0].text
    assert not any(t.type == "heatmap" for t in early.data)


def test_dynamic_evaluator_progression() -> None:
    def trial(number: int, *evaluators: dict) -> dict:
        return {
            "trial_no": number,
            "candidate_scoring_data": {"evaluator_results": list(evaluators)},
        }

    trials = [
        trial(
            1,
            {"evaluator_key": "zones", "status": "completed", "raw_score": 80, "contribution": 20},
        ),
        trial(
            2,
            {"evaluator_key": "zones", "status": "skipped", "raw_score": 100},
            {"evaluator_key": "new_evaluator", "status": "completed", "raw_score": 10},
        ),
        trial(3, {"evaluator_key": "zones", "status": "completed", "raw_score": 30}),
        {"trial_no": 4, "candidate_scoring_data": None},
    ]
    charts = figures.evaluator_histories(trials)
    assert list(charts) == ["zones", "new_evaluator"]
    zones = charts["zones"]
    assert list(zones.data[0].y) == [80, None, 30, None]
    assert list(zones.data[1].y) == [80, 80, 80, 80]
    assert zones.data[0].customdata[0] == ["completed", 20]
    assert zones.data[0].connectgaps is False
    assert list(charts["new_evaluator"].data[1].y) == [None, 10, 10, 10]
    assert list(zones.layout.yaxis.range) == [0, 100]
    assert zones.layout.shapes[0].x0 == 1


def test_replay_pages_and_ownership(tmp_path: Path) -> None:
    with LabRuntime(database_url=f"sqlite:///{tmp_path / 'replay.db'}") as runtime:
        create_profile(runtime)
        with runtime.database.session_factory() as session:
            service = P01AService(session)
            experiment = service.create_experiment(P01AInput.model_validate(payload("p01a")))
            other = service.create_experiment(P01AInput.model_validate(payload("p01a")))
            session.add_all(
                [
                    P01CandidateTrial(
                        experiment_id=experiment.id,
                        trial_no=i,
                        status="completed",
                        final_score=i % 100,
                    )
                    for i in range(205, 0, -1)
                ]
            )
            session.add(P01CandidateTrial(experiment_id=other.id, trial_no=999, status="failed"))
            session.commit()
            first = service.replay_trials(experiment.id)
            second = service.replay_trials(experiment.id, after=first[-1].trial_no)
            third = service.replay_trials(experiment.id, after=second[-1].trial_no)
            assert [t.trial_no for t in first + second + third] == list(range(1, 206))
            assert [len(first), len(second), len(third)] == [100, 100, 5]
            assert service.replay_trials(experiment.id, after=205) == []
            other.flow_type = "p01c"
            session.commit()
            with pytest.raises(NotFoundError):
                service.replay_trials(other.id)
            with pytest.raises(NotFoundError):
                service.replay_trials(999999)
