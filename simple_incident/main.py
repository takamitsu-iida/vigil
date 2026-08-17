from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from simple_incident.database import create_db_and_tables
from simple_incident.routers import api


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    yield
    # shutdown: スケジューラ停止はPhase 4で追加する


app = FastAPI(
    title="Simple Incident",
    description="Lightweight self-hosted incident management and on-call tool",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="simple_incident/static"), name="static")
app.include_router(api.router)
# Phase 5で追加: app.include_router(web.router)
