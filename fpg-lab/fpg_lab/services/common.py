from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
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
    CoreConfigCodec,
    CoreConfigurationError,
    ValidatedCoreConfiguration,
)

PRIMARY_PROFILE = "research-default"

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


def seed_namespace_registry(session: Session) -> list[str]:
    existing = set(session.scalars(select(NamespaceRegistry.tag)))
    missing = [item for item in NAMESPACE_SEEDS if item["tag"] not in existing]
    session.add_all(NamespaceRegistry(**item) for item in missing)
    return [item["tag"] for item in missing]


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
    def __init__(self, session: Session, codec: Any = None) -> None:
        self.session = session
        self.codec = codec if codec is not None else CoreConfigCodec()

    def create(self, payload: SystemConfigurationCreate) -> SystemConfiguration:
        self._ensure_name_available(payload.name)
        validated = self._validate_edit(payload)
        record = SystemConfiguration(
            name=payload.name,
            description=payload.description,
            is_active=False,
            **self.configuration_values(validated),
        )
        self.session.add(record)
        self._commit("system_configuration_conflict")
        return record

    def list(self, *, limit: int, offset: int) -> tuple[list[SystemConfiguration], int]:
        total = self.session.scalar(select(func.count()).select_from(SystemConfiguration)) or 0
        rows = self.session.scalars(
            select(SystemConfiguration)
            .order_by(SystemConfiguration.is_active.desc(), SystemConfiguration.id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows), total

    def get(self, configuration_id: int) -> SystemConfiguration:
        record = self.session.get(SystemConfiguration, configuration_id, populate_existing=True)
        if record is None:
            raise NotFoundError(
                "system_configuration_not_found",
                f"System configuration {configuration_id} was not found.",
            )
        return record

    def get_active(self) -> SystemConfiguration:
        record = self.session.scalar(
            select(SystemConfiguration).where(SystemConfiguration.is_active.is_(True))
            .execution_options(populate_existing=True)
        )
        if record is None:
            raise NotFoundError(
                "active_system_configuration_not_found",
                "No active profile. Activate a saved profile using profiles activate <id>.",
            )
        return record

    def resolve(self, configuration_id: int | None = None) -> SystemConfiguration:
        record = self.get_active() if configuration_id is None else self.get(configuration_id)
        if (record.schema_version != "8"
            or not isinstance(record.configuration_data, dict)
            or record.config_hash != self.codec.hash_payload(record.configuration_data)):
            raise InvalidInputError(
                "invalid_profile_metadata",
                f"Profile {record.id} has incompatible schema or hash metadata. Inspect it with lab_db.",
            )
        return record

    def for_flow(self, configuration_id: int | None, flow: str):
        record = self.resolve(configuration_id)
        try:
            return record, self.codec.validate_for_flow(record.configuration_data, flow)
        except CoreConfigurationError as exc:
            raise InvalidInputError(
                "invalid_fpg_core_configuration", f"Profile {record.id}: {exc}"
            ) from exc

    def validate(self, configuration_id: int) -> ValidatedCoreConfiguration:
        record = self.resolve(configuration_id)
        return self.validate_payload(record.configuration_data)

    def duplicate(self, configuration_id: int, name: str) -> SystemConfiguration:
        record = self.resolve(configuration_id)
        return self.create(SystemConfigurationCreate(
            name=name, description=record.description, configuration_data=record.configuration_data,
        ))

    def save(
        self, configuration_id: int, payload: SystemConfigurationUpdate, *, expected_hash: str
    ) -> SystemConfiguration:
        record = self.get(configuration_id)
        if record.name == PRIMARY_PROFILE and payload.name != record.name:
            raise ConflictError("primary_profile_name", f"Keep the primary profile name {PRIMARY_PROFILE!r}.")
        self._ensure_name_available(payload.name, exclude_id=configuration_id)
        return self._save_values(record, expected_hash, self._validate_edit(payload),
                                 name=payload.name, description=payload.description)

    def save_section(self, configuration_id: int, section: str, value: dict, *, expected_hash: str):
        record = self.resolve(configuration_id)
        self._check_hash(record, expected_hash)
        document = deepcopy(record.configuration_data)
        if section == "experiments.e03a":
            document["experiments"]["e03a"] = value
        elif section in {"floor_plan_scoring", "openings"}:
            document[section] = value
        else:
            raise ValueError(f"Unknown editable section {section!r}")
        return self._save_values(record, expected_hash, self.validate_payload(document))

    def _save_values(self, record, expected_hash, validated, **metadata):
        self._check_hash(record, expected_hash)
        try:
            result = self.session.execute(
                update(SystemConfiguration)
                .where(SystemConfiguration.id == record.id,
                       SystemConfiguration.config_hash == expected_hash)
                .values(**metadata, **self.configuration_values(validated))
            )
            if result.rowcount != 1:
                self._stale()
            self._commit("system_configuration_conflict")
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("system_configuration_conflict", "Profile save was rejected.") from exc
        return self.get(record.id)

    def _check_hash(self, record, expected_hash):
        if record.config_hash != expected_hash:
            self._stale()

    def _stale(self):
        self.session.rollback()
        raise ConflictError("profile_changed", "The saved profile changed. Reload it before saving.")

    def activate(self, configuration_id: int) -> SystemConfiguration:
        self.validate(configuration_id)
        record = self.get(configuration_id)
        if not record.is_active:
            self.session.execute(
                update(SystemConfiguration).where(SystemConfiguration.is_active.is_(True))
                .values(is_active=False)
            )
            record.is_active = True
            self._commit("system_configuration_activation_conflict")
        return record

    def delete(self, configuration_id: int) -> None:
        record = self.get(configuration_id)
        if record.is_active or record.name == PRIMARY_PROFILE:
            raise ConflictError(
                "protected_profile", "The active profile and primary profile cannot be deleted."
            )
        self.session.delete(record)
        self._commit("system_configuration_in_use")

    @staticmethod
    def configuration_values(validated: ValidatedCoreConfiguration) -> dict[str, Any]:
        return {
            "configuration_data": validated.payload,
            "schema_version": str(validated.payload["schema_version"]),
            "fpg_core_version": validated.fpg_core_version,
            "config_hash": validated.config_hash,
        }

    def validate_payload(self, payload: Mapping[str, Any]) -> ValidatedCoreConfiguration:
        try:
            return self.codec.validate_payload(payload)
        except CoreConfigurationError as exc:
            raise InvalidInputError("invalid_fpg_core_configuration", str(exc)) from exc

    def _validate_edit(self, payload: SystemConfigurationCreate) -> ValidatedCoreConfiguration:
        validated = self.validate_payload(payload.configuration_data.model_dump(mode="json"))
        if payload.schema_version != str(validated.payload["schema_version"]):
            raise InvalidInputError(
                "system_configuration_schema_version_mismatch",
                "The record schema_version must match configuration_data.schema_version.",
            )
        return validated

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
