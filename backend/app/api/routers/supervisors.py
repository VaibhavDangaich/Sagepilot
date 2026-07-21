from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CreateSupervisorRequest
from app.db import repository
from app.db.session import get_session
from app.domain import SupervisorConfig

router = APIRouter(prefix="/api/supervisors", tags=["supervisors"])


@router.post("", response_model=SupervisorConfig, response_model_by_alias=True)
async def create_supervisor(
    body: CreateSupervisorRequest, session: AsyncSession = Depends(get_session)
) -> SupervisorConfig:
    return await repository.create_supervisor(
        session,
        name=body.name,
        base_instruction=body.base_instruction,
        available_actions=body.available_actions,
        default_wake_policy=body.default_wake_policy,
        llm_config=body.llm_config,
        wake_aggressiveness=body.wake_aggressiveness,
        max_workflow_age_hours=body.max_workflow_age_hours,
    )


@router.get("", response_model=list[SupervisorConfig], response_model_by_alias=True)
async def list_supervisors(
    session: AsyncSession = Depends(get_session),
) -> list[SupervisorConfig]:
    return await repository.list_supervisors(session)


@router.get("/{supervisor_id}", response_model=SupervisorConfig, response_model_by_alias=True)
async def get_supervisor(
    supervisor_id: str, session: AsyncSession = Depends(get_session)
) -> SupervisorConfig:
    config = await repository.get_supervisor(session, supervisor_id)
    if config is None:
        raise HTTPException(status_code=404, detail="supervisor not found")
    return config
