from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import lessons, runs, supervisors
from app.temporal_client import connect_temporal_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.temporal_client = await connect_temporal_client()
    yield


app = FastAPI(title="Order Supervisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(supervisors.router)
app.include_router(runs.router)
app.include_router(lessons.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
