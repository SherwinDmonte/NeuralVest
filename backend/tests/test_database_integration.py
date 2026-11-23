"""Integration tests against the real Atlas cluster, using ONLY the test database.

They prove the database-level safeguards work even when Pydantic is bypassed.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pymongo.errors import DuplicateKeyError, WriteError

from app.database import models as m
from app.database.database import storage_status
from app.database.integrity import check_integrity
from app.database.repository import bulk_upsert, find_page, insert_document
from app.database.retention import cleanup_market_data

pytestmark = pytest.mark.integration

DOC_VALIDATION_FAILURE = 121


def uid() -> str:
    return uuid.uuid4().hex


def bar(day: int, symbol: str = "RELIANCE.NS") -> m.MarketDataDocument:
    return m.MarketDataDocument(symbol=symbol, date=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
                                open=100, high=110, low=95, close=105, adjusted_close=105, volume=10, source="test")


def raw_bar(**overrides) -> dict:
    doc = bar(0).to_document()
    doc.update(overrides)
    return doc


# ---------------------------------------------------------------- initialization
def test_collections_have_strict_validators_and_indexes(clean_db):
    for name in m.ALL_COLLECTIONS:
        options = clean_db[name].options()
        assert "$jsonSchema" in options["validator"], name
        assert options["validationLevel"] == "strict" and options["validationAction"] == "error"
    assert "uq_request_agent_scope" in clean_db[m.AGENT_RESULTS].index_information()
    assert clean_db[m.MARKET_DATA].index_information()["uq_symbol_date"]["unique"] is True


# ---------------------------------------------------------------- database-level validation (bypassing Pydantic)
@pytest.mark.parametrize(
    "collection, doc",
    [
        (m.MARKET_DATA, raw_bar(close=-5)),  # negative price
        (m.MARKET_DATA, {k: v for k, v in raw_bar().items() if k != "source"}),  # missing field
        (m.USERS, {"user_id": uuid.uuid4().hex, "email": "a@b.c", "password_hash": "plaintext",
                   "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC), "schema_version": 1}),
        (m.AGENT_RESULTS, {"request_id": uuid.uuid4().hex, "agent_name": "risk_assessment", "scope": "request",
                           "scope_key": "", "execution_status": "completed", "attempts": 1,
                           "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC), "schema_version": 1}),
        (m.FINANCIAL_NEWS, {"symbol": "TCS.NS", "headline": "h", "publisher": "p", "article_url": "ftp://x",
                            "url_hash": "a" * 64, "sentiment": "neutral", "source": "gdelt",
                            "fetched_at": datetime.now(UTC), "schema_version": 1}),
    ],
    ids=["negative_price", "missing_field", "plaintext_password", "empty_scope_key", "non_http_url"],
)
def test_database_rejects_invalid_raw_writes(clean_db, collection, doc):
    with pytest.raises(WriteError) as exc:
        clean_db[collection].insert_one(doc)
    assert exc.value.code == DOC_VALIDATION_FAILURE


# ---------------------------------------------------------------- uniqueness
def test_duplicate_market_day_rejected(clean_db):
    insert_document(clean_db, bar(0))
    with pytest.raises(DuplicateKeyError):
        insert_document(clean_db, bar(0))


def test_agent_results_request_scope_uniqueness(clean_db):
    rid = uid()

    def result(agent: str) -> m.AgentResultDocument:
        return m.AgentResultDocument(request_id=rid, agent_name=agent, scope="request",
                                     scope_key=m.REQUEST_SCOPE_KEY)

    # Two different agents with request scope in the same request: both allowed.
    insert_document(clean_db, result("risk_assessment"))
    insert_document(clean_db, result("portfolio_optimization"))
    # The same agent twice for the same request/scope: rejected.
    with pytest.raises(DuplicateKeyError):
        insert_document(clean_db, result("risk_assessment"))


# ---------------------------------------------------------------- bulk upsert + pagination
def test_bulk_upsert_is_idempotent_and_paginates(clean_db):
    bars = [bar(i) for i in range(250)]
    first = bulk_upsert(clean_db, bars, ["symbol", "date"])
    second = bulk_upsert(clean_db, bars, ["symbol", "date"])
    assert first["upserted"] == 250
    assert second["upserted"] == 0 and second["matched"] == 250
    assert clean_db[m.MARKET_DATA].count_documents({}) == 250

    page = find_page(clean_db, m.MARKET_DATA, {"symbol": "RELIANCE.NS"}, sort=[("date", 1)], page=3, page_size=100)
    assert page["total"] == 250 and len(page["items"]) == 50 and page["has_next"] is False
    capped = find_page(clean_db, m.MARKET_DATA, page_size=1000)
    assert capped["page_size"] == 100 and "id" in capped["items"][0]


# ---------------------------------------------------------------- integrity check
def test_integrity_check_clean_then_detects_problems(clean_db):
    insert_document(clean_db, bar(0))
    assert check_integrity(clean_db)["ok"] is True

    # Positive prices pass $jsonSchema but break the cross-field rule low <= close.
    clean_db[m.MARKET_DATA].insert_one(raw_bar(date=datetime(2026, 6, 1, tzinfo=UTC), low=200))
    # An agent result with no job record is an orphan.
    insert_document(clean_db, m.AgentResultDocument(request_id=uid(), agent_name="market_research",
                                                    scope="symbol", scope_key="TCS.NS", symbol="TCS.NS"))
    checks = {i["check"] for i in check_integrity(clean_db)["issues"]}
    assert {"price_order", "orphan_agent_results"} <= checks


# ---------------------------------------------------------------- retention + storage
def test_retention_dry_run_then_apply(clean_db):
    old = m.MarketDataDocument(**{**bar(0).model_dump(), "date": datetime(2010, 1, 4, tzinfo=UTC)})
    insert_document(clean_db, old)
    insert_document(clean_db, bar(1))
    dry = cleanup_market_data(clean_db, max_years=5)
    assert dry["dry_run"] is True and dry["would_delete"] == 1
    assert clean_db[m.MARKET_DATA].count_documents({}) == 2
    done = cleanup_market_data(clean_db, max_years=5, apply=True)
    assert done["deleted"] == 1 and clean_db[m.MARKET_DATA].count_documents({}) == 1


def test_storage_status_reports_usage(test_settings, clean_db):
    status = storage_status(test_settings)
    assert status["limit_mb"] == 512 and status["level"] in {"ok", "warn", "block"}
    assert set(status["per_database_mb"]) == {test_settings.mongodb_db_name, test_settings.mongodb_test_db_name}
