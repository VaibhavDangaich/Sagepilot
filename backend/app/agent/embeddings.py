"""Text embeddings for the long-term lessons store (see README's "Custom
addition" section — this is not part of the assignment spec).

Provider follows DEFAULT_PROVIDER: OpenAI's text-embedding-3-small (1536-dim)
or Google's gemini-embedding-001 (3072-dim). Both are cheap and fast enough to
call on both the write path (embedding a new lesson's problem description) and
the read path (embedding the current situation to search against) without
adding noticeable latency to a turn.

Note: the two models produce different-dimension vectors and the cosine search
zips them strict, so a single lessons table must stick with one provider — don't
switch DEFAULT_PROVIDER against a table that already holds another provider's
embeddings (a fresh database is fine).
"""

from __future__ import annotations

from app.config import get_settings

_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
_GOOGLE_EMBEDDING_MODEL = "models/gemini-embedding-001"
_GOOGLE_PROVIDERS = frozenset({"google", "gemini"})


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.default_provider in _GOOGLE_PROVIDERS:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        google_embeddings = GoogleGenerativeAIEmbeddings(
            model=_GOOGLE_EMBEDDING_MODEL, google_api_key=settings.gemini_api_key
        )
        return await google_embeddings.aembed_query(text)

    from langchain_openai import OpenAIEmbeddings

    openai_embeddings = OpenAIEmbeddings(
        model=_OPENAI_EMBEDDING_MODEL, openai_api_key=settings.openai_api_key
    )
    return await openai_embeddings.aembed_query(text)
