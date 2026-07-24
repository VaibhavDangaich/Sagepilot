"""Second-pass memory compaction.

The agent already produces a rolling `memory_summary` every turn — the
baseline "simple context compaction" the spec calls for ("maintaining a
rolling summary"). This adds one more layer on top of that baseline: if the
summary itself grows past a length threshold, spend one extra small LLM
call compressing it further, so a very long-running order doesn't end up
feeding an ever-growing wall of prose into every future turn's context.
Most turns never hit the threshold, so this adds no cost to the common case.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import build_chat_model, default_model_for
from app.config import get_settings

_COMPACTION_THRESHOLD_CHARS = 600

_COMPACTION_PROMPT = (
    "Compress the following AI order-supervisor memory summary into at most two "
    "dense sentences. Preserve every concrete fact that would matter to a future "
    "check-in — open issues, escalations taken, current status — and drop anything "
    "routine or superseded by later information."
)


async def compact_memory_if_needed(memory_summary: str) -> str:
    if len(memory_summary) <= _COMPACTION_THRESHOLD_CHARS:
        return memory_summary
    provider = get_settings().default_provider
    llm = build_chat_model(provider=provider, model=default_model_for(provider), temperature=0)
    result = await llm.ainvoke(
        [SystemMessage(content=_COMPACTION_PROMPT), HumanMessage(content=memory_summary)]
    )
    compacted = result.content
    return compacted if isinstance(compacted, str) and compacted.strip() else memory_summary
