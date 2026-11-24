"""Health endpoints: is the API up, and can it reach MongoDB Atlas?"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.errors import AppError
from app.config import APP_VERSION, get_settings
from app.database.database import ping, storage_status

router = APIRouter(prefix="/api/health", tags=["health"])
logger = logging.getLogger("neuralvest.health")


@router.get("", summary="API liveness")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "version": APP_VERSION, "environment": settings.app_env}


@router.get("/db", summary="MongoDB connectivity, initialization and storage use")
def health_db(request: Request) -> JSONResponse:
    """Returns 200 when the database is reachable, 503 otherwise (same body shape)."""
    settings = get_settings()
    body: dict = {
        "configured": settings.mongodb_configured,
        "connected": False,
        "database": settings.active_db_name,
        "latency_ms": None,
        "initialization": getattr(request.app.state, "db_init", None),
        "storage": None,
    }
    if not settings.mongodb_configured:
        body["message"] = "MONGODB_URI is not set (or still contains <password>) in backend/.env."
        return JSONResponse(status_code=503, content=body)
    try:
        body["latency_ms"] = ping(settings)
        body["connected"] = True
        body["storage"] = storage_status(settings)
    except (PyMongoError, AppError) as exc:
        logger.warning("Database health check failed: %s", exc.__class__.__name__)
        body["message"] = "Cannot reach MongoDB Atlas (check network access / IP allowlist and credentials)."
        return JSONResponse(status_code=503, content=body)
    return JSONResponse(status_code=200, content=body)


@router.get("/llm", summary="Local AI model status (Ollama): reachable, installed models, which one would answer")
def health_llm() -> dict:
    """Read-only. The model actually used is chosen per call from the free RAM (Phase 4 rule)."""
    from app.llm.ollama_client import available_ram_mb, get_llm_client

    settings = get_settings()
    client = get_llm_client()
    available = client.is_available()
    installed = client.installed_models() if available else []
    free_mb = round(available_ram_mb())
    primary_ok = settings.llm_primary_model in installed
    fallback = settings.llm_fallback_model
    if not available:
        would_use = None
    elif primary_ok and free_mb >= settings.llm_min_free_ram_mb:
        would_use = settings.llm_primary_model
    elif fallback and fallback in installed:
        would_use = fallback
    else:
        would_use = settings.llm_primary_model if primary_ok else None
    return {
        "available": available,
        "installed_models": installed,
        "primary_model": settings.llm_primary_model,
        "fallback_model": fallback,
        "free_ram_mb": free_mb,
        "min_free_ram_mb_for_primary": settings.llm_min_free_ram_mb,
        "would_use": would_use,
        "note": None if available else "Ollama is not reachable; explanations use the rule based templates.",
    }
