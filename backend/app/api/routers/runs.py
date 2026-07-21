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
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client, WorkflowHandle

from app.api import schemas
from app.api.deps import get_temporal_client
from app.api.schemas import AddInstructionRequest, CreateRunRequest, InjectEventRequest
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
