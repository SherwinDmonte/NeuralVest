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
