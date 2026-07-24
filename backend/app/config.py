"""Centralized runtime configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/order_supervisor"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "order-supervisor-task-queue"

    # Which provider the classifier / embeddings default to when a
    # SupervisorConfig doesn't pin one explicitly. Either "openai" or "google".
    default_provider: str = "openai"

    openai_api_key: str = ""
    default_openai_model: str = "gpt-4o-mini"

    # Google Gemini support. Set GEMINI_API_KEY (and provider="google", or
    # DEFAULT_PROVIDER=google) to run the agent on Gemini instead of OpenAI.
    gemini_api_key: str = ""
    default_gemini_model: str = "gemini-2.0-flash"

    # Threshold for continue_as_new: number of activity-log rows appended
    # since workflow start (or last continue_as_new) before compacting.
    continue_as_new_seq_threshold: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
