from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fpg_lab.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from fpg_lab.database.models import (
    FloorPlanTemplate,
    NamespaceRegistry,
    SystemConfiguration,
)
from fpg_lab.inputs import (
    FloorPlanTemplateCreate,
    FloorPlanTemplateUpdate,
    SystemConfigurationCreate,
    SystemConfigurationUpdate,
)
from fpg_lab.integrations.fpg_core.config_codec import (
    CoreConfigurationError,
    ValidatedCoreConfiguration,
)

NAMESPACE_SEEDS = (
    {"tag": "E01A", "name": "floor-traffic-experiment",
     "description": "Preset floor-plan walking routes and traffic coverage.", "kind": "experiment"},
    {
        "tag": "COMM",
        "name": "common",
        "description": "Shared records used by multiple experiments.",
        "kind": "common",
    },
    {
        "tag": "P01A",
        "name": "candidate-flow-experiment",
        "description": (
            "Floor-plan request -> preprocessing -> candidate search -> "
            "candidate circulation -> candidate scoring."
        ),
        "kind": "experiment",
    },
    {
        "tag": "P01B",
        "name": "manual-hint-floor-plan-experiment",
        "description": "Manual hint-map floor-plan generation experiment.",
        "kind": "experiment",
    },
    {
        "tag": "P01C",
        "name": "floor-plan-openings-experiment",
        "description": "Repeated floor-plan generation with openings and scoring.",
        "kind": "experiment",
    },
)


def seed_namespace_registry(session: Session) -> None:
    for item in NAMESPACE_SEEDS:
        existing = session.scalar(
            select(NamespaceRegistry).where(NamespaceRegistry.tag == item["tag"])
        )
        if existing is None:
            session.add(NamespaceRegistry(**item))
        else:
            existing.name = item["name"]
            existing.description = item["description"]
            existing.kind = item["kind"]
    session.commit()


class NamespaceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[NamespaceRegistry]:
        return list(self.session.scalars(select(NamespaceRegistry).order_by(NamespaceRegistry.tag)))


