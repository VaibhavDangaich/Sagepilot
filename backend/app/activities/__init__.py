from collections.abc import Callable
from typing import Any

from app.activities.agent_activity import run_agent, run_agent_final_summary
from app.activities.business_actions import execute_action
from app.activities.classifier_activity import handle_incoming_event
from app.activities.persistence import (
    persist_run_state,
    record_final_output,
    record_manual_instruction,
    record_system_event,
    set_run_status,
)

ALL_ACTIVITIES: list[Callable[..., Any]] = [
    run_agent,
    run_agent_final_summary,
    execute_action,
    handle_incoming_event,
    persist_run_state,
    record_final_output,
    record_manual_instruction,
    record_system_event,
    set_run_status,
]
