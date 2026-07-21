"""SQLAlchemy ORM models mirroring db/schema.sql."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    # All datetime columns are timestamptz in schema.sql; without this every
    # `Mapped[datetime]` column defaults to a naive TIMESTAMP, which then
    # rejects the timezone-aware datetimes produced by workflow.now() /
    # datetime.now(UTC).
    type_annotation_map = {datetime: DateTime(timezone=True)}


class Supervisor(Base):
    __tablename__ = "supervisors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    base_instruction: Mapped[str] = mapped_column(Text)
    available_actions: Mapped[list[str]] = mapped_column(JSONB)
    default_wake_policy: Mapped[str] = mapped_column(Text, default="")
    model_config_json: Mapped[dict[str, Any]] = mapped_column("model_config", JSONB)
    wake_aggressiveness: Mapped[str] = mapped_column(Text, default="balanced")
    max_workflow_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supervisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supervisors.id"))
    order_id: Mapped[str] = mapped_column(Text)
    temporal_workflow_id: Mapped[str] = mapped_column(String, unique=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active")
    memory_summary: Mapped[str] = mapped_column(Text, default="")
    wake_policy: Mapped[str] = mapped_column(Text, default="")
    next_wake_at: Mapped[datetime | None] = mapped_column(nullable=True)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_learnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    seq_counter: Mapped[int] = mapped_column(Integer, default=0)
    epoch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RunActivityLog(Base):
    __tablename__ = "run_activity_log"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"))
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LongTermLesson(Base):
    """Cross-run 'lessons learned' — a custom addition beyond the spec, see
    README. `embedding` is a plain Postgres array (not pgvector — see the
    comment in schema.sql for why), so similarity search is computed in
    Python rather than pushed down to the database."""

    __tablename__ = "long_term_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supervisors.id"), nullable=True
    )
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    order_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float))
    source: Mapped[str] = mapped_column(Text, default="agent")
    fault: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
