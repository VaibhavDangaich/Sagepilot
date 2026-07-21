"""One long-running Temporal workflow per order.

The workflow itself only ever does deterministic control flow: it reacts to
3 triggers (start, incoming signal, scheduled wake-up), delegates all
reasoning to the `run_agent` activity, delegates all side effects to their
own activities, and enforces completion strictly through workflow-owned
lifecycle rules — never because "the AI decided to end it".
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities.agent_activity import (
        AgentActivityInput,
        run_agent,
        run_agent_final_summary,
    )
    from app.activities.business_actions import ExecuteActionInput, execute_action
    from app.activities.classifier_activity import HandleIncomingEventInput, handle_incoming_event
    from app.activities.persistence import (
        PersistRunStateInput,
        RecordFinalOutputInput,
        RecordManualInstructionInput,
        RecordSystemEventInput,
        SetRunStatusInput,
        persist_run_state,
        record_final_output,
        record_manual_instruction,
        record_system_event,
        set_run_status,
    )
    from app.domain import TERMINAL_ORDER_EVENTS, AgentDecision, OrderEvent, RunSnapshot

_AGENT_ACTIVITY_TIMEOUT = timedelta(seconds=120)
_AGENT_ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(seconds=30)
_ACTION_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_BOOKKEEPING_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_MIN_SLEEP_SECONDS = 1

# Kept as a plain module constant rather than read from app.config: workflow
# code must avoid non-deterministic/environment-dependent calls, and this
# never needs to vary at runtime for the POC.
_CONTINUE_AS_NEW_SEQ_THRESHOLD = 300


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self) -> None:
        self._snapshot: RunSnapshot | None = None
        self._wake_flag = False
        self._paused = False
        self._stop_requested = False
        self._terminal_event_pending = False

    # -- helpers ----------------------------------------------------------

    @property
    def _s(self) -> RunSnapshot:
        assert self._snapshot is not None
        return self._snapshot

    def _next_seq(self) -> int:
        self._s.seq_counter += 1
        return self._s.seq_counter

    def _completion_rule_met(self) -> bool:
        if self._stop_requested or self._terminal_event_pending:
            return True
        max_age = self._s.supervisor.max_workflow_age_hours
        if max_age is not None:
            age = workflow.now() - self._s.started_at
            if age >= timedelta(hours=max_age):
                return True
        return False

    async def _log_system_event(self, message: str) -> None:
        try:
            await workflow.execute_activity(
                record_system_event,
                RecordSystemEventInput(
                    run_id=self._s.run_id, seq=self._next_seq(), message=message
                ),
                start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
            )
        except Exception:
            workflow.logger.exception("failed to log system event: %s", message)

    async def _set_status(self, status: str, message: str) -> None:
        try:
            await workflow.execute_activity(
                set_run_status,
                SetRunStatusInput(
                    run_id=self._s.run_id, seq=self._next_seq(), status=status, message=message
                ),
                start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
            )
        except Exception:
            workflow.logger.exception("failed to set run status to %s", status)

    # -- signal handlers ----------------------------------------------------

    @workflow.signal
    async def order_event(self, event: OrderEvent) -> None:
        try:
            event_seq = self._next_seq()
            decision_seq = self._next_seq()
            if event.event_type in TERMINAL_ORDER_EVENTS:
                self._terminal_event_pending = True
            classify_decision = await workflow.execute_activity(
                handle_incoming_event,
                HandleIncomingEventInput(
                    run_id=self._s.run_id,
                    event=event,
                    event_seq=event_seq,
                    decision_seq=decision_seq,
                    wake_policy=self._s.wake_policy,
                    wake_aggressiveness=self._s.supervisor.wake_aggressiveness,
                ),
                start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
            )
            if classify_decision.wake_now or self._terminal_event_pending:
                self._wake_flag = True
        except Exception:
            workflow.logger.exception("order_event handler failed for %s", event)

    @workflow.signal
    async def add_instruction(self, instruction: str) -> None:
        try:
            self._s.additional_instructions.append(instruction)
            await workflow.execute_activity(
                record_manual_instruction,
                RecordManualInstructionInput(
                    run_id=self._s.run_id, seq=self._next_seq(), instruction=instruction
                ),
                start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
            )
            # A human explicitly injected guidance — always worth an immediate look.
            self._wake_flag = True
        except Exception:
            workflow.logger.exception("add_instruction handler failed")

    @workflow.signal
    async def interrupt(self) -> None:
        self._paused = True
        await self._set_status("paused", "run paused via UI interrupt")

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        await self._set_status("active", "run resumed via UI")

    @workflow.signal
    async def terminate(self) -> None:
        self._stop_requested = True
        await self._log_system_event("run manually terminated via UI")

    @workflow.query
    def current_status(self) -> dict[str, str | bool | None]:
        return {
            "status": "paused" if self._paused else "active",
            "memory_summary": self._s.memory_summary,
            "wake_policy": self._s.wake_policy,
            "next_wake_at": self._s.next_wake_at.isoformat() if self._s.next_wake_at else None,
            "epoch": str(self._s.epoch),
        }

    # -- main control flow --------------------------------------------------

    @workflow.run
    async def run(self, snapshot: RunSnapshot) -> None:
        self._snapshot = snapshot
        trigger_reason = (
            "workflow_start" if snapshot.epoch == 0 else "resumed_after_continue_as_new"
        )

        while True:
            if self._paused:
                await workflow.wait_condition(lambda: not self._paused or self._stop_requested)
                if self._stop_requested:
                    break
                continue

            decision = await self._run_agent_turn(trigger_reason)

            if self._completion_rule_met():
                break

            sleep_for = timedelta(seconds=max(decision.sleep_seconds, _MIN_SLEEP_SECONDS))
            self._wake_flag = False
            try:
                await workflow.wait_condition(
                    lambda: self._wake_flag or self._stop_requested or self._terminal_event_pending,
                    timeout=sleep_for,
                )
                trigger_reason = "signal"
            except TimeoutError:
                trigger_reason = "scheduled_wakeup"

            if self._completion_rule_met():
                break

            await workflow.wait_condition(workflow.all_handlers_finished)
            if self._s.seq_counter >= _CONTINUE_AS_NEW_SEQ_THRESHOLD:
                workflow.continue_as_new(self._s.model_copy(update={"epoch": self._s.epoch + 1}))
                return

        await self._finalize()
        await workflow.wait_condition(workflow.all_handlers_finished)

    async def _run_agent_turn(self, trigger_reason: str) -> AgentDecision:
        decision = await workflow.execute_activity(
            run_agent,
            AgentActivityInput(snapshot=self._s, trigger_reason=trigger_reason),
            start_to_close_timeout=_AGENT_ACTIVITY_TIMEOUT,
            heartbeat_timeout=_AGENT_ACTIVITY_HEARTBEAT_TIMEOUT,
        )

        action_seqs = [self._next_seq() for _ in decision.actions]
        action_calls = [
            workflow.execute_activity(
                execute_action,
                ExecuteActionInput(run_id=self._s.run_id, seq=seq, action=action),
                start_to_close_timeout=_ACTION_ACTIVITY_TIMEOUT,
            )
            for seq, action in zip(action_seqs, decision.actions, strict=True)
        ]
        if action_calls:
            # One action failing (after its own activity retries are exhausted)
            # must not prevent the others from being recorded.
            await asyncio.gather(*action_calls, return_exceptions=True)

        self._s.memory_summary = decision.memory_summary
        if decision.wake_policy:
            self._s.wake_policy = decision.wake_policy
        self._s.next_wake_at = workflow.now() + timedelta(
            seconds=max(decision.sleep_seconds, _MIN_SLEEP_SECONDS)
        )

        await workflow.execute_activity(
            persist_run_state,
            PersistRunStateInput(
                run_id=self._s.run_id,
                seq=self._next_seq(),
                seq_counter=self._s.seq_counter,
                memory_summary=self._s.memory_summary,
                wake_policy=self._s.wake_policy,
                next_wake_at=self._s.next_wake_at,
                reasoning_note=decision.reasoning_note,
                sleep_seconds=decision.sleep_seconds,
                status="sleeping",
            ),
            start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
        )
        return decision

    async def _finalize(self) -> None:
        reason = (
            "manual_terminate"
            if self._stop_requested
            else "terminal_order_event"
            if self._terminal_event_pending
            else "max_workflow_age_reached"
        )
        final = await workflow.execute_activity(
            run_agent_final_summary,
            AgentActivityInput(snapshot=self._s, trigger_reason=reason),
            start_to_close_timeout=_AGENT_ACTIVITY_TIMEOUT,
            heartbeat_timeout=_AGENT_ACTIVITY_HEARTBEAT_TIMEOUT,
        )
        await workflow.execute_activity(
            record_final_output,
            RecordFinalOutputInput(
                run_id=self._s.run_id,
                seq=self._next_seq(),
                seq_counter=self._s.seq_counter,
                final_summary=final.final_summary,
                final_learnings=final.key_learnings,
                final_feedback=final.feedback,
                status="terminated" if self._stop_requested else "completed",
            ),
            start_to_close_timeout=_BOOKKEEPING_ACTIVITY_TIMEOUT,
        )
