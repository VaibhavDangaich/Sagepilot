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

from app.agent.compaction import compact_memory_if_needed
from app.agent.graph import AgentState, build_agent_graph
from app.db.models import RunActivityLog
from app.db.repository import get_timeline
from app.db.session import session_scope
from app.domain import ActivityLogKind, AgentDecision, FinalOutput, RunSnapshot

# Raw rows fetched before importance filtering, and how many low-signal
# (routine) rows survive that filter — see _load_recent_timeline.
_TIMELINE_LOOKBACK = 60
_LOW_SIGNAL_KEEP = 10

_HIGH_SIGNAL_KINDS = frozenset(
    {
        ActivityLogKind.AGENT_ACTION.value,
        ActivityLogKind.MANUAL_INSTRUCTION.value,
        ActivityLogKind.FINAL_OUTPUT.value,
    }
)


def _is_high_signal(row: RunActivityLog) -> bool:
    if row.kind in _HIGH_SIGNAL_KINDS:
        return True
    # An unknown-event wake/sleep decision is high-signal too — exactly the
    # kind of thing that shouldn't silently age out of context.
    return bool(row.payload.get("is_unknown_event"))


def _describe_log_row(kind: str, payload: dict[str, Any]) -> str:
    return f"[{kind}] {payload}"


async def _load_recent_timeline(run_id: str) -> list[str]:
    """Importance-weighted retention, not a blind sliding window.

    Within the lookback, business actions, manual instructions, final
    output, and unknown-event escalations are always kept regardless of how
    far back they are; everything else (routine wake/sleep decisions,
    ordinary incoming events, system bookkeeping) is capped to the most
    recent few. Older high-signal facts are assumed to already be folded
    into the agent's own rolling `memory_summary` — this window is
    deliberately short-term/detailed context, not the long-term memory.
    """
    async with session_scope() as session:
        rows = await get_timeline(session, run_id, limit=_TIMELINE_LOOKBACK)
    high_signal = [row for row in rows if _is_high_signal(row)]
    low_signal = [row for row in rows if not _is_high_signal(row)][-_LOW_SIGNAL_KEEP:]
    combined = sorted(high_signal + low_signal, key=lambda row: row.seq)
    return [_describe_log_row(row.kind, row.payload) for row in combined]


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
    decision = cast(AgentDecision, await _run_graph(input, mode="turn"))
    compacted_summary = await compact_memory_if_needed(decision.memory_summary)
    if compacted_summary != decision.memory_summary:
        decision = decision.model_copy(update={"memory_summary": compacted_summary})
    return decision


@activity.defn
async def run_agent_final_summary(input: AgentActivityInput) -> FinalOutput:
    return cast(FinalOutput, await _run_graph(input, mode="final_summary"))
