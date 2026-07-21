"""Read side of the long-term lessons store — a custom addition beyond the
assignment spec (see README's "Custom addition" section)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.db import repository
from app.db.session import get_session
from app.domain import LessonRecord

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("", response_model=list[LessonRecord])
async def list_lessons(session: AsyncSession = Depends(get_session)) -> list[LessonRecord]:
    rows = await repository.list_recent_lessons(session)
    return [schemas.lesson_to_record(row) for row in rows]
