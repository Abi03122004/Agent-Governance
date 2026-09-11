"""FastAPI Application Entrypoint with Typed Configuration and Lifecycle Hooks."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_security.api.router import api_router
from agent_security.config import Settings, get_settings
from agent_security.db.session import close_db
from agent_security.logging import configure_logging, get_logger
from agent_security.middleware.correlation import CorrelationIdMiddleware
from agent_security.middleware.error_handler import register_error_handlers
from agent_security.services.redis import close_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager handling startup initialization and graceful shutdown."""
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        f"Starting {settings.SERVICE_NAME} in '{settings.ENVIRONMENT}' environment "
        f"(debug={settings.DEBUG}, fail_secure={settings.ENABLE_FAIL_SECURE})."
    )

    try:
        yield
    finally:
        logger.info(f"Shutting down {settings.SERVICE_NAME}. Releasing database and redis resources...")
        await close_db()
        await close_redis()
        logger.info("Graceful shutdown complete.")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for the Agent Governance Platform."""
    active_settings = settings or get_settings()

    app = FastAPI(
        title="Autonomous AI Agent Security & Runtime Governance Platform",
        description="Deterministic runtime mediation for autonomous AI agent tool calls, APIs, and data access.",
        version="0.1.0",
        docs_url="/docs" if active_settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if active_settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # 1. CORS Middleware (Strictly validated)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Correlation ID Middleware (Request-ID and Trace-ID)
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Structured Error Handling
    register_error_handlers(app)

    # 4. Route Registration
    app.include_router(api_router)

    return app


# Default application instance for ASGI servers (uvicorn)
app = create_app()
