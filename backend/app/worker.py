"""Temporal worker entrypoint: `uv run python -m app.worker`.

Runs as its own long-lived process, separate from the FastAPI process —
this is the piece that actually executes workflow and activity code, and
it cannot be a serverless/on-demand function (it holds a persistent
connection to Temporal and continuously polls its task queue).
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.activities import ALL_ACTIVITIES
from app.config import get_settings
from app.temporal_client import connect_temporal_client
from app.workflows.order_supervisor import OrderSupervisorWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    client = await connect_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[OrderSupervisorWorkflow],
        activities=ALL_ACTIVITIES,
    )
    logger.info("Order Supervisor worker starting on task queue '%s'", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
