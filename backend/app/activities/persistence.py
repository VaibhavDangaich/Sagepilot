"""Activities that persist run state and lifecycle bookkeeping to Postgres.

Wall-clock time (`datetime.now`) is fine here — these run inside Temporal
*activities*, not workflow code, so there's no determinism/replay concern.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from temporalio import activity

from app.db.repository import append_activity_log, update_run
from app.db.session import session_scope
from app.domain import ActivityLogKind


class PersistRunStateInput(BaseModel):
    run_id: str
    seq: int
    seq_counter: int
    memory_summary: str
    wake_policy: str
    next_wake_at: datetime | None
    reasoning_note: str
    sleep_seconds: int
    status: str
    consulted_lessons: list[str] = Field(default_factory=list)


@activity.defn
async def persist_run_state(input: PersistRunStateInput) -> None:
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.SLEEP_DECISION,
            payload={
                "reasoning_note": input.reasoning_note,
                "sleep_seconds": input.sleep_seconds,
                "next_wake_at": input.next_wake_at.isoformat() if input.next_wake_at else None,
                "memory_summary": input.memory_summary,
                "wake_policy": input.wake_policy,
                "consulted_lessons": input.consulted_lessons,
            },
        )
        await update_run(
            session,
            input.run_id,
            memory_summary=input.memory_summary,
            wake_policy=input.wake_policy,
            next_wake_at=input.next_wake_at,
            seq_counter=input.seq_counter,
            status=input.status,
        )


class RecordFinalOutputInput(BaseModel):
    run_id: str
    seq: int
    seq_counter: int
    final_summary: str
    final_learnings: str
    final_feedback: str
    status: str


@activity.defn
async def record_final_output(input: RecordFinalOutputInput) -> None:
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.FINAL_OUTPUT,
            payload={
                "final_summary": input.final_summary,
                "final_learnings": input.final_learnings,
                "final_feedback": input.final_feedback,
            },
        )
        await update_run(
            session,
            input.run_id,
            final_summary=input.final_summary,
            final_learnings=input.final_learnings,
            final_feedback=input.final_feedback,
            seq_counter=input.seq_counter,
            status=input.status,
            completed_at=datetime.now(UTC),
        )


class RecordManualInstructionInput(BaseModel):
    run_id: str
    seq: int
    instruction: str


@activity.defn
async def record_manual_instruction(input: RecordManualInstructionInput) -> None:
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.MANUAL_INSTRUCTION,
            payload={"instruction": input.instruction},
        )


class RecordSystemEventInput(BaseModel):
    run_id: str
    seq: int
    message: str


@activity.defn
async def record_system_event(input: RecordSystemEventInput) -> None:
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.SYSTEM,
            payload={"message": input.message},
        )


class SetRunStatusInput(BaseModel):
    run_id: str
    seq: int
    status: str
    message: str


@activity.defn
async def set_run_status(input: SetRunStatusInput) -> None:
    """Used for status transitions that aren't tied to a full agent turn,
    e.g. pause/resume from the UI, so the DB-backed status the API/UI read
    reflects reality immediately rather than only after the next turn."""
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.SYSTEM,
            payload={"message": input.message},
        )
        await update_run(session, input.run_id, status=input.status)
