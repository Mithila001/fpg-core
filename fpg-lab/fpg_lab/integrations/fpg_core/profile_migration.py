"""Upgrade saved profiles while leaving immutable experiment snapshots untouched."""
from copy import deepcopy

from sqlalchemy import select

from fpg_lab.database.models import SystemConfiguration


def migrate_profiles(session, codec):
    for record in session.scalars(select(SystemConfiguration)):
        original = record.configuration_data
        data = deepcopy(original)
        preprocessing = data.get("preprocessing") or {}
        if preprocessing.get("hallway_min_width", 10) < 10:
            preprocessing["hallway_min_width"] = 10.0
        def update_constraints(value):
            if isinstance(value, dict):
                if value.get("key") == "hallway_dimensions":
                    settings = value.setdefault("settings", {})
                    settings["minimum_width"] = max(10, settings.get("minimum_width", 10))
                    settings["maximum_width"] = max(settings["minimum_width"], settings.get("maximum_width", 10))
                for child in value.values():
                    update_constraints(child)
            elif isinstance(value, list):
                for child in value:
                    update_constraints(child)
        update_constraints(data.get("floor_plan_solver"))
        update_constraints((data.get("experiments") or {}).get("p01b_refinement"))
        dimensions = ((data.get("openings") or {}).get("dimensions") or {})
        if dimensions.get("door_width") == 8:
            dimensions["door_width"] = 10.0
        (data.get("experiments") or {}).pop("p01c", None)
        if data != original:
            validated = codec.validate_payload(data)
            record.configuration_data = validated.payload
            record.config_hash = validated.config_hash
            record.fpg_core_version = validated.fpg_core_version
    session.commit()
