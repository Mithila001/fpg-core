"""Export a portable floor plan from an E02A stage."""


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
