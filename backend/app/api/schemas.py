"""Request bodies for the API layer. Responses reuse the domain models
directly (SupervisorConfig, AgentDecision, etc.) rather than duplicating
near-identical shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import LongTermLesson, Run, RunActivityLog
from app.domain import (
    ActionName,
    FaultSide,
    LessonRecord,
    ModelConfig,
    OrderEvent,
    WakeAggressiveness,
)


class CreateSupervisorRequest(BaseModel):
    name: str
    base_instruction: str
    available_actions: list[ActionName] = Field(default_factory=lambda: list(ActionName))
    default_wake_policy: str = ""
    llm_config: ModelConfig = Field(default_factory=ModelConfig, alias="model_config")
    wake_aggressiveness: WakeAggressiveness = WakeAggressiveness.BALANCED
    max_workflow_age_hours: int | None = None

    model_config = {"populate_by_name": True}


class CreateRunRequest(BaseModel):
    supervisor_id: str
    order_id: str
    initial_instruction: str | None = None


class AddInstructionRequest(BaseModel):
    instruction: str


class InjectEventRequest(BaseModel):
    event: OrderEvent


class ChatRequest(BaseModel):
    """A one-off, stateless question about a specific order's supervision
    history — custom addition beyond the spec (see README). Deliberately
    not a conversation: each question is answered fresh from that order's
    current timeline/memory, with no server-side chat history, and it's
    kept entirely separate from the actual order-supervisor agent (an
    admin analysis tool, not a second cooperating agent)."""

    question: str


class ChatResponse(BaseModel):
    answer: str


class LogLessonRequest(BaseModel):
    """A human-curated lesson — the manual counterpart to the AI-inferred
    lessons captured automatically at run finalization. `problem` is
    expected to already describe the specific event it's about (the UI
    pre-fills it from the timeline entry the user is annotating). Custom
    addition beyond the spec, see README."""

    fault: FaultSide
    problem: str
    resolution: str = ""


class RunSummary(BaseModel):
    id: str
    supervisor_id: str
    order_id: str
    temporal_workflow_id: str
    status: str
    next_wake_at: datetime | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RunDetail(RunSummary):
    memory_summary: str
    wake_policy: str
    final_summary: str | None
    final_learnings: str | None
    final_feedback: str | None


class TimelineEntry(BaseModel):
    seq: int
    kind: str
    payload: dict[str, Any]
    created_at: datetime


def run_to_summary(row: Run) -> RunSummary:
    return RunSummary(
        id=str(row.id),
        supervisor_id=str(row.supervisor_id),
        order_id=row.order_id,
        temporal_workflow_id=row.temporal_workflow_id,
        status=row.status,
        next_wake_at=row.next_wake_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def run_to_detail(row: Run) -> RunDetail:
    return RunDetail(
        **run_to_summary(row).model_dump(),
        memory_summary=row.memory_summary,
        wake_policy=row.wake_policy,
        final_summary=row.final_summary,
        final_learnings=row.final_learnings,
        final_feedback=row.final_feedback,
    )


def log_row_to_entry(row: RunActivityLog) -> TimelineEntry:
    return TimelineEntry(seq=row.seq, kind=row.kind, payload=row.payload, created_at=row.created_at)


def lesson_to_record(row: LongTermLesson) -> LessonRecord:
    return LessonRecord(
        id=str(row.id),
        order_id=row.order_id,
        event_type=row.event_type,
        problem=row.problem,
        resolution=row.resolution,
        source=row.source,
        fault=row.fault,
        created_at=row.created_at,
    )
