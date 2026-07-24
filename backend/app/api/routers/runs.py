"""Run lifecycle endpoints: start/list/inspect a run, inject events and
instructions, and control (pause/resume/terminate).

Deliberately references the workflow and its signals by string name
(`_WORKFLOW_TYPE`, `"order_event"`, etc.) rather than importing the
workflow module directly — the API process only needs to start workflows
and send signals, not execute agent/LangGraph code, so it has no reason to
import that module's (heavier) dependency chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client, WorkflowHandle

from app.agent.embeddings import embed_text
from app.agent.llm import build_chat_model, default_model_for
from app.api import schemas
from app.api.deps import get_temporal_client
from app.api.schemas import (
    AddInstructionRequest,
    ChatRequest,
    ChatResponse,
    CreateRunRequest,
    InjectEventRequest,
    LogLessonRequest,
)
from app.config import get_settings
from app.db import repository
from app.db.session import get_session
from app.domain import RunSnapshot

router = APIRouter(prefix="/api/runs", tags=["runs"])

_WORKFLOW_TYPE = "OrderSupervisorWorkflow"


@router.post("", response_model=schemas.RunSummary)
async def create_run(
    body: CreateRunRequest,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> schemas.RunSummary:
    supervisor = await repository.get_supervisor(session, body.supervisor_id)
    if supervisor is None:
        raise HTTPException(status_code=404, detail="supervisor not found")

    workflow_id = f"order-{body.order_id}-{uuid4().hex[:8]}"
    run_row = await repository.create_run(
        session,
        supervisor_id=body.supervisor_id,
        order_id=body.order_id,
        temporal_workflow_id=workflow_id,
    )
    run_id = str(run_row.id)

    snapshot = RunSnapshot(
        run_id=run_id,
        order_id=body.order_id,
        supervisor=supervisor,
        started_at=datetime.now(UTC),
        additional_instructions=[body.initial_instruction] if body.initial_instruction else [],
    )
    handle = await temporal_client.start_workflow(
        _WORKFLOW_TYPE,
        snapshot,
        id=workflow_id,
        task_queue=get_settings().temporal_task_queue,
    )
    await repository.update_run(session, run_id, temporal_run_id=handle.first_execution_run_id)
    return schemas.run_to_summary(run_row)


@router.get("", response_model=list[schemas.RunSummary])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[schemas.RunSummary]:
    rows = await repository.list_runs(session)
    return [schemas.run_to_summary(row) for row in rows]


@router.get("/{run_id}", response_model=schemas.RunDetail)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> schemas.RunDetail:
    row = await repository.get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return schemas.run_to_detail(row)


@router.get("/{run_id}/timeline", response_model=list[schemas.TimelineEntry])
async def get_timeline(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[schemas.TimelineEntry]:
    rows = await repository.get_timeline(session, run_id)
    return [schemas.log_row_to_entry(row) for row in rows]


@router.get("/{run_id}/memory")
async def get_memory(run_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    row = await repository.get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"memory_summary": row.memory_summary, "wake_policy": row.wake_policy}


@router.post("/{run_id}/lessons", status_code=201)
async def log_lesson(
    run_id: str,
    body: LogLessonRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Human-curated lesson, logged directly against this run — the manual
    counterpart to the AI-inferred lessons captured automatically at run
    finalization. A custom addition beyond the spec (see README); this is a
    quick out-of-band annotation, not part of the durable order-lifecycle
    workflow, so it talks to the DB directly rather than through a Temporal
    signal/activity."""
    row = await repository.get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    embedding = await embed_text(body.problem)
    await repository.insert_lesson(
        session,
        supervisor_id=str(row.supervisor_id),
        source_run_id=run_id,
        order_id=row.order_id,
        event_type=None,
        problem=body.problem,
        resolution=body.resolution,
        embedding=embedding,
        source="human",
        fault=body.fault.value,
    )
    return {"status": "logged"}


async def _get_handle(
    session: AsyncSession, temporal_client: Client, run_id: str
) -> WorkflowHandle[Any, Any]:
    row = await repository.get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return temporal_client.get_workflow_handle(row.temporal_workflow_id)


@router.post("/{run_id}/events", status_code=202)
async def inject_event(
    run_id: str,
    body: InjectEventRequest,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> dict[str, str]:
    handle = await _get_handle(session, temporal_client, run_id)
    await handle.signal("order_event", body.event)
    return {"status": "accepted"}


@router.post("/{run_id}/instructions", status_code=202)
async def add_instruction(
    run_id: str,
    body: AddInstructionRequest,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> dict[str, str]:
    handle = await _get_handle(session, temporal_client, run_id)
    await handle.signal("add_instruction", body.instruction)
    return {"status": "accepted"}


@router.post("/{run_id}/interrupt", status_code=202)
async def interrupt_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> dict[str, str]:
    handle = await _get_handle(session, temporal_client, run_id)
    await handle.signal("interrupt")
    return {"status": "accepted"}


@router.post("/{run_id}/resume", status_code=202)
async def resume_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> dict[str, str]:
    handle = await _get_handle(session, temporal_client, run_id)
    await handle.signal("resume")
    return {"status": "accepted"}


@router.post("/{run_id}/terminate", status_code=202)
async def terminate_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> dict[str, str]:
    handle = await _get_handle(session, temporal_client, run_id)
    await handle.signal("terminate")
    return {"status": "accepted"}


_CHAT_SYSTEM_PROMPT_TEMPLATE = """You are answering an admin's question about a single \
order's supervision history. Answer ONLY from the context below — if the answer isn't \
in it, say so plainly rather than guessing.

Order: {order_id}
Supervisor base instruction: {base_instruction}
Current status: {status}
Current memory summary: {memory_summary}
Current wake policy: {wake_policy}
{final_output_block}

Full timeline (chronological, one entry per line):
{timeline_text}"""


@router.post("/{run_id}/chat", response_model=ChatResponse)
async def chat_about_run(
    run_id: str, body: ChatRequest, session: AsyncSession = Depends(get_session)
) -> ChatResponse:
    """Stateless Q&A grounded in this order's own timeline/memory — a
    custom addition beyond the spec (see README). Kept deliberately
    separate from the order-supervisor agent: this only ever reads and
    answers, it never acts on the order."""
    run = await repository.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    supervisor = await repository.get_supervisor(session, str(run.supervisor_id))
    timeline = await repository.get_timeline(session, run_id)
    timeline_text = "\n".join(f"[seq {row.seq}] [{row.kind}] {row.payload}" for row in timeline)
    final_output_block = (
        f"Final summary: {run.final_summary}\nKey learnings: {run.final_learnings}"
        if run.final_summary
        else ""
    )

    system_prompt = _CHAT_SYSTEM_PROMPT_TEMPLATE.format(
        order_id=run.order_id,
        base_instruction=supervisor.base_instruction if supervisor else "(unknown)",
        status=run.status,
        memory_summary=run.memory_summary or "(empty)",
        wake_policy=run.wake_policy or "(none set)",
        final_output_block=final_output_block,
        timeline_text=timeline_text or "(no activity yet)",
    )
    provider = get_settings().default_provider
    llm = build_chat_model(provider=provider, model=default_model_for(provider), temperature=0)
    result = await llm.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=body.question)]
    )
    return ChatResponse(answer=str(result.content))
