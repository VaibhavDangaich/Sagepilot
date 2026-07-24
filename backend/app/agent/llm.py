"""Provider-agnostic LLM factory.

Every LLM call site in the app (the reasoning agent, the wake-up classifier,
the lessons embeddings) goes through here rather than instantiating a concrete
LangChain client, so switching between OpenAI and Google Gemini is a matter of
a `provider` string on the config — no branching scattered across the code.

Keys are passed explicitly rather than via process env vars: pydantic-settings
loads `.env` into our own Settings object only, it never exports values into
os.environ, so the LangChain clients wouldn't otherwise see them.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings
from app.domain import ModelConfig

_GOOGLE_PROVIDERS = frozenset({"google", "gemini"})


def default_model_for(provider: str) -> str:
    """The lightweight default chat model for a provider (used by call sites
    that don't carry an explicit model, e.g. the classifier)."""
    settings = get_settings()
    if provider in _GOOGLE_PROVIDERS:
        return settings.default_gemini_model
    return settings.default_openai_model


def default_model_config() -> ModelConfig:
    """A ModelConfig seeded from the configured DEFAULT_PROVIDER, so a supervisor
    created without an explicit llm_config follows the deployment's chosen
    provider (e.g. Gemini) instead of always defaulting to OpenAI."""
    provider = get_settings().default_provider
    return ModelConfig(provider=provider, model=default_model_for(provider))


def build_chat_model(*, provider: str, model: str, temperature: float) -> BaseChatModel:
    """Return a LangChain chat model for the given provider.

    Callers still apply `.with_structured_output(...)` themselves — both
    supported clients implement it, so structured output works either way.
    """
    settings = get_settings()
    if provider in _GOOGLE_PROVIDERS:
        # Imported lazily so the OpenAI-only path never requires the Google SDK.
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=settings.gemini_api_key,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )
