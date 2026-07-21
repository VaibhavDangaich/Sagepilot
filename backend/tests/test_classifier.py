"""Unit tests for the wake classifier — no live OpenAI calls.

The deterministic fast paths (always-important events, aggressive mode) are
tested directly. The LLM-backed path is tested with a mocked `ChatOpenAI` so
we can prove the *code-level* force-escalation override for unknown event
types actually works — deliberately having the mocked LLM get it "wrong" to
show the override doesn't depend on the LLM behaving correctly.
"""

from __future__ import annotations

from typing import Any

from app.activities import classifier_activity
from app.domain import ClassifyDecision, OrderEvent, WakeAggressiveness


async def test_always_important_event_wakes_without_calling_the_llm() -> None:
    event = OrderEvent(event_type="payment_failed")
    decision = await classifier_activity._classify(
        event, wake_policy="", aggressiveness=WakeAggressiveness.CONSERVATIVE
    )
    assert decision.wake_now is True
    assert decision.is_unknown_event is False


async def test_aggressive_supervisor_wakes_on_any_event_without_calling_the_llm() -> None:
    event = OrderEvent(event_type="shipment_created")
    decision = await classifier_activity._classify(
        event, wake_policy="", aggressiveness=WakeAggressiveness.AGGRESSIVE
    )
    assert decision.wake_now is True


class _FakeStructuredLLM:
    def __init__(self, canned: ClassifyDecision) -> None:
        self._canned = canned

    async def ainvoke(self, messages: list[Any]) -> ClassifyDecision:
        return self._canned


class _FakeChatOpenAI:
    def __init__(self, canned: ClassifyDecision) -> None:
        self._canned = canned

    def with_structured_output(self, schema: type) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._canned)


def _patch_llm(monkeypatch: Any, canned: ClassifyDecision) -> None:
    monkeypatch.setattr(classifier_activity, "ChatOpenAI", lambda **kwargs: _FakeChatOpenAI(canned))


async def test_known_routine_event_uses_the_llms_classification(monkeypatch: Any) -> None:
    _patch_llm(monkeypatch, ClassifyDecision(wake_now=False, reason="routine, no action needed"))
    event = OrderEvent(event_type="order_created")
    decision = await classifier_activity._classify(
        event, wake_policy="", aggressiveness=WakeAggressiveness.BALANCED
    )
    assert decision.wake_now is False
    assert decision.is_unknown_event is False


async def test_unknown_event_type_is_force_escalated_even_if_llm_disagrees(
    monkeypatch: Any,
) -> None:
    # The mocked LLM deliberately gets it "wrong" — says routine, not unknown —
    # to prove escalation is enforced in code, not left to LLM reliability.
    _patch_llm(
        monkeypatch,
        ClassifyDecision(wake_now=False, reason="seems routine", is_unknown_event=False),
    )
    event = OrderEvent(event_type="carrier_lost_package")
    decision = await classifier_activity._classify(
        event, wake_policy="", aggressiveness=WakeAggressiveness.BALANCED
    )
    assert decision.wake_now is True
    assert decision.is_unknown_event is True


async def test_known_event_type_is_never_marked_unknown(monkeypatch: Any) -> None:
    _patch_llm(monkeypatch, ClassifyDecision(wake_now=False, reason="routine"))
    event = OrderEvent(event_type="shipment_created")
    decision = await classifier_activity._classify(
        event, wake_policy="", aggressiveness=WakeAggressiveness.BALANCED
    )
    assert decision.is_unknown_event is False
