import asyncio
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

from vigil.config import settings
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
    # topology-syslog クライアント（AI の有無によらず初期化）
    if settings.topology_syslog_url:
        from vigil.services.ai.topology_client import TopologySyslogClient
        app.state.topology_client = TopologySyslogClient(settings.topology_syslog_url)
        logger.info("topology-syslog クライアント起動 (%s)", settings.topology_syslog_url)
    else:
        app.state.topology_client = None

    app.state.ai_agent = None
    if settings.ai_enabled:
        try:
            from vigil.services.ai.agent import InvestigationAgent
            from vigil.services.ai.llm_client import create_llm_client
            from vigil.services.ai.query_cache import QueryCache
            from vigil.services.ai.rag_store import RAGStore

            llm = create_llm_client(
                provider=settings.llm_provider,
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
                ollama_base_url=settings.ollama_base_url,
                ollama_model=settings.ollama_model,
            )
            cache = QueryCache(settings.database_url, ttl_days=settings.ai_cache_ttl_days)
            rag = RAGStore(settings.ai_rag_path)
            app.state.ai_agent = InvestigationAgent(llm, cache, rag, app.state.topology_client)
            logger.info(
                "AI 調査エージェント起動 (topology-syslog: %s)",
                settings.topology_syslog_url or "未設定",
            )
        except Exception:
            logger.exception("AI エージェントの初期化に失敗")

    async def _daily_cleanup() -> None:
        agent = getattr(app.state, "ai_agent", None)
        if agent is not None:
            try:
                purged = await asyncio.to_thread(agent.purge_cache)
                if purged:
                    logger.info("AI cache cleanup: purged %d expired entries", purged)
            except Exception:
                logger.exception("Daily cleanup error")

    scheduler.add_job(_daily_cleanup, "interval", hours=24, id="daily_cleanup", replace_existing=True)
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
