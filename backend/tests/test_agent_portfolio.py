"""Portfolio Optimization Agent and /api/portfolio endpoints (no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents import portfolio_optimizer as po
from app.api.routes import portfolio as portfolio_routes
from app.config import Settings, get_settings
from app.data.data_validator import validate_ohlcv
from app.data.stock_data import PriceHistory
from app.database import models as m
from app.main import create_app
from app.schemas.agents import PortfolioOptimizationInput
from app.services.analysis_runner import AnalysisRunner
from tests.agent_fakes import NOW, FakeLLM
from tests.fixtures.generate_synthetic_prices import generate

RFR = dict(risk_free_rate_pct=6.0, risk_free_rate_date="2026-11-20", risk_free_rate_source="test rate")
SEEDS = {"TCS.NS": 42, "INFY.NS": 11, "HDFCBANK.NS": 3}


def history(symbol: str, seed: int, days: int = 500) -> PriceHistory:
    frame, report = validate_ohlcv(generate(seed=seed, days=days), symbol, now=NOW.replace(year=2031))  # synthetic dates run to 2029
    return PriceHistory(symbol=symbol, period="2y", frame=frame, report=report, fetched_at=NOW, from_cache=False)


def records(*symbols: str, days: int = 500) -> dict:
    return {s: history(s, SEEDS[s], days).to_records() for s in symbols}


BENCH = history("^NSEI", 7).frame


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def request(**kw) -> dict:
    return {"symbols": ["TCS.NS", "INFY.NS", "HDFCBANK.NS"], "investment_amount": 200_000, **kw}


def test_allocation_end_to_end_with_llm():
    llm = FakeLLM()
    out = po.run_portfolio_optimization(records(*SEEDS), request(risk_preference="aggressive"), benchmark_frame=BENCH,
                                        llm=llm, settings=settings(**RFR))
    assert out.status == "completed" and out.method == "efficient_risk" and out.fallback_reason is None
    assert sum(a["weight_pct"] for a in out.allocations) == pytest.approx(100)
    assert all(a["weight_pct"] <= 50 for a in out.allocations)  # aggressive cap
    assert out.invested_inr + out.leftover_cash_inr == pytest.approx(200_000)
    for a in out.allocations:
        assert a["amount_inr"] == pytest.approx(a["shares"] * a["last_price"], abs=0.01)
    assert out.backtest["period"]["trading_days"] > 200 and out.backtest["vs_benchmark"]["nifty50"]
    assert out.risk_free_rate["value_pct"] == 6.0 and out.expected_metrics["sharpe_ratio"] is not None
    assert llm.calls == ["portfolio_explanation"] and "not personalised investment advice" in out.disclaimer
    assert {"method_reading", "split_reading", "backtest_reading", "cash_reading"} <= set(out.readings)
    assert out.symbol == "__request__" and out.agent == "portfolio_optimization"


def test_moderate_without_risk_free_rate_falls_back():
    out = po.run_portfolio_optimization(records("TCS.NS", "INFY.NS"), request(symbols=["TCS.NS", "INFY.NS"]),
                                        benchmark_frame=BENCH, settings=settings())
    assert out.method_requested == "max_sharpe" and out.method == "min_volatility" and out.status == "partial"
    assert any("Method changed" in w for w in out.warnings) and "because" in out.readings["method_reading"]
    assert out.constraints["max_weight_pct"] == 50.0  # 35% default cannot work with 2 stocks
    assert out.llm["source"] == "template" and "without the AI model" in out.explanation


def test_one_symbol_and_excluded_symbols():
    one = po.run_portfolio_optimization(records("TCS.NS", "INFY.NS"), request(symbols=["TCS.NS", "INFY.NS"]),
                                        risk_per_symbol={"INFY.NS": {"status": "failed", "errors": ["too short"]}},
                                        settings=settings(**RFR))
    assert one.status == "failed" and "at least 2 stocks" in one.errors[0]
    assert one.excluded_symbols == {"INFY.NS": "its risk could not be measured (too short)"}

    partial = po.run_portfolio_optimization(records("TCS.NS", "INFY.NS"), request(), settings=settings(**RFR))
    assert partial.status == "partial" and partial.excluded_symbols == {"HDFCBANK.NS": "no validated price data"}
    assert sorted(partial.symbols) == ["INFY.NS", "TCS.NS"]


def test_infeasible_explicit_constraints():
    out = po.run_portfolio_optimization(records(*SEEDS), request(constraints={"max_weight_pct": 20}),
                                        settings=settings(**RFR))
    assert out.status == "failed" and "cannot be met with 3 stocks" in out.errors[0]


def test_invalid_capital_and_inputs():
    for bad in ({"investment_amount": 0}, {"investment_amount": -5}, {"investment_amount": 1e12},
                {"symbols": ["TCS.NS"]}, {"constraints": {"allow_short": True}}, {"method": "magic"},
                {"transaction_cost_bps": -1}):
        with pytest.raises(ValidationError):
            PortfolioOptimizationInput(**request(**bad))


def test_small_amount_and_short_history():
    out = po.run_portfolio_optimization(records(*SEEDS), request(investment_amount=500, method="equal_weight"),
                                        settings=settings(**RFR))
    assert out.status == "completed" and any("too small to buy one share" in w for w in out.warnings)
    short = po.run_portfolio_optimization(records("TCS.NS", "INFY.NS", days=200),
                                          request(symbols=["TCS.NS", "INFY.NS"], method="hrp"), settings=settings())
    assert short.status == "partial" and short.backtest is None and "not enough history" in short.backtest_reason


def test_portfolio_document_projection():
    out = po.run_portfolio_optimization(records(*SEEDS), request(), benchmark_frame=BENCH, settings=settings(**RFR))
    doc = po.portfolio_document(out.model_dump(mode="json"), "f" * 32)
    assert doc.portfolio_id == out.portfolio_id and len(doc.stock_allocations) == 3
    assert doc.expected_metrics["risk_free_rate"]["source"] == "test rate"
    assert "equity_curve" not in (doc.expected_metrics["backtest"] or {})


@pytest.mark.integration
def test_results_saved_with_request_scope(clean_db):
    out = po.run_portfolio_optimization(records(*SEEDS), request(), settings=settings(**RFR), db=clean_db,
                                        request_id="a" * 32)
    doc = clean_db[m.AGENT_RESULTS].find_one({"request_id": "a" * 32})
    assert doc["agent_name"] == "portfolio_optimization" and doc["scope_key"] == "__request__" and doc["symbol"] is None
    assert doc["output"]["portfolio_id"] == out.portfolio_id and doc["output"]["backtest"]["equity_curve"]


# ---------------------------------------------------------------- API
def _patch(monkeypatch):
    monkeypatch.setattr(portfolio_routes, "get_price_history",
                        lambda symbol, period="2y", **_: history(symbol, SEEDS.get(symbol, 1),
                                                                 1250 if period == "5y" else 500))
    monkeypatch.setattr(portfolio_routes, "get_benchmark_history",
                        lambda period="2y", **_: history("^NSEI", 7, 1250 if period == "5y" else 500))


@pytest.fixture
def client(monkeypatch, no_db_settings):
    _patch(monkeypatch)
    with TestClient(create_app(no_db_settings)) as c:
        yield c


def test_optimize_api_without_database(client):
    r = client.post("/api/portfolio/optimize", json={"symbols": ["TCS", "INFY", "HDFCBANK"],
                                                     "investment_amount": 100000, "risk_preference": "conservative"})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "min_volatility" and body["stored"] is False and body["request_id"] is None
    assert sum(a["weight_pct"] for a in body["allocations"]) == pytest.approx(100)
    assert client.get(f"/api/portfolio/{'0' * 32}").status_code == 503


def test_optimize_api_validation(client):
    assert client.post("/api/portfolio/optimize", json={"symbols": ["TCS", "TCS.NS"],
                                                        "investment_amount": 1000}).status_code == 422
    assert client.post("/api/portfolio/optimize", json={"symbols": ["TCS", "INFY"],
                                                        "investment_amount": 0}).status_code == 422
    r = client.post("/api/portfolio/optimize", json={"symbols": ["TCS", "INFY", "HDFCBANK"], "investment_amount": 1000,
                                                     "constraints": {"max_weight_pct": 10}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "portfolio_infeasible"


def test_backtest_api(client):
    r = client.post("/api/portfolio/backtest", json={"symbols": ["TCS", "INFY"], "method": "inverse_volatility",
                                                     "period": "5y", "rebalance": "monthly"})
    assert r.status_code == 200
    bk = r.json()["backtest"]
    assert bk["settings"]["rebalancing"] == "monthly" and len(bk["rebalances"]) > 40
    assert bk["period"]["trading_days"] == 1250 - 1 - 252 and bk["vs_benchmark"]["nifty50"]
    assert client.post("/api/portfolio/backtest", json={"symbols": ["TCS", "INFY"], "period": "3y"}).status_code == 422


@pytest.mark.integration
def test_optimize_api_stores_and_reads_back(monkeypatch, clean_db):
    _patch(monkeypatch)
    runner = AnalysisRunner(clean_db, get_settings(), llm=None)
    with TestClient(create_app(get_settings(), runner=runner)) as c:
        body = c.post("/api/portfolio/optimize", json={"symbols": ["TCS", "INFY"], "investment_amount": 50000,
                                                       "method": "hrp"}).json()
        assert body["stored"] is True
        saved = c.get(f"/api/portfolio/{body['portfolio_id']}").json()
        assert c.get(f"/api/portfolio/{'0' * 32}").status_code == 404
    runner.shutdown()
    assert saved["portfolio"]["optimization_method"] == "hrp" and saved["result"]["backtest"]["equity_curve"]
    job = clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": body["request_id"]})
    assert job["status"] == body["status"] and job["request_params"]["source"] == "api/portfolio/optimize"
    assert saved["portfolio"]["source_agent_result_ids"]
