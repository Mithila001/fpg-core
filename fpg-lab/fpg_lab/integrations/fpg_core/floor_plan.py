"""Decode current portable floor plans for inspection."""

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


