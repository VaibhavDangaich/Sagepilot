# Architecture Note

## Overview

One Temporal workflow (`OrderSupervisorWorkflow`) runs per order, for the order's
entire lifecycle. It never polls in a loop: it reacts to exactly three triggers —
workflow start, an incoming signal, or its own scheduled wake-up timer — runs one
agent turn, then goes back to sleep until the next trigger.

```
FastAPI  ──start/signal──▶  Temporal Workflow  ──execute_activity──▶  Agent Activity (LangGraph)
   │                              │  (deterministic control flow only)         │
   ▼                              │                                            ▼
Postgres ◀─────────────────────── activities write all state ──────── OpenAI (reasoning)
```

## Workflow control flow

The workflow's main loop is a single `while` loop around one primitive:

```python
await workflow.wait_condition(lambda: wake_flag or stop_requested or terminal_event_pending,
                               timeout=sleep_for)
```

- If a signal sets `wake_flag` before the timeout, that's an **event-driven wake**.
- If it times out (`TimeoutError`), that's a **scheduled wake-up**.

This single idiom implements both wake paths without a separate timer future. All
signal handlers (`order_event`, `add_instruction`, `interrupt`, `resume`, `terminate`)
are guarded with try/except so one failing handler can't fail the whole workflow task.

**Determinism**: the workflow only ever calls `workflow.now()` (never wall-clock time),
assigns activity-log sequence numbers itself (an in-memory counter, not a DB
auto-increment — `asyncio.gather` gives no ordering guarantee across concurrently
dispatched action activities), and delegates every side effect (DB writes, the LLM
call) to an activity. The workflow file's own imports of activity modules are wrapped
in `workflow.unsafe.imports_passed_through()`, since those modules pull in
non-deterministic dependencies (SQLAlchemy, LangChain) that don't need per-workflow
sandbox isolation.

## Completion is workflow-owned, not agent-owned

The spec is explicit that a run should not end just because the AI decides to end it.
`_completion_rule_met()` only returns true for three conditions: a terminal order event
arrived (`delivered`), the run was manually terminated via the UI, or a configured
`max_workflow_age_hours` was exceeded. The agent's own `recommend_complete` flag is
logged for visibility but never independently triggers completion.

## Agent runtime (LangGraph)

Each turn invokes a small LangGraph graph (`load_context → reason`) inside one
Temporal Activity, producing a structured `AgentDecision` (Pydantic, enforced via
`with_structured_output`): actions to take, an updated memory summary, how long to
sleep, an optional refined wake policy, and a reasoning note. Two design choices here:

- **No LangGraph checkpointer.** The activity is stateless — every call rehydrates the
  recent timeline and memory summary from Postgres. Temporal + Postgres stay the single
  source of truth; a second persistence layer inside LangGraph would create two
  competing versions of "what happened."
- **The activity only decides, the workflow executes.** LangGraph never calls the real
  business-action side effects directly — it returns a plan, and the *workflow* fans
  each action out to its own activity (`asyncio.gather(..., return_exceptions=True)`, so
  one failing action doesn't block the others). This means a retried `run_agent`
  activity (after a timeout or worker crash) can never double-execute a real action.

## Wake-up classifier + agent-generated wake policy

`handle_incoming_event` decides, per incoming event, whether to wake the main agent now
or leave it asleep until the next scheduled check. It's a hybrid, not one strategy for
everything:

1. **Deterministic fast path.** A small fixed set of unambiguous, safety-critical event
   types (`payment_failed`, `shipment_delayed`, `refund_requested`,
   `customer_message_received`, `delivered`) always wake immediately — no LLM call, no
   latency. An "aggressive" supervisor config takes the same fast path for any event.
2. **LLM classification for everything else.** Routine known event types, *and* any
   free-text/custom event type typed directly in the UI (the event catalog is not a
   closed enum on the wire — `OrderEvent.event_type` is a plain string), go through a
   small `ChatOpenAI` call with `with_structured_output(ClassifyDecision)`. Its system
   prompt bakes in a handful of **few-shot examples** showing how routine, important,
   and unknown events should be classified, plus the run's current agent-authored
   `wake_policy` as additional context — so if the agent decided "wake immediately on
   shipment_delayed for this order" last turn, that guidance persists into how future
   events for this specific run get classified.
3. **Unknown-event escalation.** If the event's type isn't in the system's known
   catalog (`KNOWN_EVENT_TYPES`), the code force-overrides the LLM's output to
   `wake_now=true, is_unknown_event=true` regardless of what it returned — escalation
   of unrecognized input is a code-level guarantee, not something left to LLM
   reliability. The LLM's `reason` is kept, though, so the main agent gets a useful
   interpretation to act on rather than a bare flag. In testing, a made-up
   `carrier_lost_package` event correctly triggered `message_logistics_team` and
   `create_internal_note` actions from the main agent on the very next turn.

## Memory and timeline

A single append-only `run_activity_log` table stores everything: incoming events, wake
and sleep decisions, agent actions, manual instructions, and the final output — matching
the spec's own suggested simplification over a separate messages table. The `runs`
table holds the current snapshot (status, compact memory summary, wake policy, next
wake time). Compaction is intentionally simple: the agent's memory summary is a
rolling, agent-maintained digest, not the full history — the activity only ever reads
the last ~30 timeline rows plus this summary, not the entire log.

## continue_as_new

The workflow tracks its own `seq_counter` (the same counter used for activity-log
sequencing) and calls `continue_as_new` once it crosses a threshold, carrying forward
order context, accumulated instructions, the memory summary, wake policy, and an
incremented epoch counter — deliberately *not* the full timeline, since that already
lives in Postgres. This is why continue_as_new is cheap here: the compact-memory design
and the continue_as_new design solve the same problem (don't let workflow history grow
unbounded) from two complementary angles.

## Why not deploy this to Vercel

We considered folding the FastAPI layer into a single Next.js-rooted repo for a Vercel
deployment. A Temporal **worker**, however, is a long-lived process that continuously
polls a task queue — it cannot run as an on-demand serverless function, regardless of
language or repo layout. The assignment doesn't require a hosted deployment (only
source + README + this note + a walkthrough video), so the backend and frontend are
kept as ordinary separate local services instead.

## Testing

`backend/tests/test_workflow.py` exercises the actual workflow class against
`temporalio.testing.WorkflowEnvironment`'s time-skipping test server, with real
activities swapped for lightweight mocks registered under the same activity names. This
validates the trickiest logic — scheduled vs. signal-driven wake, pause/resume,
terminal-event and manual-terminate completion, max-age completion, action fan-out, and
`continue_as_new` — without a live Temporal server, database, or OpenAI key.
`backend/tests/test_classifier.py` covers the rule-based classifier in isolation.
