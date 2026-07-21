"""The 5 required business actions.

Per the spec these don't need to send anything externally — each one just
records an activity-log row for the run. Kept intentionally as a single
generic activity (dispatch on `action.name` would only add a switch
statement with identical bodies) rather than 5 near-duplicate activities.
"""

from __future__ import annotations

from pydantic import BaseModel
from temporalio import activity

from app.db.repository import append_activity_log
from app.db.session import session_scope
from app.domain import ActionCall, ActivityLogKind


class ExecuteActionInput(BaseModel):
    run_id: str
    seq: int
    action: ActionCall


@activity.defn
async def execute_action(input: ExecuteActionInput) -> None:
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.seq,
            kind=ActivityLogKind.AGENT_ACTION,
            payload=input.action.model_dump(),
        )
