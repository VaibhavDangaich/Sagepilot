"""LangGraph agent runtime: load_context -> reason -> (assemble_decision).

Each invocation is stateless — it rehydrates the full prompt from the
snapshot + recent timeline passed in, and returns a structured decision.
There is deliberately no LangGraph checkpointer here: Temporal + Postgres
are the single source of truth for run state, and re-introducing a second
persistence layer inside LangGraph would create two competing sources of
truth for the same data.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.domain import AgentDecision, FinalOutput, SupervisorConfig

_SYSTEM_PROMPT = (
    "You are a careful, terse AI supervisor for a single e-commerce order. "
    "You reason about the order's current state and decide what, if "
    "anything, needs to happen next. You do not run continuously — you are "
    "invoked once per turn and must decide how long to sleep until the next "
    "check."
)


class AgentState(TypedDict):
    supervisor: SupervisorConfig
    order_id: str
    trigger_reason: str
    memory_summary: str
    wake_policy: str
    instructions: list[str]
    recent_timeline: list[str]
    # Cross-run "lessons learned" from semantically similar past issues on
    # *other* orders — a custom addition beyond the spec, see README.
    relevant_lessons: NotRequired[list[str]]
    mode: str  # "turn" | "final_summary"
    prompt: NotRequired[str]
    decision: NotRequired[AgentDecision | FinalOutput]


def _render_context(state: AgentState) -> str:
    supervisor = state["supervisor"]
    timeline_block = "\n".join(state["recent_timeline"]) or "(no prior activity)"
    instructions_block = "\n".join(f"- {i}" for i in state["instructions"]) or "(none)"
    lessons = state.get("relevant_lessons") or []
    lessons_block = (
        "\n\n".join(lessons) if lessons else "(none found similar enough to this situation)"
    )
    return f"""Order: {state["order_id"]}

Base instruction: {supervisor.base_instruction}

Additional run-specific instructions:
{instructions_block}

Compact memory summary so far:
{state["memory_summary"] or "(empty — this is the first turn)"}

Recent timeline (most recent last):
{timeline_block}

Relevant lessons from past, unrelated orders (may or may not apply here — use your \
judgment):
{lessons_block}

You were invoked because: {state["trigger_reason"]}"""


def load_context(state: AgentState) -> dict[str, Any]:
    if state["mode"] == "final_summary":
        prompt = f"""{_render_context(state)}

This run is ending. Produce a final wrap-up: a concise final summary of \
what happened, the key learnings for next time, and any feedback or \
recommendations for whoever configured this supervisor. If a specific, \
concrete problem occurred during this run (not a routine event), also set \
notable_problem and notable_resolution describing it and how it was \
handled — this gets remembered for future, unrelated orders that hit \
something similar. Leave both unset if nothing about this run's issues \
(if any) is distinctive enough to be worth recalling later."""
    else:
        supervisor = state["supervisor"]
        actions_list = ", ".join(a.value for a in supervisor.available_actions)
        prompt = f"""{_render_context(state)}

Decide what, if anything, to do next. You may call zero or more of the \
available business actions ({actions_list}) — each with a short message \
describing what it communicates. Always return an updated compact memory \
summary (fold in anything from the recent timeline worth remembering \
long-term), how many seconds to sleep before the next scheduled check, a \
short one-line reasoning note, and whether you believe the order's \
lifecycle is complete (the workflow, not you, has the final say on \
ending the run). Optionally refine the wake-up policy guidance used by \
the lightweight event classifier, e.g. "wake immediately on \
shipment_delayed or refund_requested for this order"."""
    return {"prompt": prompt}


async def reason(state: AgentState) -> dict[str, Any]:
    # Async so the (potentially slow) LLM call never blocks the worker's
    # event loop while other activities are in flight alongside it.
    supervisor = state["supervisor"]
    output_schema = FinalOutput if state["mode"] == "final_summary" else AgentDecision
    llm = ChatOpenAI(
        model=supervisor.llm_config.model,
        temperature=supervisor.llm_config.temperature,
        # Passed explicitly rather than relying on the OPENAI_API_KEY
        # process env var: pydantic-settings loads .env into our own
        # Settings object only, it never exports values into os.environ.
        api_key=get_settings().openai_api_key,
    ).with_structured_output(output_schema)
    decision = await llm.ainvoke(
        [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=state["prompt"])]
    )
    return {"decision": decision}


def build_agent_graph() -> CompiledStateGraph[AgentState, Any, AgentState, AgentState]:
    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context)
    graph.add_node("reason", reason)
    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "reason")
    graph.add_edge("reason", END)
    return graph.compile()
