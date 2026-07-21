"""Centralized runtime configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/order_supervisor"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "order-supervisor-task-queue"

    openai_api_key: str = ""
    default_openai_model: str = "gpt-4o-mini"

    # Threshold for continue_as_new: number of activity-log rows appended
    # since workflow start (or last continue_as_new) before compacting.
    continue_as_new_seq_threshold: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
