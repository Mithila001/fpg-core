from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import pytest
from fpg_core.candidate_circulation import (
    CandidateCirculationConfig,
    CandidateCirculationInput,
    CirculationRouteRule,
    RoutingCostProfile,
    refine_candidate_circulation,
)
from fpg_core.domain import (
    CandidateMap,
    CandidatePoint,
    CirculationTrafficClass,
    DestinationSelection,
    ExecutionMode,
    ResolvedCandidateGrid,
    RoomId,
    RoomType,
)
from test_lab import RecordingAdapter, create_profile, initialized_runtime, payload, wait

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.visualization import circulation


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("flow", ["p01a"])
def test_diagnostic_retention_is_p01a_debug_only(tmp_path: Path, debug: bool, flow: str) -> None:
    class DiagnosticAdapter(RecordingAdapter):
        pass

    adapters = []

    def factory(config: Any) -> DiagnosticAdapter:
        adapter = DiagnosticAdapter(config)
        adapters.append(adapter)
        return adapter

    with initialized_runtime(
        database_url=f"sqlite:///{tmp_path / 'diagnostics.db'}",
        adapter_factory=factory,
    ) as runtime:
        create_profile(runtime)
        experiment_id = runtime.start_experiment(flow, payload(flow, debug=debug))
        result = wait(runtime, flow, experiment_id)
    assert result["experiment"]["status"] == "completed"
    assert "diagnostic_routing" not in adapters[0].calls
    if debug:
        assert all(t["circulation_data"] for t in result["trials"])
        assert result["experiment"]["best_candidate_score"] == 80


def test_cleaned_diagnostic_capture_and_saved_overlays(monkeypatch: pytest.MonkeyPatch) -> None:
    config = CandidateCirculationConfig(
        costs=RoutingCostProfile(2, 0.75, 0.35, 1.5, 8),
        route_rules=(
            CirculationRouteRule(
                id=1,
                name="living to kitchen",
                source_room_type=RoomType.LIVING_ROOM,
                destination_room_type=RoomType.KITCHEN,
                destination_selection=DestinationSelection.ALL_MATCHING,
                traffic_class=CirculationTrafficClass.PUBLIC,
                allowed_transit_room_types=(),
                importance_weight=1,
            ),
        ),
        always_traversable_room_types=(RoomType.HALLWAY,),
    )
    grid = ResolvedCandidateGrid(tuple(range(7)), tuple(range(7)))
    candidate = CandidateMap(
        grid,
        (
            CandidatePoint(RoomId("living"), 1, 1, RoomType.LIVING_ROOM),
            CandidatePoint(RoomId("kitchen"), 5, 1, RoomType.KITCHEN),
            CandidatePoint(RoomId("unused"), 5, 5, RoomType.HALLWAY),
        ),
    )
    execution = refine_candidate_circulation(
        CandidateCirculationInput(candidate, config),
        mode=ExecutionMode.DEBUG,
    )
    recorded = to_jsonable(execution)
    assert recorded["result"]["final_circulation"]["routes"]
    assert {p.room_id for p in execution.result.points} == {"living", "kitchen"}
    assert len(candidate.points) == 3
    frame = {"circulation_data": recorded}
    before = circulation.paths(frame, before=True)
    after = circulation.paths(frame, before=False)
    assert before and after
    assert after[0]["source_room_id"] == "living"
    key = circulation.path_key(after[0])
    assert key == circulation.path_key(before[0])
    chart = go.Figure()
    circulation.add_overlay(chart, frame, before=False, selected={key}, styles={})
    assert len(chart.data) == 2  # One selected route and the removed hallway.
    assert list(chart.data[0].x)[0] == 1 and list(chart.data[0].x)[-1] == 5
    assert chart.data[0].line.dash == "solid"
    assert chart.data[1].marker.symbol == "x"
    assert "unused" in chart.data[1].hovertemplate
    hidden = go.Figure()
    circulation.add_overlay(hidden, frame, before=False, selected=set(), styles={})
    assert len(hidden.data) == 1
    assert circulation.paths({"circulation_data": to_jsonable(execution)}, before=False)
    assert circulation.paths({}, before=True) is None

    assert execution.result.candidate is not None


def test_path_identity_survives_missing_trials_and_private_style() -> None:
    path = {
        "rule_id": 2,
        "rule_name": "private route",
        "traffic_class": "private",
        "source_point_key": "bed[1]",
        "destination_point_key": "bath[1]",
        "source_room_id": "bed",
        "destination_room_id": "bath",
        "manhattan_reference_cost": 3.0,
        "importance_weight": 1.0,
        "step_count": 2,
        "turn_count": 1,
        "nodes": [{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 2}],
        "costs": {
            "movement_cost": 3.0,
            "perimeter_bias_cost": 0.5,
            "turn_cost": 0.5,
            "traffic_conflict_cost": 0.0,
            "total_cost": 4.0,
        },
    }
    selected = {circulation.path_key(path)}
    present = {
        "circulation_data": {"result": {"final_circulation": {"routes": [path], "hallways": []}}}
    }
    missing = {
        "circulation_data": {"result": {"final_circulation": {"routes": [], "hallways": []}}}
    }
    counts = []
    for frame in (present, missing, present):
        figure = go.Figure()
        circulation.add_overlay(figure, frame, before=False, selected=selected, styles={})
        counts.append(len(figure.data))
    assert counts == [1, 0, 1]
    assert figure.data[0].line.dash == "dash"
    assert list(figure.data[0].marker.symbol)[-1] == "diamond"
    assert selected == {(2, "bed[1]", "bath[1]")}
