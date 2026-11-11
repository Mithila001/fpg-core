from copy import deepcopy

import pytest
from shapely.geometry import LineString

from fpg_lab.flows.e01a import RADIUS, geometry, simulate
from fpg_lab.flows.e01a_plans import plans
from fpg_lab.ui.e01a import traffic_figure


@pytest.fixture(scope="module")
def results():
    return {key: simulate(plan) for key, plan in plans().items()}


def test_fixtures_and_routes(results):
    for key, plan in plans().items():
        rooms, floor, walls = geometry(plan)
        result = results[key]
        assert len(rooms) == 9
        doors = [opening for opening in plan["openings"] if opening["opening_type"] == "door"]
        assert all(LineString([(o["start"]["x"], o["start"]["y"]),
                               (o["end"]["x"], o["end"]["y"]) ]).length == pytest.approx(10)
                   for o in doors)
        assert len([o for o in doors if o["purpose"] == "main_entrance"]) == 1
        # Bedrooms have corridor access; only attached bathrooms require crossing a bedroom.
        connections = [set(o["connected_room_ids"]) for o in doors]
        assert {"hallway", "bedroom_1"} in connections
        assert {"hallway", "bedroom_2"} in connections
        assert {"hallway", "bathroom_1"} in connections
        assert len(result["routes"]) == 8
        assert not result["failures"]
        assert floor.equals(geometry(plan)[1])
        for route in result["routes"]:
            line = LineString(route["points"])
            assert line.distance(walls) >= RADIUS - 1e-6
            assert floor.buffer(1e-7).covers(route["footprint"])
            assert line.coords[0] == (rooms[route["source"]].centroid.x, rooms[route["source"]].centroid.y)
            assert line.coords[-1] == (rooms[route["destination"]].centroid.x, rooms[route["destination"]].centroid.y)
        assert any(len(route["points"]) > 4 for route in result["routes"])
        assert all(len(row) == len(result["heatmap"]["x"]) for row in result["heatmap"]["z"])
        assert any(v == 0 for row in result["heatmap"]["z"] for v in row)
        assert any(v is not None and v > 1 for row in result["heatmap"]["z"] for v in row)


def test_closest_bathroom_and_determinism(results):
    plan = plans()["compact"]
    result = results["compact"]
    for source in ("bedroom_1", "bedroom_2"):
        chosen = next(r for r in result["routes"] if r["source"] == source and r["destination"].startswith("bathroom"))
        candidates = simulate(plan, [(source, "bathroom_1"), (source, "bathroom_2")])["routes"]
        expected = min(candidates, key=lambda r: (r["length"], r["destination"]))
        assert chosen["destination"] == expected["destination"]
        assert chosen["points"] == expected["points"]


def test_closed_and_narrow_doors_block_and_windows_never_open_walls():
    plan = deepcopy(plans()["compact"])
    # The only interior exit is too narrow for the 8-unit footprint.
    door = next(o for o in plan["openings"] if set(o["connected_room_ids"]) == {"veranda", "living"})
    midpoint = (door["start"]["x"] + door["end"]["x"]) / 2
    door["start"]["x"], door["end"]["x"] = midpoint - 3, midpoint + 3
    result = simulate(plan, [("veranda", "living")])
    assert not result["routes"]
    assert len(result["failures"]) == 1
    assert all(value in (None, 0) for row in result["heatmap"]["z"] for value in row)
    door["opening_type"] = "window"
    door["start"]["x"], door["end"]["x"] = midpoint - 5, midpoint + 5
    assert not simulate(plan, [("veranda", "living")])["routes"]


def test_traffic_overlap_and_plot_modes(results):
    plan = plans()["compact"]
    one = simulate(plan, [("veranda", "living")])
    two = simulate(plan, [("veranda", "living"), ("veranda", "living")])
    for row1, row2 in zip(one["heatmap"]["z"], two["heatmap"]["z"], strict=True):
        for a, b in zip(row1, row2, strict=True):
            if a is not None:
                assert b == pytest.approx(a * 2)
    for mode in ("Floor plan", "Paths", "Heatmap"):
        chart = traffic_figure(plan, results["compact"], mode)
        assert chart.data
        assert (any(trace.type == "heatmap" for trace in chart.data)) == (mode == "Heatmap")
    all_paths = traffic_figure(plan, results["compact"], "Paths")
    one_path = traffic_figure(plan, results["compact"], "Paths", {0})
    assert len(one_path.data) < len(all_paths.data)
    no_paths = traffic_figure(plan, results["compact"], "Paths", set())
    two_paths = traffic_figure(plan, results["compact"], "Paths", {0, 2})
    assert len(no_paths.data) < len(one_path.data) < len(two_paths.data) < len(all_paths.data)


def test_import_scaled_plan_and_automatic_room_id_matching():
    from fpg_lab.flows.e01a import preset_trips
    from fpg_lab.integrations.fpg_core.traffic_plan import import_traffic_plan

    original = plans()["compact"]
    scaled = deepcopy(original)
    for polygon in [scaled["boundary"], *(room["boundary"] for room in scaled["rooms"])]:
        for point in polygon["points"]:
            point["x"] *= 2
            point["y"] *= 2
    for opening in scaled["openings"]:
        for key in ("start", "end"):
            opening[key]["x"] *= 2
            opening[key]["y"] *= 2
    imported = import_traffic_plan({"version": 1, "project_units_per_meter": 20, "floor_plan": scaled})
    assert imported["rooms"][0]["boundary"] == original["rooms"][0]["boundary"]
    for room in imported["rooms"]:
        room["id"] = "generated_" + room["id"]
    for opening in imported["openings"]:
        opening["connected_room_ids"] = ["generated_" + key for key in opening["connected_room_ids"]]
    assert ("generated_veranda", "generated_living") in preset_trips(imported)
    assert len(simulate(imported)["routes"]) == 8
    with pytest.raises(ValueError):
        import_traffic_plan({"version": 2, "project_units_per_meter": 10, "floor_plan": original})
