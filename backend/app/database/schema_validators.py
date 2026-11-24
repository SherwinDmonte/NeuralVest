"""Database-level validation: MongoDB `$jsonSchema` validators (database_design.md §5.1).

These protect the data even when a document bypasses the Pydantic models (a script,
mongosh, the Atlas Data Explorer). They enforce only the essentials and stay simpler than
the Pydantic models, so the two layers do not drift apart. Cross-field rules are checked by
Pydantic and by the integrity check.

Permissions note: creating a collection with a validator needs only `readWrite`.
Changing the validator of an EXISTING collection (`collMod`) needs `dbAdmin` on that
database. Without it, existing collections keep their current validator and a warning is
reported.
"""

import logging
from typing import Any

from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.database import models as m

logger = logging.getLogger("neuralvest.db.validators")

_DATE = {"bsonType": "date"}
_DATE_OR_NULL = {"bsonType": ["date", "null"]}
_STRING = {"bsonType": "string"}
_NONEMPTY = {"bsonType": "string", "minLength": 1}
_INT = {"bsonType": ["int", "long"]}
_POSITIVE = {"bsonType": "number", "minimum": 0, "exclusiveMinimum": True}
_NON_NEGATIVE = {"bsonType": "number", "minimum": 0}


def _enum(values: Any) -> dict:
    return {"enum": list(values.__args__)}


def _schema(required: list[str], properties: dict[str, Any]) -> dict:
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["schema_version", *required],
            "properties": {"schema_version": _INT, **properties},
        }
    }


VALIDATORS: dict[str, dict] = {
    m.USERS: _schema(
        ["user_id", "email", "password_hash", "created_at", "updated_at"],
        {
            "user_id": _NONEMPTY,
            "email": _NONEMPTY,
            # Blocks plaintext passwords: only Argon2 hashes are accepted.
            "password_hash": {"bsonType": "string", "pattern": r"^\$argon2"},
            "created_at": _DATE,
            "updated_at": _DATE,
        },
    ),
    # Phase 12B: profile pictures, always re-encoded by the API to a 256 x 256 WebP (at most 256 KB).
    m.USER_AVATARS: _schema(
        ["user_id", "content_type", "data", "size_bytes", "width", "height", "updated_at"],
        {
            "user_id": _NONEMPTY,
            "content_type": {"enum": ["image/webp"]},
            "data": {"bsonType": "binData"},
            "size_bytes": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 262144},
            "width": _INT,
            "height": _INT,
            "updated_at": _DATE,
        },
    ),
    m.STOCKS: _schema(
        ["symbol", "company_name", "exchange", "updated_at"],
        {"symbol": _NONEMPTY, "company_name": _NONEMPTY, "exchange": _enum(m.Exchange), "updated_at": _DATE},
    ),
    m.MARKET_DATA: _schema(
        ["symbol", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "fetched_at"],
        {
            "symbol": _NONEMPTY,
            "date": _DATE,
            "open": _POSITIVE,
            "high": _POSITIVE,
            "low": _POSITIVE,
            "close": _POSITIVE,
            "adjusted_close": _POSITIVE,
            "volume": _NON_NEGATIVE,
            "source": _NONEMPTY,
            "fetched_at": _DATE,
        },
    ),
    m.FINANCIAL_NEWS: _schema(
        ["symbol", "headline", "publisher", "article_url", "url_hash", "sentiment", "source", "fetched_at"],
        {
            "symbol": _NONEMPTY,
            "headline": _NONEMPTY,
            "publisher": _NONEMPTY,
            "article_url": {"bsonType": "string", "pattern": "^https?://"},
            "url_hash": {"bsonType": "string", "pattern": "^[0-9a-f]{64}$"},
            "publication_date": _DATE_OR_NULL,
            "sentiment": _enum(m.Sentiment),
            "source": _NONEMPTY,
            "fetched_at": _DATE,
        },
    ),
    m.AGENT_RESULTS: _schema(
        ["request_id", "agent_name", "scope", "scope_key", "execution_status", "attempts", "created_at",
         "updated_at"],
        {
            "request_id": _NONEMPTY,
            "agent_name": _enum(m.AgentName),
            "scope": {"enum": ["symbol", "request"]},
            # Never null/empty: this field is part of the unique index.
            "scope_key": _NONEMPTY,
            "symbol": {"bsonType": ["string", "null"]},
            "execution_status": _enum(m.ExecutionStatus),
            "attempts": {"bsonType": ["int", "long"], "minimum": 1},
            "created_at": _DATE,
            "updated_at": _DATE,
        },
    ),
    m.RISK_REPORTS: _schema(
        ["request_id", "symbols", "risk_free_rate", "created_at"],
        {
            "request_id": _NONEMPTY,
            "symbols": {"bsonType": "array", "minItems": 1},
            "risk_free_rate": {
                "bsonType": "object",
                "required": ["value_pct", "as_of_date", "source"],
                "properties": {
                    "value_pct": {"bsonType": "number"},
                    "as_of_date": {"bsonType": ["string", "date"]},
                    "source": _NONEMPTY,
                },
            },
            "created_at": _DATE,
        },
    ),
    m.PORTFOLIOS: _schema(
        ["portfolio_id", "request_id", "stock_allocations", "investment_amount", "optimization_method",
         "created_at"],
        {
            "portfolio_id": _NONEMPTY,
            "request_id": _NONEMPTY,
            "stock_allocations": {"bsonType": "array", "minItems": 1},
            "investment_amount": _POSITIVE,
            "optimization_method": _enum(m.OptimizationMethod),
            "created_at": _DATE,
        },
    ),
    m.ANALYSIS_REPORTS: _schema(
        ["report_id", "request_id", "symbols", "request_params", "status", "status_history", "requested_at"],
        {
            "report_id": _NONEMPTY,
            "request_id": _NONEMPTY,
            "symbols": {"bsonType": "array", "minItems": 1},
            "request_params": {"bsonType": "object"},
            "status": _enum(m.ReportStatus),
            "status_history": {"bsonType": "array", "minItems": 1},
            "requested_at": _DATE,
        },
    ),
}


def apply_validators(db: Database) -> dict[str, str]:
    """Create each collection with its validator, or update it if it already exists.

    Returns {collection: outcome}. Outcomes: "created", "updated", "unchanged_no_permission", "failed".
    """
    existing = set(db.list_collection_names())
    outcomes: dict[str, str] = {}
    for name, validator in VALIDATORS.items():
        options = {"validator": validator, "validationLevel": "strict", "validationAction": "error"}
        try:
            if name not in existing:
                db.create_collection(name, **options)
                outcomes[name] = "created"
            else:
                db.command({"collMod": name, **options})
                outcomes[name] = "updated"
        except OperationFailure as exc:
            if exc.code == 13:  # Unauthorized: collMod needs the dbAdmin role
                logger.warning("No permission to update the validator of '%s' (needs dbAdmin).", name)
                outcomes[name] = "unchanged_no_permission"
            else:
                logger.error("Could not apply validator to '%s': %s", name, exc.code)
                outcomes[name] = "failed"
    return outcomes
