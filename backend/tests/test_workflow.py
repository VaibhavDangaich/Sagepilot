"""Workflow control-flow tests using Temporal's time-skipping test
environment. Real activities (LangGraph/OpenAI, Postgres) are replaced with
lightweight mocks registered under the same activity names, so these tests
exercise only the workflow's own deterministic control flow: signal
handling, sleep/wake timing, pause/resume, and continue_as_new — with no
live Temporal server, database, or OpenAI key required.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from temporalio import activity
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.activities.agent_activity import AgentActivityInput
from app.activities.business_actions import ExecuteActionInput
from app.activities.classifier_activity import HandleIncomingEventInput
from app.activities.lessons import StoreLessonInput
from app.activities.persistence import (
    PersistRunStateInput,
    RecordFinalOutputInput,
    RecordManualInstructionInput,
    RecordSystemEventInput,
    SetRunStatusInput,
)
from app.domain import (
    ActionCall,
    ActionName,
    AgentDecision,
    ClassifyDecision,
    FinalOutput,
    ModelConfig,
    OrderEvent,
    OrderEventType,
    RunSnapshot,
    SupervisorConfig,
)
from app.workflows.order_supervisor import OrderSupervisorWorkflow

TASK_QUEUE = "test-task-queue"
_DEFAULT_TURN_SLEEP_SECONDS = 3600


def make_snapshot(**overrides: Any) -> RunSnapshot:
    supervisor = SupervisorConfig(
        id="sup-1",
        name="Test Supervisor",
        base_instruction="Watch the order and act if needed.",
        model_config=ModelConfig(),
    )
    defaults: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "order_id": "order-1",
        "supervisor": supervisor,
        "started_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return RunSnapshot(**defaults)


class Calls:
    """Simple call counters, since mock activities run in-process and can
    share this via closure."""

    def __init__(self) -> None:
        self.run_agent = 0
        self.execute_action = 0
        self.final_summary = 0
        self.store_lesson = 0


def build_mock_activities(
    calls: Calls, *, sleep_seconds: int = _DEFAULT_TURN_SLEEP_SECONDS, always_wake: bool = True
) -> list[Callable[..., Any]]:
    @activity.defn(name="run_agent")
    async def mock_run_agent(input: AgentActivityInput) -> AgentDecision:
        calls.run_agent += 1
        return AgentDecision(
            memory_summary=f"turn {calls.run_agent}",
            sleep_seconds=sleep_seconds,
            reasoning_note="mocked turn",
        )

    @activity.defn(name="run_agent_final_summary")
    async def mock_run_agent_final_summary(input: AgentActivityInput) -> FinalOutput:
        calls.final_summary += 1
        return FinalOutput(final_summary="done", key_learnings="none", feedback="none")

    @activity.defn(name="execute_action")
    async def mock_execute_action(input: ExecuteActionInput) -> None:
        calls.execute_action += 1

    @activity.defn(name="handle_incoming_event")
    async def mock_handle_incoming_event(input: HandleIncomingEventInput) -> ClassifyDecision:
        return ClassifyDecision(wake_now=always_wake, reason="test override")

    @activity.defn(name="persist_run_state")
    async def mock_persist_run_state(input: PersistRunStateInput) -> None:
        pass

    @activity.defn(name="record_final_output")
    async def mock_record_final_output(input: RecordFinalOutputInput) -> None:
        pass

    @activity.defn(name="record_manual_instruction")
    async def mock_record_manual_instruction(input: RecordManualInstructionInput) -> None:
        pass

    @activity.defn(name="record_system_event")
    async def mock_record_system_event(input: RecordSystemEventInput) -> None:
        pass

    @activity.defn(name="set_run_status")
    async def mock_set_run_status(input: SetRunStatusInput) -> None:
        pass

    @activity.defn(name="store_lesson")
    async def mock_store_lesson(input: StoreLessonInput) -> None:
        calls.store_lesson += 1

    return [
        mock_run_agent,
        mock_run_agent_final_summary,
        mock_execute_action,
        mock_handle_incoming_event,
        mock_persist_run_state,
        mock_record_final_output,
        mock_record_manual_instruction,
        mock_record_system_event,
        mock_set_run_status,
        mock_store_lesson,
    ]


@pytest.fixture
async def env() -> AsyncIterator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as environment:
        yield environment


async def test_scheduled_wakeup_fires_without_any_signal(env: WorkflowEnvironment) -> None:
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=3600),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))
        assert calls.run_agent == 1  # the workflow-start trigger

        # No signal is sent — only the scheduled wake-up should cause turn 2.
        await env.sleep(timedelta(hours=1, minutes=5))
        assert calls.run_agent == 2

        await handle.terminate()


async def test_signal_wakes_early_before_scheduled_time(env: WorkflowEnvironment) -> None:
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=3600, always_wake=True),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))
        assert calls.run_agent == 1

        await handle.signal("order_event", OrderEvent(event_type=OrderEventType.PAYMENT_FAILED))
        await env.sleep(timedelta(seconds=1))
        assert calls.run_agent == 2  # woke well before the 1-hour scheduled time

        await handle.terminate()


async def test_pause_resume_suspends_turns(env: WorkflowEnvironment) -> None:
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=60),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))
        assert calls.run_agent == 1

        await handle.signal("interrupt")
        status = await handle.query(OrderSupervisorWorkflow.current_status)
        assert status["status"] == "paused"

        # Time passes well beyond the normal 60s sleep — no new turn while paused.
        await env.sleep(timedelta(minutes=10))
        assert calls.run_agent == 1

        await handle.signal("resume")
        await env.sleep(timedelta(seconds=1))
        status = await handle.query(OrderSupervisorWorkflow.current_status)
        assert status["status"] == "active"

        await handle.terminate()


async def test_terminal_order_event_completes_the_run(env: WorkflowEnvironment) -> None:
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=3600),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))

        await handle.signal("order_event", OrderEvent(event_type=OrderEventType.DELIVERED))
        # Completion is workflow-owned: reaching a terminal order event ends
        # the run, which should trigger exactly one final-summary call.
        await handle.result()
        assert calls.final_summary == 1


async def test_max_workflow_age_completes_the_run(env: WorkflowEnvironment) -> None:
    calls = Calls()
    supervisor = SupervisorConfig(
        id="sup-1",
        name="Test Supervisor",
        base_instruction="Watch the order.",
        model_config=ModelConfig(),
        max_workflow_age_hours=1,
    )
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=600),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            # started_at pinned near real "now" (the time-skipping server's
            # virtual clock starts there too) so this genuinely exercises
            # time-skipping past the 1-hour threshold, rather than already
            # being expired at t=0.
            make_snapshot(supervisor=supervisor, started_at=datetime.now(UTC)),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        # No terminal event, no manual terminate — only max_workflow_age_hours
        # should end the run once enough (virtual) time has passed.
        await handle.result()
        assert calls.final_summary == 1


async def test_manual_terminate_completes_the_run(env: WorkflowEnvironment) -> None:
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=3600),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))

        await handle.signal("terminate")
        await handle.result()
        assert calls.final_summary == 1
        assert calls.store_lesson == 0  # no notable_problem -> nothing to remember


async def test_notable_problem_triggers_store_lesson(env: WorkflowEnvironment) -> None:
    """Custom addition beyond the spec (see README): when the wrap-up agent
    flags a notable problem/resolution, the workflow must persist it to the
    cross-run lessons store via the store_lesson activity."""
    calls = Calls()

    @activity.defn(name="run_agent_final_summary")
    async def mock_final_summary_with_problem(input: AgentActivityInput) -> FinalOutput:
        calls.final_summary += 1
        return FinalOutput(
            final_summary="done",
            key_learnings="payments API was flaky",
            feedback="none",
            notable_problem="Payment provider timed out repeatedly for this order.",
            notable_resolution="Retried with exponential backoff and it went through.",
        )

    activities = build_mock_activities(calls, sleep_seconds=3600)
    activities[1] = mock_final_summary_with_problem  # swap in the notable-problem variant

    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=activities,
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))

        await handle.signal("terminate")
        await handle.result()
        assert calls.store_lesson == 1


async def test_actions_are_dispatched_and_recorded(env: WorkflowEnvironment) -> None:
    calls = Calls()

    @activity.defn(name="run_agent")
    async def mock_run_agent_with_action(input: AgentActivityInput) -> AgentDecision:
        calls.run_agent += 1
        return AgentDecision(
            actions=[ActionCall(name=ActionName.CREATE_INTERNAL_NOTE, message="hello")],
            memory_summary="acted",
            sleep_seconds=3600,
            reasoning_note="took an action",
        )

    activities = build_mock_activities(calls)
    activities[0] = mock_run_agent_with_action  # swap in the action-emitting variant

    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=activities,
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=1))
        assert calls.execute_action == 1
        await handle.terminate()


async def test_continue_as_new_triggers_past_seq_threshold(env: WorkflowEnvironment) -> None:
    """Each mocked turn advances seq_counter by exactly 1 (via persist_run_state,
    no actions), so after crossing `_CONTINUE_AS_NEW_SEQ_THRESHOLD` (300) turns
    the workflow must have continued-as-new at least once — carrying the epoch
    forward while the workflow ID (and this handle) stay the same."""
    calls = Calls()
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=build_mock_activities(calls, sleep_seconds=1),
    ):
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            make_snapshot(),
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        await env.sleep(timedelta(seconds=310))
        status = await handle.query(OrderSupervisorWorkflow.current_status)
        epoch = status["epoch"]
        assert isinstance(epoch, str)
        assert int(epoch) >= 1
        assert calls.run_agent > 300

        await handle.terminate()
