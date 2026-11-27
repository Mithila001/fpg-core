"""Export cleaned candidate inputs from P01 trials."""

from fpg_lab.integrations.fpg_core.hint_map import validate_export


def export_trial(experiment: dict, trial: dict) -> dict:
    circulation = trial.get("circulation_data") or {}
    candidate = (circulation.get("result") or {}).get("candidate")
    specification = circulation.get("lab_generation_specification")
    if not candidate or not specification:
        raise ValueError("Cleaned candidate or its specification was not saved for this trial")
    document = {
        "version": 1,
        "candidate": candidate,
        "specification": specification,
        "request": experiment["floor_plan_request"],
        "project_units_per_meter": experiment["system_configuration_snapshot"][
            "project_units_per_meter"
        ],
        "source": {
            "experiment_id": experiment["id"],
            "trial_no": trial["trial_no"],
            "core_version": experiment["fpg_core_version"],
        },
    }
    validate_export(document)
    return document
