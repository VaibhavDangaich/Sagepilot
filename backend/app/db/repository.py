"""Data-access functions shared by the API layer and Temporal activities.

Kept as plain functions over an `AsyncSession` (not a class) since there is
a single, small set of tables and no need for a repository abstraction
beyond this.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunActivityLog, Supervisor
from app.domain import (
    ActionName,
    ActivityLogKind,
    ModelConfig,
    SupervisorConfig,
    WakeAggressiveness,
)


def _supervisor_to_domain(row: Supervisor) -> SupervisorConfig:
    return SupervisorConfig(
        id=str(row.id),
        name=row.name,
        base_instruction=row.base_instruction,
        available_actions=row.available_actions,
        default_wake_policy=row.default_wake_policy,
        model_config=ModelConfig(**row.model_config_json),
        wake_aggressiveness=WakeAggressiveness(row.wake_aggressiveness),
        max_workflow_age_hours=row.max_workflow_age_hours,
    )


async def create_supervisor(
    session: AsyncSession,
    *,
    name: str,
    base_instruction: str,
    available_actions: list[ActionName],
    default_wake_policy: str,
    llm_config: ModelConfig,
    wake_aggressiveness: WakeAggressiveness,
    max_workflow_age_hours: int | None,
) -> SupervisorConfig:
    row = Supervisor(
        name=name,
        base_instruction=base_instruction,
        available_actions=[a.value for a in available_actions],
        default_wake_policy=default_wake_policy,
        model_config_json=llm_config.model_dump(),
        wake_aggressiveness=wake_aggressiveness.value,
        max_workflow_age_hours=max_workflow_age_hours,
    )
    session.add(row)
    await session.flush()
    return _supervisor_to_domain(row)


async def get_supervisor(session: AsyncSession, supervisor_id: str) -> SupervisorConfig | None:
    row = await session.get(Supervisor, uuid.UUID(supervisor_id))
    return _supervisor_to_domain(row) if row else None


async def list_supervisors(session: AsyncSession) -> list[SupervisorConfig]:
    result = await session.execute(select(Supervisor).order_by(Supervisor.created_at.desc()))
    return [_supervisor_to_domain(row) for row in result.scalars()]


async def create_run(
    session: AsyncSession, *, supervisor_id: str, order_id: str, temporal_workflow_id: str
) -> Run:
    row = Run(
        supervisor_id=uuid.UUID(supervisor_id),
        order_id=order_id,
        temporal_workflow_id=temporal_workflow_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_run(session: AsyncSession, run_id: str) -> Run | None:
    return await session.get(Run, uuid.UUID(run_id))


async def get_run_by_workflow_id(session: AsyncSession, temporal_workflow_id: str) -> Run | None:
    result = await session.execute(
        select(Run).where(Run.temporal_workflow_id == temporal_workflow_id)
    )
    return result.scalar_one_or_none()


async def list_runs(session: AsyncSession) -> list[Run]:
    result = await session.execute(select(Run).order_by(Run.created_at.desc()))
    return list(result.scalars())


async def update_run(session: AsyncSession, run_id: str, **fields: Any) -> None:
    run = await session.get(Run, uuid.UUID(run_id))
    if run is None:
        raise ValueError(f"run {run_id} not found")
    for key, value in fields.items():
        setattr(run, key, value)


async def append_activity_log(
    session: AsyncSession,
    *,
    run_id: str,
    seq: int,
    kind: ActivityLogKind,
    payload: dict[str, Any],
) -> None:
    session.add(RunActivityLog(run_id=uuid.UUID(run_id), seq=seq, kind=kind.value, payload=payload))


async def get_timeline(
    session: AsyncSession, run_id: str, *, limit: int | None = None
) -> list[RunActivityLog]:
    stmt = (
        select(RunActivityLog)
        .where(RunActivityLog.run_id == uuid.UUID(run_id))
        .order_by(RunActivityLog.seq.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars())
    rows.reverse()
    return rows