class FloorPlanTemplateService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: FloorPlanTemplateCreate) -> FloorPlanTemplate:
        self._ensure_name_available(payload.name)
        record = FloorPlanTemplate(**payload.model_dump())
        self.session.add(record)
        self._commit("floor_plan_template_conflict")
        return record

    def list(self, *, limit: int, offset: int) -> tuple[list[FloorPlanTemplate], int]:
        total = self.session.scalar(select(func.count()).select_from(FloorPlanTemplate)) or 0
        items = list(
            self.session.scalars(
                select(FloorPlanTemplate)
                .order_by(FloorPlanTemplate.created_at.desc(), FloorPlanTemplate.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total)

    def get(self, template_id: int) -> FloorPlanTemplate:
        record = self.session.get(FloorPlanTemplate, template_id)
        if record is None:
            raise NotFoundError(
                "floor_plan_template_not_found",
                f"Floor-plan template {template_id} was not found.",
            )
        return record

    def update(
        self,
        template_id: int,
        payload: FloorPlanTemplateUpdate,
    ) -> FloorPlanTemplate:
        record = self.get(template_id)
        self._ensure_name_available(payload.name, exclude_id=template_id)
        for key, value in payload.model_dump().items():
            setattr(record, key, value)
        self._commit("floor_plan_template_conflict")
        return record

    def delete(self, template_id: int) -> None:
        record = self.get(template_id)
        self.session.delete(record)
        self._commit("floor_plan_template_conflict")

    def _ensure_name_available(self, name: str, *, exclude_id: int | None = None) -> None:
        statement = select(FloorPlanTemplate.id).where(FloorPlanTemplate.name == name)
        if exclude_id is not None:
            statement = statement.where(FloorPlanTemplate.id != exclude_id)
        if self.session.scalar(statement) is not None:
            raise ConflictError(
                "floor_plan_template_name_exists",
                f"A floor-plan template named {name!r} already exists.",
            )

    def _commit(self, code: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(code, "The database rejected the template change.") from exc


class SystemConfigurationService:
    def __init__(self, session: Session, codec: Any) -> None:
        self.session = session
        self.codec = codec

    def create(self, payload: SystemConfigurationCreate) -> SystemConfiguration:
        self._ensure_name_available(payload.name)
        validated = self._validate(payload.configuration_data.model_dump(mode="json"))
        self._validate_schema_version(payload.schema_version, validated)
        record = SystemConfiguration(
            name=payload.name,
            description=payload.description,
            configuration_data=validated.payload,
            is_active=False,
            schema_version=str(validated.payload["schema_version"]),
            fpg_core_version=validated.fpg_core_version,
            config_hash=validated.config_hash,
        )
        self.session.add(record)
        self._commit("system_configuration_conflict")
        return record

    def list(self, *, limit: int, offset: int) -> tuple[list[SystemConfiguration], int]:
        total = self.session.scalar(select(func.count()).select_from(SystemConfiguration)) or 0
        items = list(
            self.session.scalars(
                select(SystemConfiguration)
                .order_by(
                    SystemConfiguration.is_active.desc(),
                    SystemConfiguration.created_at.desc(),
                    SystemConfiguration.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )
        for item in items:
            self._refresh_stored_configuration(item)
        return items, int(total)

    def get(self, configuration_id: int) -> SystemConfiguration:
        record = self.session.get(SystemConfiguration, configuration_id)
        if record is None:
            raise NotFoundError(
                "system_configuration_not_found",
                f"System configuration {configuration_id} was not found.",
            )
        return self._refresh_stored_configuration(record)

    def get_active(self) -> SystemConfiguration:
        record = self.session.scalar(
            select(SystemConfiguration).where(SystemConfiguration.is_active.is_(True))
        )
        if record is None:
            raise NotFoundError(
                "active_system_configuration_not_found",
                "No active FPG Core system configuration exists.",
            )
        return self._refresh_stored_configuration(record)

    def update(
        self,
        configuration_id: int,
        payload: SystemConfigurationUpdate,
    ) -> SystemConfiguration:
        record = self.get(configuration_id)
        self._ensure_name_available(payload.name, exclude_id=configuration_id)
        validated = self._validate(payload.configuration_data.model_dump(mode="json"))
        self._validate_schema_version(payload.schema_version, validated)
        record.name = payload.name
        record.description = payload.description
        record.configuration_data = validated.payload
        record.schema_version = str(validated.payload["schema_version"])
        record.fpg_core_version = validated.fpg_core_version
        record.config_hash = validated.config_hash
        self._commit("system_configuration_conflict")
        return record

    def activate(self, configuration_id: int) -> SystemConfiguration:
        record = self.get(configuration_id)
        # Revalidate at activation time against the installed FPG Core version.
        validated = self._validate(record.configuration_data)
        record.configuration_data = validated.payload
        record.fpg_core_version = validated.fpg_core_version
        record.config_hash = validated.config_hash

        self.session.execute(
            update(SystemConfiguration)
            .where(SystemConfiguration.id != record.id)
            .values(is_active=False)
        )
        record.is_active = True
        self._commit("system_configuration_activation_conflict")
        return record

    def delete(self, configuration_id: int) -> None:
        record = self.get(configuration_id)
        if record.is_active:
            raise ConflictError(
                "active_system_configuration_cannot_be_deleted",
                "Deactivate it by activating another profile before deleting it.",
            )
        self.session.delete(record)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "system_configuration_in_use",
                "This configuration is referenced by one or more experiments.",
            ) from exc

    def default_configuration(self) -> ValidatedCoreConfiguration:
        try:
            return self.codec.default_configuration()
        except CoreConfigurationError as exc:
            raise InvalidInputError(
                "fpg_core_default_configuration_unavailable",
                str(exc),
            ) from exc

    def configuration_schema(self) -> dict[str, Any]:
        try:
            document = self.codec.configuration_schema()
        except CoreConfigurationError as exc:
            raise InvalidInputError(
                "fpg_core_configuration_schema_unavailable",
                str(exc),
            ) from exc
        if not isinstance(document, dict):
            raise InvalidInputError(
                "fpg_core_configuration_schema_unavailable",
                "FPG Core returned an invalid configuration schema document.",
            )
        return document

    def _validate(self, payload: Mapping[str, Any]) -> ValidatedCoreConfiguration:
        try:
            return self.codec.validate_payload(payload)
        except CoreConfigurationError as exc:
            raise InvalidInputError(
                "invalid_fpg_core_configuration",
                str(exc),
            ) from exc

    def _refresh_stored_configuration(
        self,
        record: SystemConfiguration,
    ) -> SystemConfiguration:
        validated = self._validate(record.configuration_data)
        configuration_version = str(validated.payload["schema_version"])
        if (
            record.configuration_data != validated.payload
            or record.schema_version != configuration_version
            or record.fpg_core_version != validated.fpg_core_version
            or record.config_hash != validated.config_hash
        ):
            record.configuration_data = validated.payload
            record.schema_version = configuration_version
            record.fpg_core_version = validated.fpg_core_version
            record.config_hash = validated.config_hash
            self._commit("system_configuration_upgrade_conflict")
        return record

    @staticmethod
    def _validate_schema_version(
        envelope_version: str,
        validated: ValidatedCoreConfiguration,
    ) -> None:
        configuration_version = str(validated.payload["schema_version"])
        if envelope_version != configuration_version:
            raise InvalidInputError(
                "system_configuration_schema_version_mismatch",
                "The record schema_version must match configuration_data.schema_version.",
                details={
                    "record_schema_version": envelope_version,
                    "configuration_schema_version": configuration_version,
                },
            )

    def _ensure_name_available(self, name: str, *, exclude_id: int | None = None) -> None:
        statement = select(SystemConfiguration.id).where(SystemConfiguration.name == name)
        if exclude_id is not None:
            statement = statement.where(SystemConfiguration.id != exclude_id)
        if self.session.scalar(statement) is not None:
            raise ConflictError(
                "system_configuration_name_exists",
                f"A system configuration named {name!r} already exists.",
            )

    def _commit(self, code: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                code,
                "The database rejected the system-configuration change.",
            ) from exc
