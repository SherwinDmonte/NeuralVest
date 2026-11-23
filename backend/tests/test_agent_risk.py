"""Risk Assessment Agent and POST /api/risk/analyze (no network)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agents import risk_assessment as ra
from app.api.routes import risk as risk_routes
from app.config import Settings
from app.data.data_validator import validate_ohlcv
from app.data.stock_data import PriceHistory
from app.database import models as m
from app.main import create_app
from tests.agent_fakes import NOW, FakeLLM
from tests.fixtures.generate_synthetic_prices import generate

RFR = dict(risk_free_rate_pct=6.0, risk_free_rate_date="2026-11-20", risk_free_rate_source="test rate")


def history(symbol: str, seed: int, rows: int | None = None) -> PriceHistory:
    df = generate(seed=seed)
    if rows:
        df = df.iloc[-rows:]
    frame, report = validate_ohlcv(df, symbol, now=NOW)
    return PriceHistory(symbol=symbol, period="2y", frame=frame, report=report, fetched_at=NOW, from_cache=False)


def records(**symbols_seeds) -> dict:
    return {s.replace("_", ".") + "": history(s.replace("_", "."), seed).to_records()
            for s, seed in symbols_seeds.items()}


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


BENCH = history("^NSEI", 7).frame


def test_single_stock_without_risk_free_rate():
    results, portfolio = ra.run_risk_assessment({"TCS.NS": history("TCS.NS", 42).to_records()},
                                                benchmark_frame=BENCH, settings=settings())
    out = results["TCS.NS"]
    assert portfolio is None and out.status == "partial"  # Sharpe missing
    assert out.annualized_volatility_pct > 0 and out.beta["value"] is not None
    assert out.sharpe["value"] is None and any("Sharpe ratio unavailable" in w for w in out.warnings)
    assert out.risk_free_rate is None and out.risk_classification in {"low", "moderate", "high"}
    assert "not forecasts" in out.disclaimer and out.window["observations"] == 249


def test_risk_free_rate_is_used_and_recorded():
    llm = FakeLLM()
    results, _ = ra.run_risk_assessment({"TCS.NS": history("TCS.NS", 42).to_records()}, benchmark_frame=BENCH,
                                        llm=llm, settings=settings(**RFR))
    out = results["TCS.NS"]
    assert out.status == "completed" and out.sharpe["value"] is not None
    assert out.risk_free_rate == {"value_pct": 6.0, "as_of_date": "2026-11-20", "source": "test rate"}
    assert llm.calls == ["risk_explanation"] and "sharpe_reading" in out.readings
    assert any(d.detail == "risk-free rate 6.0%" for d in out.data_sources)


def test_multiple_stocks_portfolio_view():
    recs = {"TCS.NS": history("TCS.NS", 42).to_records(), "INFY.NS": history("INFY.NS", 11).to_records(),
            "CLONE.NS": history("CLONE.NS", 42).to_records()}  # identical to TCS: correlation 1
    results, portfolio = ra.run_risk_assessment(recs, benchmark_frame=BENCH, settings=settings(**RFR))
    assert set(results) == set(recs) and portfolio.status == "completed"
    assert portfolio.correlation["matrix"]["TCS.NS"]["CLONE.NS"] == 1.0
    assert portfolio.concentration["effective_number_of_stocks"] == 3.0  # equal weights
    assert any("moved very similarly" in w for w in portfolio.warnings)
    assert portfolio.symbol == "__request__"


def test_insufficient_overlapping_history():
    recs = {"TCS.NS": history("TCS.NS", 42).to_records(), "NEW.NS": history("NEW.NS", 11, rows=40).to_records()}
    results, portfolio = ra.run_risk_assessment(recs, benchmark_frame=BENCH, settings=settings())
    assert results["NEW.NS"].status == "failed" and "Only 39 daily returns" in results["NEW.NS"].errors[0]
    assert portfolio.correlation["reason"] == "needs at least two stocks"
    assert portfolio.diversification["assessment"] == "not_diversified"


def test_no_benchmark():
    results, _ = ra.run_risk_assessment({"TCS.NS": history("TCS.NS", 42).to_records()}, settings=settings())
    assert results["TCS.NS"].beta["value"] is None and results["TCS.NS"].market_sensitivity is None


def test_report_projection_fields():
    recs = {"TCS.NS": history("TCS.NS", 42).to_records(), "INFY.NS": history("INFY.NS", 11).to_records()}
    results, portfolio = ra.run_risk_assessment(recs, benchmark_frame=BENCH, settings=settings(**RFR))
    fields = ra.risk_report_fields({s: o.model_dump(mode="json") for s, o in results.items()},
                                   portfolio.model_dump(mode="json"))
    doc = m.RiskReportDocument(request_id="d" * 32, risk_free_rate=settings(**RFR).risk_free_rate, **fields)
    assert set(doc.volatility) == {"TCS.NS", "INFY.NS"} and doc.correlation["TCS.NS"]["INFY.NS"] is not None


@pytest.mark.integration
def test_results_saved_per_symbol_and_per_request(clean_db):
    recs = {"TCS.NS": history("TCS.NS", 42).to_records(), "INFY.NS": history("INFY.NS", 11).to_records()}
    ra.run_risk_assessment(recs, benchmark_frame=BENCH, settings=settings(**RFR), db=clean_db, request_id="e" * 32)
    docs = list(clean_db[m.AGENT_RESULTS].find({"request_id": "e" * 32}))
    assert sorted(d["scope_key"] for d in docs) == ["INFY.NS", "TCS.NS", "__request__"]
    request_doc = next(d for d in docs if d["scope"] == "request")
    assert request_doc["symbol"] is None and request_doc["output"]["correlation"]["matrix"]


# ---------------------------------------------------------------- API
@pytest.fixture
def client(monkeypatch, no_db_settings):
    monkeypatch.setattr(risk_routes, "get_price_history",
                        lambda symbol, period="2y", **_: history(symbol, 42 if symbol == "TCS.NS" else 11))
    monkeypatch.setattr(risk_routes, "get_benchmark_history", lambda period="2y", **_: history("^NSEI", 7))
    with TestClient(create_app(no_db_settings)) as c:
        yield c


def test_risk_api(client):
    r = client.post("/api/risk/analyze", json={"symbols": ["TCS", "INFY"], "weights": {"TCS": 3, "INFY": 1}})
    assert r.status_code == 200
    body = r.json()
    assert set(body["symbols"]) == {"TCS.NS", "INFY.NS"} and "explanation" not in body["symbols"]["TCS.NS"]
    assert body["portfolio"]["concentration"]["hhi"] == 0.625
    assert body["portfolio"]["weights_assumption"] == "weights provided by the caller"
    assert "not forecasts" in body["disclaimer"]


def test_risk_api_validation(client):
    assert client.post("/api/risk/analyze", json={"symbols": []}).status_code == 422
    assert client.post("/api/risk/analyze", json={"symbols": ["TCS"], "weights": {"TCS": -1}}).status_code == 422
