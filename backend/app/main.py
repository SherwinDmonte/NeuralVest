"""NeuralVest FastAPI application.

Run from the `backend/` folder:
    uvicorn app.main:app --reload --port 8000
Swagger UI: http://localhost:8000/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.errors import register_exception_handlers
from app.api.routes import health, stocks
from app.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.database.database import close_client, get_database, initialize_database, ping
from app.utils.logging_config import configure_logging
from app.utils.request_context import REQUEST_ID_HEADER, RequestIdMiddleware

logger = logging.getLogger("neuralvest")


def _startup_database(app: FastAPI, settings: Settings) -> None:
    """Connect and initialize MongoDB. Never crashes the API: problems are reported in /api/health/db."""
    app.state.db_init = None
    if not settings.mongodb_configured:
        logger.warning("MongoDB not configured: database endpoints will return 503.")
        return
    try:
        latency = ping(settings)
        app.state.db_init = initialize_database(get_database(settings))
        logger.info(
            "MongoDB connected (%.0f ms) to '%s'; init ok=%s",
            latency, settings.active_db_name, app.state.db_init["ok"],
        )
    except PyMongoError as exc:
        logger.error("MongoDB unavailable at startup: %s", exc.__class__.__name__)
        app.state.db_init = {"ok": False, "error": exc.__class__.__name__}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _startup_database(app, settings)
        yield
        close_client()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Multi-agent financial intelligence API for Indian equities (educational project).",
        lifespan=lifespan,
    )
    app.state.db_init = None

    # Middleware order: CORS is outermost so even error responses carry CORS headers.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # auth will use a bearer token header, not cookies
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(stocks.router)
    return app


app = create_app()
