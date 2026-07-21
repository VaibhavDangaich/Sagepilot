"""Shared Pydantic types used across the workflow, activities, and API layers.

Kept as plain Pydantic models (not dataclasses) because the worker and client
are configured with `temporalio.contrib.pydantic.pydantic_data_converter`,
so these serialize natively as Temporal workflow/activity payloads with no
separate dataclass<->pydantic translation layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class OrderEventType(StrEnum):
    ORDER_CREATED = "order_created"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_FAILED = "payment_failed"
    SHIPMENT_CREATED = "shipment_created"
    SHIPMENT_DELAYED = "shipment_delayed"
    DELIVERED = "delivered"
    REFUND_REQUESTED = "refund_requested"
    CUSTOMER_MESSAGE_RECEIVED = "customer_message_received"
    NO_UPDATE_FOR_N_HOURS = "no_update_for_n_hours"


# Events that, on arrival, end the order lifecycle. Evaluated by the
# workflow's completion rules, never by the agent's own judgment.
TERMINAL_ORDER_EVENTS: frozenset[str] = frozenset({OrderEventType.DELIVERED.value})

# Fast, deterministic, always-wake set: unambiguous enough that they skip
# the LLM classifier entirely (zero latency/cost, no judgment call needed).
DEFAULT_IMPORTANT_EVENTS: frozenset[str] = frozenset(
    {
        OrderEventType.PAYMENT_FAILED.value,
        OrderEventType.SHIPMENT_DELAYED.value,
        OrderEventType.REFUND_REQUESTED.value,
        OrderEventType.CUSTOMER_MESSAGE_RECEIVED.value,
        OrderEventType.DELIVERED.value,
    }
)

# The system's built-in event catalog — used only to decide whether an
# incoming event's type is "known" (eligible for few-shot-informed LLM
# classification) or genuinely unrecognized (force-escalated, see
# classifier_activity.py). event_type itself is a free-text string so the
# UI can send arbitrary custom triggers, not just this list.
KNOWN_EVENT_TYPES: frozenset[str] = frozenset(e.value for e in OrderEventType)


class OrderEvent(BaseModel):
    event_type: str
    data: dict[str, str] = Field(default_factory=dict)


class ActionName(StrEnum):
    MESSAGE_FULFILLMENT_TEAM = "message_fulfillment_team"
    MESSAGE_PAYMENTS_TEAM = "message_payments_team"
    MESSAGE_LOGISTICS_TEAM = "message_logistics_team"
    MESSAGE_CUSTOMER = "message_customer"
    CREATE_INTERNAL_NOTE = "create_internal_note"


class ActionCall(BaseModel):
    name: ActionName
    message: str


class WakeAggressiveness(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class ModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2


class SupervisorConfig(BaseModel):
    """A supervisor template, as configured by the user in the UI."""

    id: str
    name: str
    base_instruction: str
    available_actions: list[ActionName] = Field(default_factory=lambda: list(ActionName))
    default_wake_policy: str = ""
    llm_config: ModelConfig = Field(default_factory=ModelConfig, alias="model_config")
    wake_aggressiveness: WakeAggressiveness = WakeAggressiveness.BALANCED
    max_workflow_age_hours: int | None = None

    # pydantic's own config knob (unrelated to the llm_config field above)
    model_config = {"populate_by_name": True}


class ActivityLogKind(StrEnum):
    INCOMING_EVENT = "incoming_event"
    WAKE_DECISION = "wake_decision"
    SLEEP_DECISION = "sleep_decision"
    AGENT_ACTION = "agent_action"
    MANUAL_INSTRUCTION = "manual_instruction"
    FINAL_OUTPUT = "final_output"
    SYSTEM = "system"


class ClassifyDecision(BaseModel):
    wake_now: bool
    reason: str
    is_unknown_event: bool = Field(
        default=False,
        description="True when the event's type isn't one of the system's known event "
        "types — always paired with wake_now=True so unrecognized input is escalated "
        "for the main agent to interpret, never silently dropped.",
    )


class AgentDecision(BaseModel):
    """Structured output of one agent-runtime invocation (one LangGraph run)."""

    actions: list[ActionCall] = Field(default_factory=list)
    memory_summary: str
    sleep_seconds: int = Field(
        description="How long to sleep before the next scheduled wake-up, in seconds."
    )
    wake_policy: str | None = Field(
        default=None,
        description=(
            "Optional refined guidance for the classifier, e.g. "
            "'wake immediately on shipment_delayed or refund_requested for this order'."
        ),
    )
    reasoning_note: str
    recommend_complete: bool = False
    consulted_lessons: list[str] = Field(
        default_factory=list,
        description=(
            "Past problem/resolution lessons that were surfaced to the agent this turn "
            "(semantic search over the cross-run lessons store, not part of the LLM's "
            "own output — attached by the activity for UI transparency, see README)."
        ),
    )


class FinalOutput(BaseModel):
    """Structured output of the one-time, end-of-run wrap-up agent call."""

    final_summary: str
    key_learnings: str
    feedback: str
    notable_problem: str | None = Field(
        default=None,
        description=(
            "A specific, concrete problem that occurred during this run, worth "
            "remembering for future unrelated orders that hit something similar "
            "(e.g. a particular kind of payment failure or delay). Leave unset if "
            "nothing about this run's issues (if any) is distinctive enough to be "
            "useful to recall later."
        ),
    )
    notable_resolution: str | None = Field(
        default=None,
        description="How notable_problem was resolved. Required if notable_problem is set.",
    )


class LessonSource(StrEnum):
    AGENT = "agent"  # auto-extracted by the wrap-up LLM call at run finalization
    HUMAN = "human"  # manually logged from the UI against a timeline entry


class FaultSide(StrEnum):
    INTERNAL = "internal"  # our side — should carry a resolution
    CLIENT = "client"  # the customer/external party's side


class LessonRecord(BaseModel):
    """A cross-run 'lessons learned' entry — see the README's 'Custom
    addition' section. Not part of the assignment spec; this app's own
    extension for long-term, cross-order memory."""

    id: str
    order_id: str
    event_type: str | None
    problem: str
    resolution: str
    source: LessonSource
    fault: FaultSide | None
    created_at: datetime


class RunSnapshot(BaseModel):
    """Compact state carried across signals and continue_as_new.

    Deliberately excludes the full timeline (that lives in Postgres) — this
    is what keeps continue_as_new payloads small.
    """

    run_id: str
    order_id: str
    supervisor: SupervisorConfig
    started_at: datetime
    additional_instructions: list[str] = Field(default_factory=list)
    memory_summary: str = ""
    wake_policy: str = ""
    next_wake_at: datetime | None = None
    seq_counter: int = 0
    epoch: int = 0
