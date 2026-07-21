# Walkthrough Script

A step-by-step script for the recorded walkthrough, covering every point the
assignment's checklist requires. Everything below has already been validated live
(via the API directly) during development — this is just the UI-driven version of the
same flow.

**Before recording**: have all four processes running (`temporal server start-dev`,
the worker, FastAPI, and `pnpm dev`), plus the Temporal Web UI
(`http://localhost:8233`) open in a second tab — showing the workflow history there
after each action makes the Temporal usage much more visible on screen.

1. **Create a supervisor config** — go to `/supervisors`, use a preset or fill in a
   name + base instruction (e.g. "Watch this order and act if needed"), pick actions,
   set wake aggressiveness, submit. Point out the created config in the list.

2. **Start an order run** — go to `/runs`, pick the supervisor, enter an order ID,
   start the run. Open the run detail page. Switch to the Temporal Web UI and show the
   new workflow execution (`order-<order_id>-...`) and its first `run_agent` activity
   in history — this is the workflow-start trigger.

3. **Send events into the workflow** — from the run detail page, inject a
   `shipment_created` event (routine, shouldn't wake the agent immediately) and then a
   `payment_failed` event (always important). Show the timeline updating: the incoming
   event log entry, the wake/sleep decision, and — for the important one — the agent
   waking and acting.

4. **Tool execution** — after the `payment_failed` event, show the `agent_action`
   entries in the timeline (e.g. `message_payments_team`, `message_customer`) and the
   corresponding Activity executions in the Temporal Web UI.

4a. **Bonus: unknown-event escalation** — in the "Inject event" dropdown, pick
    **custom…** and type something the system has never seen, e.g.
    `carrier_lost_package`. Show it get accepted (no fixed enum on the wire), the
    timeline logging it as `is_unknown_event: true` with `wake_now: true` regardless,
    and the agent taking a sensible real action in response (e.g.
    `message_logistics_team`) — worth narrating that this escalation is a code-level
    guarantee (forced regardless of what the LLM classifier itself returns), not
    something left entirely to the LLM's judgment.

5. **The agent going to sleep and waking up** — point out the "Next wake-up" time in
   the status header after a turn, and the `sleep_decision` timeline entries showing
   the agent's chosen sleep duration and reasoning note. If time allows, wait for a
   scheduled wake-up to fire naturally (or use a short sleep duration in the
   supervisor's instructions to make this fast for the recording).

6. **Adding extra instructions to a live run** — use the "Add instruction" control to
   inject something like *"If shipment is delayed, escalate immediately."* Show it
   appear as a `manual_instruction` timeline entry and confirm the agent wakes
   immediately in response.

7. **Interrupting or terminating a run** — click **Pause**, show the status badge
   change to `paused` and that no new turns happen even if you send an event or wait
   past the scheduled wake time. Click **Resume**, show it goes back to `active`. Then
   click **Terminate**.

8. **Final summary, learnings, and feedback** — after termination, show the "Final
   output" panel on the run detail page with the generated summary, key learnings, and
   feedback, and the run's status badge now reading `terminated`.

Optional, if time allows: show `continue_as_new` conceptually by explaining the
`seq_counter` threshold in `ARCHITECTURE.md` (triggering it live would require ~300
turns, impractical to record in real time — it's covered by an automated test instead,
`test_continue_as_new_triggers_past_seq_threshold` in `backend/tests/test_workflow.py`).
