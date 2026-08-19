from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vigil.routers import api, web
from vigil.services.escalation import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Simple Incident",
    description="Lightweight self-hosted incident management and on-call tool",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="vigil/static"), name="static")
app.include_router(api.router)
app.include_router(web.router)
