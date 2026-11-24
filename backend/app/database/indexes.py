"""Index definitions (database_design.md §3). Creation is idempotent: safe at every startup."""

import logging

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel
from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.database import models as m

logger = logging.getLogger("neuralvest.db.indexes")

INDEXES: dict[str, list[IndexModel]] = {
    m.USERS: [
        IndexModel([("user_id", ASCENDING)], name="uq_user_id", unique=True),
        IndexModel([("email", ASCENDING)], name="uq_email", unique=True),
    ],
    m.USER_AVATARS: [
        IndexModel([("user_id", ASCENDING)], name="uq_user_id", unique=True),
    ],
    m.STOCKS: [
        IndexModel([("symbol", ASCENDING)], name="uq_symbol", unique=True),
        IndexModel([("company_name", TEXT), ("symbol", TEXT)], name="txt_company_symbol"),
    ],
    m.MARKET_DATA: [
        # One row per symbol per trading day; also serves date-range queries.
        IndexModel([("symbol", ASCENDING), ("date", ASCENDING)], name="uq_symbol_date", unique=True),
    ],
    m.FINANCIAL_NEWS: [
        IndexModel([("symbol", ASCENDING), ("url_hash", ASCENDING)], name="uq_symbol_url", unique=True),
        IndexModel([("symbol", ASCENDING), ("publication_date", DESCENDING)], name="ix_symbol_pubdate"),
        IndexModel([("sentiment", ASCENDING), ("publication_date", DESCENDING)], name="ix_sentiment_pubdate"),
    ],
    m.AGENT_RESULTS: [
        # scope_key (never null) instead of symbol: see database_design.md §3.5.
        IndexModel(
            [("request_id", ASCENDING), ("agent_name", ASCENDING), ("scope_key", ASCENDING)],
            name="uq_request_agent_scope",
            unique=True,
        ),
        IndexModel([("agent_name", ASCENDING), ("created_at", DESCENDING)], name="ix_agent_created"),
        IndexModel(
            [("symbol", ASCENDING), ("agent_name", ASCENDING), ("created_at", DESCENDING)],
            name="ix_symbol_agent_created",
        ),
    ],
    m.RISK_REPORTS: [
        IndexModel([("request_id", ASCENDING)], name="uq_request_id", unique=True),
        IndexModel([("symbols", ASCENDING), ("created_at", DESCENDING)], name="ix_symbols_created"),
    ],
    m.PORTFOLIOS: [
        IndexModel([("portfolio_id", ASCENDING)], name="uq_portfolio_id", unique=True),
        IndexModel([("request_id", ASCENDING)], name="uq_request_id", unique=True),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="ix_user_created"),
    ],
    m.ANALYSIS_REPORTS: [
        IndexModel([("report_id", ASCENDING)], name="uq_report_id", unique=True),
        IndexModel([("request_id", ASCENDING)], name="uq_request_id", unique=True),
        IndexModel([("user_id", ASCENDING), ("requested_at", DESCENDING)], name="ix_user_requested"),
        IndexModel([("status", ASCENDING), ("requested_at", ASCENDING)], name="ix_status_requested"),
    ],
}


def ensure_indexes(db: Database) -> dict[str, list[str] | str]:
    """Create all indexes. Returns {collection: [index names]} or an error code per collection."""
    report: dict[str, list[str] | str] = {}
    for collection, indexes in INDEXES.items():
        try:
            report[collection] = db[collection].create_indexes(indexes)
        except OperationFailure as exc:
            logger.error("Index creation failed for '%s': code %s", collection, exc.code)
            report[collection] = f"failed (code {exc.code})"
    return report
