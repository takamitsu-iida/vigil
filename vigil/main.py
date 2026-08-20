import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vigil.database import engine
from vigil.routers import api, web
from vigil.services.escalation import scheduler

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="vigil/templates")


def _check_migrations() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()
        head = script.get_current_head()
    if current != head:
        logger.warning(
            "未適用のマイグレーションがあります。"
            " `alembic upgrade head` を実行してください。"
            " (現在: %s, 最新: %s)",
            current,
            head,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _check_migrations()
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


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> HTMLResponse:
    logger.exception("Unhandled error: %s", exc)
    return templates.TemplateResponse(
        request, "500.html", {"detail": str(exc)}, status_code=500
    )
