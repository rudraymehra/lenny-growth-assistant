"""Application factory and lifespan wiring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.routes_artifacts import router as artifacts_router
from app.api.routes_config import router as config_router
from app.api.routes_health import router as health_router
from app.api.routes_messages import router as messages_router
from app.api.routes_sessions import router as sessions_router
from app.config import get_settings
from app.db.pool import apply_schema, create_pool
from app.db.repos import ArtifactRepo, KnowledgeRepo, MessageRepo, SessionRepo
from app.engines.router import EngineRouter
from app.logging import configure_logging, get_logger
from app.rag import embedder

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    pool = await create_pool(settings.database_url)
    await apply_schema(pool)

    import asyncio
    # ONNX warmup off the loop so the first user query isn't slow.
    await asyncio.to_thread(embedder.warmup, settings.embedding_model)

    app.state.settings = settings
    app.state.pool = pool
    app.state.session_repo = SessionRepo(pool)
    app.state.message_repo = MessageRepo(pool)
    app.state.artifact_repo = ArtifactRepo(pool)
    app.state.knowledge_repo = KnowledgeRepo(pool)
    app.state.engine_router = EngineRouter(settings, pool)

    log.info("app.started", provider_default=settings.default_provider,
             anthropic_configured=settings.anthropic_configured)
    yield
    await pool.close()


def create_app(lifespan_ctx=lifespan) -> FastAPI:
    """lifespan_ctx is injectable so tests can wire app.state themselves
    (test DB + FakeEngine) without touching production startup."""
    app = FastAPI(
        title="The Lenny Growth Assistant",
        version="1.0.0",
        lifespan=lifespan_ctx,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins.split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    for router in (health_router, config_router, sessions_router, messages_router, artifacts_router):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
