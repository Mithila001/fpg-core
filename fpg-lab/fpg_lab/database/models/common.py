from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fpg_lab.database.base import Base
from fpg_lab.database.types import JSONDocument

if TYPE_CHECKING:
    from fpg_lab.database.models.p01 import P01Experiment


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class NamespaceRegistry(Base, TimestampMixin):
    __tablename__ = "fpg_namespace_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)


class FloorPlanTemplate(Base, TimestampMixin):
    __tablename__ = "fpg_comm_floor_plan_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_data: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")


class SystemConfiguration(Base, TimestampMixin):
    __tablename__ = "fpg_comm_system_configuration"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration_data: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="6")
    fpg_core_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    experiments: Mapped[list[P01Experiment]] = relationship(
        "P01Experiment", back_populates="system_configuration"
    )


Index(
    "uq_fpg_comm_system_configuration_one_active",
    SystemConfiguration.is_active,
    unique=True,
    sqlite_where=SystemConfiguration.is_active.is_(True),
    postgresql_where=SystemConfiguration.is_active.is_(True),
)
