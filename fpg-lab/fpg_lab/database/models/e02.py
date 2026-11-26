from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fpg_lab.database.base import Base
from fpg_lab.database.models.common import TimestampMixin
from fpg_lab.database.types import JSONDocument


class E02Run(Base, TimestampMixin):
    __tablename__ = "fpg_e02_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    cases: Mapped[list] = mapped_column(JSONDocument, nullable=False, default=list)
    error: Mapped[dict | None] = mapped_column(JSONDocument)


class E02BSavedPlan(Base, TimestampMixin):
    __tablename__ = "fpg_e02b_saved_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    document: Mapped[dict] = mapped_column(JSONDocument, nullable=False)


class E02BRun(Base, TimestampMixin):
    __tablename__ = "fpg_e02b_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    official: Mapped[dict | None] = mapped_column(JSONDocument)
    diagnostics: Mapped[list | None] = mapped_column(JSONDocument)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error: Mapped[dict | None] = mapped_column(JSONDocument)
