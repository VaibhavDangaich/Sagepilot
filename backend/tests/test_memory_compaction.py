"""Tests for the two memory-compaction layers:
importance-weighted timeline retention, and second-pass summary
compaction. No live DB or OpenAI key required."""

from __future__ import annotations

from typing import Any

from app.activities.agent_activity import _HIGH_SIGNAL_KINDS, _is_high_signal
from app.agent import compaction
from app.db.models import RunActivityLog


def _row(kind: str, payload: dict[str, Any] | None = None) -> RunActivityLog:
    return RunActivityLog(run_id=None, seq=1, kind=kind, payload=payload or {})


def test_agent_action_is_high_signal() -> None:
    assert _is_high_signal(_row("agent_action")) is True


def test_manual_instruction_is_high_signal() -> None:
    assert _is_high_signal(_row("manual_instruction")) is True


def test_final_output_is_high_signal() -> None:
    assert _is_high_signal(_row("final_output")) is True


def test_routine_incoming_event_is_not_high_signal() -> None:
    assert _is_high_signal(_row("incoming_event", {"event_type": "shipment_created"})) is False


def test_routine_sleep_decision_is_not_high_signal() -> None:
    assert _is_high_signal(_row("sleep_decision", {"reasoning_note": "nothing to do"})) is False


def test_unknown_event_wake_decision_is_high_signal_despite_kind() -> None:
    # A wake_decision row is normally low-signal, but one flagging an
    # unrecognized event type must not be allowed to silently age out.
    row = _row("wake_decision", {"reason": "unrecognized", "is_unknown_event": True})
    assert _is_high_signal(row) is True


def test_high_signal_kinds_cover_the_expected_set() -> None:
    assert {"agent_action", "manual_instruction", "final_output"} == _HIGH_SIGNAL_KINDS


async def test_short_summary_passes_through_without_any_llm_call() -> None:
    short_summary = "Order created, nothing else has happened yet."
    result = await compaction.compact_memory_if_needed(short_summary)
    assert result == short_summary


class _FakeLLMResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatOpenAI:
    def __init__(self, compacted: str) -> None:
        self._compacted = compacted

    async def ainvoke(self, messages: list[Any]) -> _FakeLLMResult:
        return _FakeLLMResult(self._compacted)


async def test_long_summary_gets_compacted_via_llm(monkeypatch: Any) -> None:
    long_summary = "x" * 700
    monkeypatch.setattr(
        compaction, "ChatOpenAI", lambda **kwargs: _FakeChatOpenAI("a much shorter summary")
    )
    result = await compaction.compact_memory_if_needed(long_summary)
    assert result == "a much shorter summary"


async def test_long_summary_falls_back_to_original_on_empty_llm_response(
    monkeypatch: Any,
) -> None:
    long_summary = "y" * 700
    monkeypatch.setattr(compaction, "ChatOpenAI", lambda **kwargs: _FakeChatOpenAI("   "))
    result = await compaction.compact_memory_if_needed(long_summary)
    assert result == long_summary
