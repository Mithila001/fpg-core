"""Validate and normalize portable floor plans for session-local traffic."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

from fpg_core.domain import FloorPlan
from pydantic import TypeAdapter

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.flows.e01a import geometry


def import_traffic_plan(document: Any) -> dict:
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("Unsupported floor-plan document version")
    units = document.get("project_units_per_meter")
    if isinstance(units, bool) or not isinstance(units, (int, float)) or not isfinite(units) or units <= 0:
        raise ValueError("project_units_per_meter must be positive and finite")
    plan = to_jsonable(TypeAdapter(FloorPlan).validate_python(deepcopy(document.get("floor_plan"))))
    scale = 10 / units
    for polygon in [plan["boundary"], *(room["boundary"] for room in plan["rooms"])]:
        for point in polygon["points"]:
            point["x"] *= scale
            point["y"] *= scale
    for opening in plan["openings"]:
        for key in ("start", "end"):
            opening[key]["x"] *= scale
            opening[key]["y"] *= scale
    geometry(plan)
    plan["name"] = "Pasted floor plan"
    return plan
