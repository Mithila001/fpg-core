import json
from copy import deepcopy

import pytest
from fpg_core.domain import ExecutionMode
from fpg_core.floor_plan_scoring import (
    EvaluatorRegistry,
    FloorPlanScoringInput,
    RoomSizeConsistencyEvaluator,
    ScoringInputError,
    create_default_registry,
    diagnose_skipped_evaluators,
    score_floor_plan,
)
from sqlalchemy import inspect
from test_lab import initialized_runtime

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.database.models import E02BRun, E02BSavedPlan, E02Run
from fpg_lab.flows.e02b import delete_layout, save_layout, start
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.integrations.fpg_core.e02b_input import (
    decode_plan,
    export_stage,
)
from fpg_lab.services.common import SystemConfigurationService
from fpg_lab.visualization import e02b as plots


def rectangle(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def polygon(points):
    return {"points": [{"x": x, "y": y} for x, y in points]}


def source_case():
    room_data = [
        ("k", "kitchen", rectangle(0, 0, 100, 20)),
        ("d", "dining_room", rectangle(0, 20, 20, 70)),
        ("l", "living_room", rectangle(80, 20, 100, 70)),
        (
            "h",
            "hallway",
            [(0, 70), (100, 70), (100, 120), (55, 120), (55, 90), (40, 90), (40, 120), (0, 120)],
        ),
        ("b", "bathroom", rectangle(30, 5, 45, 18)),
    ]
    rooms = [
        {
            "id": key,
            "room_type": kind,
            "name": kind.replace("_", " ").title(),
            "boundary": polygon(points),
        }
        for key, kind, points in room_data
    ]
    plan = {
        "boundary": polygon(rectangle(0, 0, 120, 120)),
        "rooms": rooms,
        "openings": [],
        "identity_redirects": {"old_h": "h"},
    }
    sizes = {"min_width": 10, "max_width": 100, "min_area": 100, "max_area": 5000}
    specs = [
        {"id": room["id"], "room_type": room["room_type"], "name": room["name"], "size": sizes}
        for room in rooms
    ]
    specs.append({**specs[3], "id": "old_h"})
    spec = {
        "floor": {"width": 120, "length": 120},
        "rooms": specs,
        "room_relations": [
            {
                "source_room_id": "d",
                "target_room_ids": ["k", "l"],
                "match_policy": "and",
                "strength": "hard",
            },
            {
                "source_room_id": "d",
                "target_room_ids": ["old_h", "l"],
                "match_policy": "or",
                "strength": "hard",
            },
        ],
    }
    record = {
        "id": 5,
        "snapshot": {
            "core_version": "test",
            "maps": {
                "case": {
                    "project_units_per_meter": 10,
                    "specification": spec,
                }
            },
        },
    }
    stages = [
        {"name": title, "data": {"result": {"floor_plan": plan}}}
        for title in ("Initial", "Refinement 1", "Post-process")
    ]
    return record, {"name": "case", "stages": stages}


def portable_plan():
    record, case = source_case()
    return export_stage(record, case, case["stages"][-1])


def test_portable_stages_accept_architectural_defects():
    record, case = source_case()
    for stage in case["stages"]:
        document = export_stage(record, case, stage)
        plan, spec = decode_plan(document)
        assert document["source"]["stage"] == stage["name"]
        assert plan.identity_redirects == {"old_h": "h"}
        assert spec.room_relations[1].target_room_ids == ("old_h", "l")
        assert "openings" not in document["floor_plan"]
    invalid = deepcopy(document)
    invalid["floor_plan"]["rooms"][0]["boundary"]["points"][0]["x"] = "0"
    with pytest.raises(ValueError):
        decode_plan(invalid)
    invalid = deepcopy(document)
    invalid["floor_plan"]["identity_redirects"] = {"old_h": "k"}
    with pytest.raises(ScoringInputError, match="room type"):
        decode_plan(invalid)




def decode_config(document):
    return CoreConfigCodec().decode_floor_scoring(document)


def default_config_document():
    from fpg_core.floor_plan_scoring import create_default_config

    return to_jsonable(create_default_config())


def test_storage_snapshot_recovery_and_measurements(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'lab.db'}"
    runtime = initialized_runtime(database_url=database_url)
    document = portable_plan()
    with runtime:
        assert {"fpg_e02_run", "fpg_e02b_run", "fpg_e02b_saved_plan"} <= set(
            inspect(runtime.database.engine).get_table_names()
        )
        with runtime.database.session_factory() as session:
            service = SystemConfigurationService(session, runtime.codec)
            profile = service.duplicate(service.get_active().id, "scoring fixture")
            saved = service.save_section(profile.id, "floor_plan_scoring", default_config_document(),
                                         expected_hash=profile.config_hash)
            profile_id, profile_hash = saved.id, saved.config_hash
            config = saved.configuration_data["floor_plan_scoring"]
            session.add(E02Run(status="completed", snapshot={"existing": True}, cases=[]))
            session.commit()
            layout_id = save_layout(session, "Ring and notch", document)
        saved_run = start(runtime, layout_id=layout_id, configuration_id=profile_id)
        temporary_run = start(runtime, document=document, configuration_id=profile_id)
        with runtime.database.session_factory() as session:
            delete_layout(session, layout_id)
            interrupted = E02BRun(status="running", snapshot={"existing": True})
            session.add(interrupted)
            session.commit()
            interrupted_id = interrupted.id
        changed = deepcopy(config)
        changed["groups"][1]["weight"] = 3
        with runtime.database.session_factory() as session:
            SystemConfigurationService(session).save_section(
                profile_id, "floor_plan_scoring", changed, expected_hash=profile_hash
            )

    with (
        initialized_runtime(database_url=database_url) as reopened,
        reopened.database.session_factory() as session,
    ):
        assert session.get(E02BSavedPlan, layout_id) is None
        assert session.get(E02Run, 1).snapshot == {"existing": True}
        assert session.get(E02BRun, interrupted_id).status == "interrupted"
        historical = session.get(E02BRun, saved_run)
        assert historical.status == "completed", historical.error
        assert historical.duration_seconds > 0
        assert historical.snapshot["input"] == json.loads(json.dumps(document))
        assert historical.snapshot["configuration"] == config
        assert historical.snapshot["configuration_hash"] == profile_hash
        assert historical.snapshot["configuration_id"] == profile_id
        assert session.get(E02BRun, temporary_run).snapshot["layout_name"] == "Temporary import"

        plan, spec = decode_plan(document)
        request = FloorPlanScoringInput(plan, spec, decode_config(config))
        production = score_floor_plan(request)
        official = historical.official
        assert official["result"]["total_score"] == production.result.total_score
        assert official["result"]["passed_critical"] == production.result.passed_critical is False
        results = {item["evaluator_key"]: item for item in official["details"]["evaluator_results"]}
        for attempt in historical.diagnostics:
            assert attempt["status"] == "completed"
            assert results[attempt["evaluator_key"]]["raw_score"] is None
            results[attempt["evaluator_key"]] = attempt["evaluation"]
        assert len(historical.diagnostics) == 2
        assert results["geometry_integrity"]["findings"][0]["metrics"][0]["value"] == 195
        assert results["required_adjacency"]["visualization_payload"]["relations"][1]["passed"]
        assert results["enclosed_voids"]["visualization_payload"]["voids"][0]["area"] == 3000
        recess = results["inward_recess"]["visualization_payload"]["recesses"][0]
        assert recess["region"]["depth_to_width_ratio"] == 2
        assert recess["sections"][0]["entrances"]
        assert (
            results["kitchen_dining_proximity"]["visualization_payload"]["pairs"][0][
                "shared_length"
            ]
            == 20
        )
        assert plots.size_matrix(results["room_size_consistency"]["visualization_payload"])
        for key, evaluation in results.items():
            observations = plots.observations(key, evaluation, document["floor_plan"])
            assert observations
            enabled = {layer.overlay for item in observations for layer in item.layers}
            fig = plots.inspection_plot(
                document["floor_plan"], key, 10, observations, evaluation, 0, enabled
            )
            assert fig.layout.yaxis.scaleanchor == "x"
            if key != "room_size_consistency":
                assert len(fig.data) > len(plan.rooms) + 1


def test_diagnostics_recover_valid_pairs_and_report_invalid_inputs():
    document = portable_plan()
    document["floor_plan"]["rooms"][-1]["boundary"] = polygon(
        [(30, 5), (45, 18), (45, 5), (30, 18)]
    )
    plan, spec = decode_plan(document)
    request = FloorPlanScoringInput(plan, spec, decode_config(default_config_document()))
    official = score_floor_plan(request, mode=ExecutionMode.DEBUG)
    results = {item.evaluator_key: item for item in diagnose_skipped_evaluators(request, official)}
    assert results["room_size_consistency"].status == "unavailable"
    assert results["kitchen_dining_proximity"].status == "completed"


def test_diagnostics_handle_exceptions_inapplicability_and_passed_gate():
    document = portable_plan()
    document["floor_plan"]["rooms"] = [r for r in document["floor_plan"]["rooms"] if r["id"] != "d"]
    document["specification"]["rooms"] = [
        r for r in document["specification"]["rooms"] if r["id"] != "d"
    ]
    document["specification"]["room_relations"] = []
    config = decode_config(default_config_document())

    class BrokenSize(RoomSizeConsistencyEvaluator):
        def evaluate(self, context, settings):
            raise RuntimeError("test evaluator failure")

    default_registry = create_default_registry()
    registry = EvaluatorRegistry(
        BrokenSize() if rule.key == BrokenSize().key else default_registry.get(rule.key)
        for rule in config.evaluators
    )
    request = FloorPlanScoringInput(*decode_plan(document), config)
    official = score_floor_plan(request, mode=ExecutionMode.DEBUG, registry=registry)
    attempts = diagnose_skipped_evaluators(request, official, registry=registry)
    assert [item.status for item in attempts] == ["failed", "not_applicable"]
    assert "test evaluator failure" in attempts[0].error

    document["floor_plan"]["rooms"] = document["floor_plan"]["rooms"][:1]
    document["floor_plan"]["identity_redirects"] = {}
    document["specification"]["rooms"] = document["specification"]["rooms"][:1]
    request = FloorPlanScoringInput(*decode_plan(document), config)
    official = score_floor_plan(request, mode=ExecutionMode.DEBUG)
    assert official.result.passed_critical
    assert official.result == score_floor_plan(request).result
    assert diagnose_skipped_evaluators(request, official) == ()
