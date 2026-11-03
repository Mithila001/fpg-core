from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fpg_lab.database.base import Base
from fpg_lab.database.models.common import TimestampMixin, utc_now
from fpg_lab.database.types import JSONDocument

if TYPE_CHECKING:
    from fpg_lab.database.models.common import SystemConfiguration


class P01Experiment(Base, TimestampMixin):
    __tablename__ = "fpg_p01_experiment"
    __table_args__ = (
        CheckConstraint("flow_type IN ('p01a', 'p01b', 'p01c')", name="ck_p01_flow_type"),
        Index("ix_fpg_p01_experiment_flow_status_created", "flow_type", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_type: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stop_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    requested_trial_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_trial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_trial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_trial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    persist_trial_data: Mapped[bool] = mapped_column(nullable=False, default=True)

    floor_plan_request: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    hint_points: Mapped[dict | None] = mapped_column(JSONDocument, nullable=True)
    preprocessing_result: Mapped[dict | list | None] = mapped_column(JSONDocument, nullable=True)

    system_configuration_id: Mapped[int] = mapped_column(
        ForeignKey("fpg_comm_system_configuration.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    system_configuration_snapshot: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    system_configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fpg_core_version: Mapped[str] = mapped_column(String(64), nullable=False)

    best_trial_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_plan_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_floor_plan_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_floor_plan_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_floor_plan_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_data: Mapped[dict | None] = mapped_column(JSONDocument, nullable=True)
    termination_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    system_configuration: Mapped[SystemConfiguration] = relationship(
        "SystemConfiguration", back_populates="experiments"
    )
    candidate_trials: Mapped[list[P01CandidateTrial]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="P01CandidateTrial.trial_no",
    )
    floor_plan_runs: Mapped[list[P01FloorPlanRun]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="P01FloorPlanRun.id",
    )


class P01CandidateTrial(Base):
    __tablename__ = "fpg_p01_candidate_trial"
    __table_args__ = (
        UniqueConstraint("experiment_id", "trial_no", name="uq_p01_trial_experiment_no"),
        UniqueConstraint("id", "experiment_id", name="uq_p01_trial_id_experiment"),
        Index("ix_fpg_p01_trial_experiment_score", "experiment_id", "final_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("fpg_p01_experiment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trial_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_search_data: Mapped[dict | list | None] = mapped_column(JSONDocument)
    circulation_data: Mapped[dict | list | None] = mapped_column(JSONDocument)
    candidate_scoring_data: Mapped[dict | list | None] = mapped_column(JSONDocument)
    final_score: Mapped[float | None] = mapped_column(Float)
    error_data: Mapped[dict | None] = mapped_column(JSONDocument)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    experiment: Mapped[P01Experiment] = relationship(back_populates="candidate_trials")


class P01FloorPlanRun(Base):
    __tablename__ = "fpg_p01_floor_plan_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_trial_id", "experiment_id"],
            ["fpg_p01_candidate_trial.id", "fpg_p01_candidate_trial.experiment_id"],
            ondelete="CASCADE",
            name="fk_p01_run_source_trial_experiment",
        ),
        UniqueConstraint("source_trial_id", name="uq_p01_run_source_trial"),
        Index("ix_fpg_p01_run_experiment_status", "experiment_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("fpg_p01_experiment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_trial_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    source_candidate_data: Mapped[dict | None] = mapped_column(JSONDocument)
    circulation_data: Mapped[dict | None] = mapped_column(JSONDocument)
    generation_specification: Mapped[dict | None] = mapped_column(JSONDocument)
    initial_solver_data: Mapped[dict | None] = mapped_column(JSONDocument)
    refinement_a_data: Mapped[dict | None] = mapped_column(JSONDocument)
    refinement_b_data: Mapped[dict | None] = mapped_column(JSONDocument)
    post_processing_data: Mapped[dict | None] = mapped_column(JSONDocument)
    opening_generation_data: Mapped[dict | None] = mapped_column(JSONDocument)
    floor_plan_scoring_data: Mapped[dict | None] = mapped_column(JSONDocument)
    final_floor_plan: Mapped[dict | None] = mapped_column(JSONDocument)
    final_score: Mapped[float | None] = mapped_column(Float)
    error_data: Mapped[dict | None] = mapped_column(JSONDocument)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    experiment: Mapped[P01Experiment] = relationship(back_populates="floor_plan_runs")
