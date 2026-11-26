"""Portable E02 floor plans and the standalone scoring configuration."""

import json

from fpg_core.domain import FloorPlan, FloorPlanGenerationSpec
from fpg_core.floor_plan_scoring import (
    validate_scoring_input,
)
from pydantic import TypeAdapter

PLAN_ADAPTER = TypeAdapter(FloorPlan)
SPEC_ADAPTER = TypeAdapter(FloorPlanGenerationSpec)


def decode_plan(document):
    if (
        not isinstance(document, dict)
        or document.get("schema") != "fpg-floor-plan"
        or type(document.get("version")) is not int
        or document["version"] != 1
    ):
        raise ValueError("Expected a version 1 portable FPG floor plan")
    units = document.get("project_units_per_meter")
    if type(units) is not int or units <= 0:
        raise ValueError("Project units per metre must be a positive integer")
    if not isinstance(document.get("source"), dict):
        raise ValueError("Portable floor plans require a source object")
    plan = PLAN_ADAPTER.validate_json(
        json.dumps(document.get("floor_plan"), allow_nan=False), strict=True
    )
    spec = SPEC_ADAPTER.validate_json(
        json.dumps(document.get("specification"), allow_nan=False), strict=True
    )
    validate_scoring_input(plan, spec)
    return plan, spec


def export_stage(record, case, stage):
    plan = (stage["data"].get("result") or {}).get("floor_plan")
    if not plan:
        raise ValueError("The selected stage has no floor plan")
    snapshot = record["snapshot"]
    hint_map = snapshot["maps"][case["name"]]
    document = {
        "schema": "fpg-floor-plan",
        "version": 1,
        "floor_plan": {key: value for key, value in plan.items() if key != "openings"},
        "specification": hint_map["specification"],
        "project_units_per_meter": hint_map["project_units_per_meter"],
        "source": {
            "experiment": "e02a",
            "run_id": record["id"],
            "case": case["name"],
            "stage": stage["name"],
            "core_version": snapshot["core_version"],
        },
    }
    return document
