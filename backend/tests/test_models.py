"""Application-level validation rules (database/models.py)."""

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.database import models as m

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def uid() -> str:
    return uuid.uuid4().hex


def price(**overrides) -> dict:
    base = dict(symbol="RELIANCE.NS", date=NOW, open=100, high=110, low=95, close=105,
                adjusted_close=105, volume=1000, source="test")
    return {**base, **overrides}


# ---------------------------------------------------------------- symbols
@pytest.mark.parametrize("symbol", ["RELIANCE.NS", "500325.BO", "M&M.NS", "BAJAJ-AUTO.NS", "^NSEI"])
def test_valid_symbols(symbol):
    assert m.is_valid_symbol(symbol)


@pytest.mark.parametrize("symbol", ["reliance.ns", "RELIANCE.XX", "", "RELI ANCE.NS", "$(rm).NS"])
def test_invalid_symbols(symbol):
    assert not m.is_valid_symbol(symbol)


# ---------------------------------------------------------------- market_data
def test_market_data_valid():
    doc = m.MarketDataDocument(**price()).to_document()
    assert doc["schema_version"] == 1 and doc["date"].tzinfo is not None


@pytest.mark.parametrize(
    "overrides",
    [dict(low=106), dict(high=104), dict(open=0, low=0), dict(volume=-1)],
)
def test_market_data_rejects_bad_prices(overrides):
    with pytest.raises(ValidationError):
        m.MarketDataDocument(**price(**overrides))


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        m.MarketDataDocument(**price(date=datetime(2026, 11, 20)))


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        m.MarketDataDocument(**price(colse=1))  # typo must fail loudly


# ---------------------------------------------------------------- agent_results scope_key
def test_agent_result_symbol_scope():
    r = m.AgentResultDocument(request_id=uid(), agent_name="market_research", scope="symbol",
                              scope_key="TCS.NS", symbol="TCS.NS")
    assert r.scope_key == "TCS.NS"


def test_agent_result_request_scope():
    r = m.AgentResultDocument(request_id=uid(), agent_name="portfolio_optimization", scope="request",
                              scope_key=m.REQUEST_SCOPE_KEY)
    assert r.symbol is None


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(scope="symbol", scope_key="TCS.NS", symbol="INFY.NS"),  # mismatch
        dict(scope="symbol", scope_key="TCS.NS", symbol=None),
        dict(scope="request", scope_key=m.REQUEST_SCOPE_KEY, symbol="TCS.NS"),
        dict(scope="request", scope_key="", symbol=None),
    ],
)
def test_agent_result_scope_rules(kwargs):
    with pytest.raises(ValidationError):
        m.AgentResultDocument(request_id=uid(), agent_name="risk_assessment", **kwargs)


# ---------------------------------------------------------------- users
def test_user_rejects_plaintext_password_and_lowercases_email():
    with pytest.raises(ValidationError):
        m.UserDocument(user_id=uid(), name="A", email="a@example.com", password_hash="plaintext")
    u = m.UserDocument(user_id=uid(), name="A", email="A@Example.COM", password_hash="$argon2id$v=19$x")
    assert u.email == "a@example.com"


# ---------------------------------------------------------------- news
def test_news_rejects_non_http_url():
    with pytest.raises(ValidationError):
        m.FinancialNewsDocument(symbol="TCS.NS", headline="h", publisher="p", article_url="javascript:alert(1)",
                                url_hash="a" * 64, sentiment="neutral", source="gdelt")


# ---------------------------------------------------------------- portfolios
def alloc(symbol: str, weight: float) -> dict:
    return dict(symbol=symbol, weight_pct=weight, amount_inr=weight * 1000, shares=1, last_price=10)


def test_portfolio_weights_must_sum_to_100():
    ok = m.PortfolioDocument(portfolio_id=uid(), request_id=uid(), investment_amount=100000,
                             optimization_method="equal_weight",
                             stock_allocations=[alloc("TCS.NS", 50), alloc("INFY.NS", 50)])
    assert len(ok.stock_allocations) == 2
    with pytest.raises(ValidationError):
        m.PortfolioDocument(portfolio_id=uid(), request_id=uid(), investment_amount=100000,
                            optimization_method="equal_weight",
                            stock_allocations=[alloc("TCS.NS", 50), alloc("INFY.NS", 40)])


# ---------------------------------------------------------------- risk_reports (D4)
def test_risk_report_requires_and_stores_risk_free_rate():
    with pytest.raises(ValidationError):
        m.RiskReportDocument(request_id=uid(), symbols=["TCS.NS"])
    doc = m.RiskReportDocument(
        request_id=uid(), symbols=["TCS.NS"],
        risk_free_rate={"value_pct": 6.5, "as_of_date": date(2026, 11, 20), "source": "manual"},
    ).to_document()
    assert doc["risk_free_rate"] == {"value_pct": 6.5, "as_of_date": "2026-11-20", "source": "manual"}


# ---------------------------------------------------------------- analysis_reports (job record)
def job(**overrides) -> dict:
    base = dict(report_id=uid(), request_id=uid(), symbols=["RELIANCE.NS"],
                request_params={"symbols": ["RELIANCE.NS"]}, status="queued",
                status_history=[{"status": "queued"}])
    return {**base, **overrides}


def test_report_status_must_match_history():
    m.AnalysisReportDocument(**job())
    with pytest.raises(ValidationError):
        m.AnalysisReportDocument(**job(status="running"))


def test_interrupted_requires_reason():
    with pytest.raises(ValidationError):
        m.AnalysisReportDocument(**job(status="interrupted", status_history=[{"status": "interrupted"}]))
    m.AnalysisReportDocument(**job(status="interrupted", status_history=[{"status": "interrupted"}],
                                   interrupted_reason="server_restart_during_run"))
