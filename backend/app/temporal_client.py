"""Shared Temporal client factory.

Both the FastAPI process and the worker process connect with the Pydantic
data converter so `RunSnapshot`/`OrderEvent`/etc. pass through as native
Pydantic models on both sides of every signal/start call.
"""

from __future__ import annotations

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from app.config import get_settings


async def connect_temporal_client() -> Client:
    settings = get_settings()
    return await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
