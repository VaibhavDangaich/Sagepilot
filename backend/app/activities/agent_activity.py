"""The main agent-runtime activity: invokes the LangGraph graph once per
Temporal trigger (workflow start, signal, or scheduled wake-up).

Stateless by design: every call rehydrates the recent timeline from
Postgres rather than relying on any framework-level memory, so Temporal +
Postgres remain the single source of truth for run state.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel
from temporalio import activity

from app.agent.graph import AgentState, build_agent_graph
from app.db.repository import get_timeline
from app.db.session import session_scope
from app.domain import AgentDecision, FinalOutput, RunSnapshot

_RECENT_TIMELINE_LIMIT = 30


def _describe_log_row(kind: str, payload: dict[str, Any]) -> str:
    return f"[{kind}] {payload}"


async def _load_recent_timeline(run_id: str) -> list[str]:
    async with session_scope() as session:
        rows = await get_timeline(session, run_id, limit=_RECENT_TIMELINE_LIMIT)
    return [_describe_log_row(row.kind, row.payload) for row in rows]


class AgentActivityInput(BaseModel):
    snapshot: RunSnapshot
    trigger_reason: str


async def _run_graph(input: AgentActivityInput, *, mode: str) -> AgentDecision | FinalOutput:
    recent_timeline = await _load_recent_timeline(input.snapshot.run_id)
    graph = build_agent_graph()
    initial_state: AgentState = {
        "supervisor": input.snapshot.supervisor,
        "order_id": input.snapshot.order_id,
        "trigger_reason": input.trigger_reason,
        "memory_summary": input.snapshot.memory_summary,
        "wake_policy": input.snapshot.wake_policy,
        "instructions": input.snapshot.additional_instructions,
        "recent_timeline": recent_timeline,
        "mode": mode,
    }
    final_state: AgentState = initial_state
    # stream_mode="values" yields the full accumulated state after each node;
    # heartbeating here lets long LLM calls pass through without the worker
    # mistaking a slow-but-alive activity for a dead one.
    async for state_snapshot in graph.astream(initial_state, stream_mode="values"):
        activity.heartbeat()
        final_state = cast(AgentState, state_snapshot)
    return final_state["decision"]


@activity.defn
async def run_agent(input: AgentActivityInput) -> AgentDecision:
    return cast(AgentDecision, await _run_graph(input, mode="turn"))


@activity.defn
async def run_agent_final_summary(input: AgentActivityInput) -> FinalOutput:
    return cast(FinalOutput, await _run_graph(input, mode="final_summary"))
