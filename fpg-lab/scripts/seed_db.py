from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

from fpg_lab.core.exceptions import AppError
from fpg_lab.core.settings import get_settings
from fpg_lab.database.models import FloorPlanTemplate, SystemConfiguration
from fpg_lab.database.session import Database
from fpg_lab.inputs import (
    FloorPlanTemplateCreate,
    FloorPlanTemplateUpdate,
    SystemConfigurationCreate,
    SystemConfigurationUpdate,
)
from fpg_lab.integrations.fpg_core.config_codec import CoreConfigCodec
from fpg_lab.services.common import (
    FloorPlanTemplateService,
    SystemConfigurationService,
    seed_namespace_registry,
)


def read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def seed_configuration(
    service: SystemConfigurationService,
    session: Any,
    path: Path,
    *,
    activate: bool,
) -> int:
    payload_data = read_object(path)
    if "configuration_data" not in payload_data:
        configuration_data = payload_data
        payload_data = {
            "name": path.stem,
            "description": f"Imported from {path.name}",
            "schema_version": str(configuration_data.get("schema_version", "6")),
            "configuration_data": configuration_data,
        }
    create_payload = SystemConfigurationCreate.model_validate(payload_data)
    existing_id = session.scalar(
        select(SystemConfiguration.id).where(SystemConfiguration.name == create_payload.name)
    )
    if existing_id is None:
        record = service.create(create_payload)
    else:
        record = service.update(
            int(existing_id),
            SystemConfigurationUpdate.model_validate(payload_data),
        )
    if activate:
        record = service.activate(record.id)
    return record.id


def seed_template(
    service: FloorPlanTemplateService,
    session: Any,
    path: Path,
) -> int:
    payload_data = read_object(path)
    create_payload = FloorPlanTemplateCreate.model_validate(payload_data)
    existing_id = session.scalar(
        select(FloorPlanTemplate.id).where(FloorPlanTemplate.name == create_payload.name)
    )
    if existing_id is None:
        record = service.create(create_payload)
    else:
        record = service.update(
            int(existing_id),
            FloorPlanTemplateUpdate.model_validate(payload_data),
        )
    return record.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FPG Lab records.")
    parser.add_argument("--system-config", type=Path)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--floor-plan-template", type=Path, action="append", default=[])
    args = parser.parse_args()

    if args.system_config is None and not args.floor_plan_template:
        parser.error("Provide --system-config and/or --floor-plan-template")
    if args.activate and args.system_config is None:
        parser.error("--activate requires --system-config")

    settings = get_settings()
    database = Database(settings.database_url)
    codec = CoreConfigCodec()
    try:
        database.create_schema()
        with database.session_factory() as session:
            seed_namespace_registry(session)
            if args.system_config is not None:
                config_id = seed_configuration(
                    SystemConfigurationService(session, codec),
                    session,
                    args.system_config,
                    activate=args.activate,
                )
                print(f"Seeded system configuration id={config_id}")
            template_service = FloorPlanTemplateService(session)
            for path in args.floor_plan_template:
                template_id = seed_template(template_service, session, path)
                print(f"Seeded floor-plan template id={template_id}")
    finally:
        database.dispose()


if __name__ == "__main__":
    try:
        main()
    except (AppError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Database seed failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
