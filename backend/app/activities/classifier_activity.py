"""Wake-up classifier: decides whether an incoming order event is important
enough to wake the main agent now, or whether the workflow should stay
asleep until its next scheduled wake-up.

Hybrid design:
  - A handful of unambiguous, safety-critical event types (payment_failed,
    shipment_delayed, refund_requested, customer_message_received,
    delivered) always wake immediately via a deterministic fast path — no
    LLM call, zero latency/cost, no judgment call needed.
  - An "aggressive" supervisor config always wakes too (same fast path).
  - Everything else — routine known event types AND any free-text/custom
    trigger the UI lets you type — goes through a small LLM call
    (`_llm_classify`) with a handful of few-shot examples baked into its
    system prompt, so it generalizes beyond the fixed event catalog.
  - Genuinely unrecognized event types are force-escalated in code
    (`wake_now=True`, `is_unknown_event=True`) regardless of what the LLM
    returns — escalation of unknown input must not depend on LLM
    reliability. The LLM is still asked for a reason so the main agent gets
    a useful interpretation to act on, not just a bare flag.
"""

from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from temporalio import activity

from app.agent.llm import build_chat_model, default_model_for
from app.config import get_settings
from app.db.repository import append_activity_log
from app.db.session import session_scope
from app.domain import (
    DEFAULT_IMPORTANT_EVENTS,
    KNOWN_EVENT_TYPES,
    ActivityLogKind,
    ClassifyDecision,
    OrderEvent,
    WakeAggressiveness,
)

_FEW_SHOT_EXAMPLES = """\
Examples of how to classify events (event type -> data -> decision):

- order_created -> {} -> wake_now=false
  reason="routine lifecycle start, nothing to act on yet"
- shipment_created -> {} -> wake_now=false
  reason="routine fulfillment update"
- no_update_for_n_hours -> {"hours": "6"} -> wake_now=false
  reason="inactivity alone isn't urgent unless the wake policy says otherwise"
- payment_failed -> {} -> wake_now=true
  reason="payment issues need prompt attention"
- customer_message_received -> {"message": "where is my order?"} -> wake_now=true
  reason="a human is waiting on a response"
- carrier_lost_package -> {} -> wake_now=true, is_unknown_event=true
  reason="not one of the system's known event types — escalating for the main agent"
"""

_SYSTEM_PROMPT_TEMPLATE = """You are a lightweight event-importance classifier for an AI \
order supervisor. You are NOT the main reasoning agent — you only decide whether an \
incoming event should wake it up right now, or whether it can wait until the next \
scheduled check.

{few_shot}

The system's known event types are: {known_types}. If the incoming event's type is not \
in that list, treat it as unknown: set is_unknown_event=true and wake_now=true \
regardless of how routine it sounds — unrecognized input must always be escalated to \
the main agent, never silently ignored.

The supervisor's current wake-policy guidance for this specific order (if any) is: \
"{wake_policy}" — treat this as an override that can widen what counts as important."""


async def _llm_classify(event: OrderEvent, wake_policy: str) -> ClassifyDecision:
    provider = get_settings().default_provider
    llm = build_chat_model(
        provider=provider,
        model=default_model_for(provider),
        temperature=0,
    ).with_structured_output(ClassifyDecision)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        few_shot=_FEW_SHOT_EXAMPLES,
        known_types=", ".join(sorted(KNOWN_EVENT_TYPES)),
        wake_policy=wake_policy or "(none set)",
    )
    decision = cast(
        ClassifyDecision,
        await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"event_type: {event.event_type}\ndata: {event.data}"),
            ]
        ),
    )
    if event.event_type not in KNOWN_EVENT_TYPES:
        # Never trust the LLM alone to catch this — force it deterministically.
        decision = decision.model_copy(update={"wake_now": True, "is_unknown_event": True})
    return decision


async def _classify(
    event: OrderEvent, wake_policy: str, aggressiveness: WakeAggressiveness
) -> ClassifyDecision:
    if event.event_type in DEFAULT_IMPORTANT_EVENTS:
        return ClassifyDecision(
            wake_now=True, reason=f"'{event.event_type}' is always treated as important"
        )
    if aggressiveness is WakeAggressiveness.AGGRESSIVE:
        return ClassifyDecision(
            wake_now=True, reason="supervisor is configured to wake aggressively on any event"
        )
    return await _llm_classify(event, wake_policy)


class HandleIncomingEventInput(BaseModel):
    run_id: str
    event: OrderEvent
    event_seq: int
    decision_seq: int
    wake_policy: str
    wake_aggressiveness: WakeAggressiveness


@activity.defn
async def handle_incoming_event(input: HandleIncomingEventInput) -> ClassifyDecision:
    decision = await _classify(input.event, input.wake_policy, input.wake_aggressiveness)
    async with session_scope() as session:
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.event_seq,
            kind=ActivityLogKind.INCOMING_EVENT,
            payload=input.event.model_dump(mode="json"),
        )
        await append_activity_log(
            session,
            run_id=input.run_id,
            seq=input.decision_seq,
            kind=(
                ActivityLogKind.WAKE_DECISION
                if decision.wake_now
                else ActivityLogKind.SLEEP_DECISION
            ),
            payload=decision.model_dump(),
        )
    return decision
