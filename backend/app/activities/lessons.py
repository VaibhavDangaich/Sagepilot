"""Write side of the long-term lessons store (custom addition, see README).

Called once per run, at finalization, only when the wrap-up agent flagged a
`notable_problem` worth remembering for future, unrelated orders.
"""

from __future__ import annotations

from pydantic import BaseModel
from temporalio import activity

from app.agent.embeddings import embed_text
from app.db.repository import insert_lesson
from app.db.session import session_scope


class StoreLessonInput(BaseModel):
    run_id: str
    supervisor_id: str
    order_id: str
    event_type: str | None
    problem: str
    resolution: str


@activity.defn
async def store_lesson(input: StoreLessonInput) -> None:
    embedding = await embed_text(input.problem)
    async with session_scope() as session:
        await insert_lesson(
            session,
            supervisor_id=input.supervisor_id,
            source_run_id=input.run_id,
            order_id=input.order_id,
            event_type=input.event_type,
            problem=input.problem,
            resolution=input.resolution,
            embedding=embedding,
        )
