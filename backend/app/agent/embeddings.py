"""Text embeddings for the long-term lessons store (see README's "Custom
addition" section — this is not part of the assignment spec).

Uses OpenAI's text-embedding-3-small (1536 dimensions): cheap and fast
enough to call on both the write path (embedding a new lesson's problem
description) and the read path (embedding the current situation to search
against) without adding noticeable latency to a turn.
"""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from app.config import get_settings

_EMBEDDING_MODEL = "text-embedding-3-small"


async def embed_text(text: str) -> list[float]:
    embeddings = OpenAIEmbeddings(
        model=_EMBEDDING_MODEL, openai_api_key=get_settings().openai_api_key
    )
    return await embeddings.aembed_query(text)
