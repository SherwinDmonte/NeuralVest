"""MongoDB connection management, startup initialization and storage monitoring.

One MongoClient per process (PyMongo pools connections internally). The client is created
lazily so the API can start, and report a clear status, even when Atlas is unreachable.
"""

import logging
import threading
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from app.api.errors import AppError
from app.config import Settings, get_settings
from app.database.indexes import ensure_indexes
from app.database.schema_validators import apply_validators
from app.utils.timing import stopwatch

logger = logging.getLogger("neuralvest.db")

_client: MongoClient | None = None
_client_lock = threading.Lock()


def create_client(settings: Settings) -> MongoClient:
    """A new, independent MongoClient (the app uses the shared one from get_client)."""
    if not settings.mongodb_configured:
        raise AppError(
            503,
            "database_not_configured",
            "MongoDB is not configured. Set MONGODB_URI (with the real password) in backend/.env.",
        )
    return MongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        retryWrites=True,
        maxPoolSize=10,  # far below the Atlas free-tier limit of 500 connections
        tz_aware=True,  # datetimes come back timezone-aware (UTC)
        uuidRepresentation="standard",
    )


def get_client(settings: Settings | None = None) -> MongoClient:
    """Return the shared MongoClient, creating it on first use."""
    global _client
    settings = settings or get_settings()
    with _client_lock:
        if _client is None:
            _client = create_client(settings)
    return _client


def get_database(settings: Settings | None = None) -> Database:
    settings = settings or get_settings()
    return get_client(settings)[settings.active_db_name]


def close_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


def ping(settings: Settings | None = None) -> float:
    """Round-trip to the cluster. Returns latency in milliseconds; raises on failure."""
    with stopwatch() as t:
        get_client(settings).admin.command("ping")
    return round(t["seconds"] * 1000, 1)


def initialize_database(db: Database) -> dict[str, Any]:
    """Apply validators then indexes. Idempotent; safe to run at every startup."""
    validators = apply_validators(db)
    indexes = ensure_indexes(db)
    failed = [c for c, outcome in validators.items() if outcome == "failed"]
    failed += [c for c, outcome in indexes.items() if isinstance(outcome, str)]
    return {"validators": validators, "indexes": indexes, "ok": not failed, "failed": sorted(set(failed))}


def storage_status(settings: Settings | None = None) -> dict[str, Any]:
    """Estimate storage use against the Atlas free-tier quota (database_design.md §4.5).

    Counts NeuralVest's own databases (main + test) and adds STORAGE_RESERVED_MB for other
    projects sharing the cluster, which NeuralVest's least-privilege user cannot measure.
    """
    settings = settings or get_settings()
    client = get_client(settings)
    used_bytes = 0
    per_db: dict[str, float] = {}
    for name in (settings.mongodb_db_name, settings.mongodb_test_db_name):
        stats = client[name].command("dbStats")
        size = int(stats.get("dataSize", 0)) + int(stats.get("indexSize", 0))
        per_db[name] = round(size / 1024**2, 2)
        used_bytes += size

    neuralvest_mb = used_bytes / 1024**2
    total_mb = neuralvest_mb + settings.storage_reserved_mb
    pct = 100 * total_mb / settings.storage_limit_mb
    level = "block" if pct >= settings.storage_block_pct else "warn" if pct >= settings.storage_warn_pct else "ok"
    return {
        "neuralvest_mb": round(neuralvest_mb, 2),
        "per_database_mb": per_db,
        "reserved_mb": settings.storage_reserved_mb,
        "total_mb": round(total_mb, 2),
        "limit_mb": settings.storage_limit_mb,
        "used_pct": round(pct, 2),
        "level": level,
        "basis": "dataSize + indexSize (uncompressed), plus STORAGE_RESERVED_MB",
    }


def ensure_storage_available(settings: Settings | None = None) -> None:
    """Raise 507 before a large write when the storage guard is at the 'block' level."""
    status = storage_status(settings)
    if status["level"] == "block":
        raise AppError(
            507,
            "storage_limit_reached",
            "Database storage is nearly full. Clean up old data before running new analyses.",
            {"used_pct": status["used_pct"]},
        )
