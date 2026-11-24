"""Phase 12B endpoints: market indices, curated-list breadth, financial statements, model status.
Offline: prices, statements and Ollama are faked."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes import market as market_routes
from app.api.routes import stocks as stocks_routes
from app.data.errors import DataSourceError, NoDataError
from app.data.financial_data import FinancialStatements
from app.main import create_app
from tests.agent_fakes import synthetic_history


@pytest.fixture
def client(no_db_settings):
    with TestClient(create_app(no_db_settings)) as c:
        yield c


def fake_prices(monkeypatch, failing=(), short=()):
    def prices(symbol, period="1y", settings=None, **_):
        if symbol in failing:
            raise DataSourceError(f"Yahoo Finance unavailable for {symbol}")
        h = synthetic_history(symbol, scale=1.0 + (sum(map(ord, symbol)) % 7) / 10)
        if symbol in short:
            h.frame = h.frame.iloc[:-1]  # last bar a day earlier than the others
        return h
    monkeypatch.setattr(market_routes, "get_price_history", prices)


def test_indices(client, monkeypatch):
    fake_prices(monkeypatch)
    body = client.get("/api/market/indices").json()
    names = [i["name"] for i in body["items"]]
    assert names == ["NIFTY 50", "SENSEX"]
    item = body["items"][0]
    expected = round((item["last_close"] / item["previous_close"] - 1) * 100, 2)
    assert abs(item["change_pct"] - expected) < 0.05  # adjusted vs unadjusted rounding only
    assert len(item["series"]) == market_routes.SPARK_POINTS and item["date"] > item["previous_date"]


def test_indices_partial_and_total_failure(client, monkeypatch):
    fake_prices(monkeypatch, failing=("^BSESN",))
    body = client.get("/api/market/indices").json()
    assert [i["name"] for i in body["items"]] == ["NIFTY 50"] and "^BSESN" in body["unavailable"]
    fake_prices(monkeypatch, failing=("^BSESN", "^NSEI"))
    r = client.get("/api/market/indices")
    assert r.status_code == 502 and r.json()["error"]["code"] == "data_source_unavailable"


def test_breadth_counts_and_ranking(client, monkeypatch):
    fake_prices(monkeypatch, failing=("TCS.NS",), short=("INFY.NS",))
    b = client.get("/api/market/breadth?top=3").json()
    assert "not the whole market" in b["universe"]
    assert b["left_out"]["unavailable"].keys() == {"TCS.NS"}
    assert b["left_out"]["different_last_date"] == ["INFY.NS"]  # never compared with another day
    assert b["counted"] == 28 == b["advancers"] + b["decliners"] + b["unchanged"]
    changes = [r["change_pct"] for r in b["rows"]]
    assert changes == sorted(changes, reverse=True)
    assert len(b["gainers"]) <= 3 and all(g["change_pct"] > 0 for g in b["gainers"])
    assert all(r["change_pct"] < 0 for r in b["losers"])
    assert all(r["date"] == b["as_of"] for r in b["rows"])


def test_breadth_validation(client):
    assert client.get("/api/market/breadth?top=0").status_code == 422


def test_financials(client, monkeypatch):
    fs = FinancialStatements(symbol="TCS.NS", statements={"income_statement": {"2026-03-31": {"Total Revenue": 1.0}},
                                                           "balance_sheet": {}, "cash_flow": {}},
                             latest_period={"income_statement": "2026-03-31"}, missing_key_items={},
                             is_stale=False, fetched_at=datetime(2026, 11, 24, tzinfo=UTC), from_cache=True)
    monkeypatch.setattr(stocks_routes, "get_financial_statements", lambda s: fs)
    body = client.get("/api/stocks/TCS.NS/financials").json()
    assert body["statements"]["income_statement"]["2026-03-31"]["Total Revenue"] == 1.0

    def missing(s):
        raise NoDataError("No financial statements available for X.NS.")
    monkeypatch.setattr(stocks_routes, "get_financial_statements", missing)
    assert client.get("/api/stocks/TCS.NS/financials").json()["error"]["code"] == "financials_not_found"


class FakeOllama:
    def __init__(self, up=True, models=("qwen3:1.7b", "qwen3:0.6b")):
        self.up, self.models = up, list(models)

    def is_available(self):
        return self.up

    def installed_models(self):
        return self.models


@pytest.mark.parametrize("up, ram, expected", [
    (True, 4000, "qwen3:1.7b"),   # enough free RAM: the primary model
    (True, 500, "qwen3:0.6b"),    # low RAM: the fallback
    (False, 4000, None),          # Ollama down: templates
])
def test_llm_status(client, monkeypatch, up, ram, expected):
    import app.llm.ollama_client as oc
    monkeypatch.setattr(oc, "get_llm_client", lambda: FakeOllama(up))
    monkeypatch.setattr(oc, "available_ram_mb", lambda: ram)
    monkeypatch.setenv("LLM_PRIMARY_MODEL", "qwen3:1.7b")
    body = client.get("/api/health/llm").json()
    assert body["available"] is up and body["would_use"] == expected


def test_quotes(client, monkeypatch):
    fake_prices(monkeypatch, failing=("INFY.NS",))
    body = client.get("/api/market/quotes?symbols=reliance,TCS.NS,INFY").json()
    assert [i["symbol"] for i in body["items"]] == ["RELIANCE.NS", "TCS.NS"]
    assert "INFY.NS" in body["unavailable"] and body["items"][0]["series"]
    assert client.get("/api/market/quotes?symbols=not a symbol!").status_code == 422
    many = ",".join(f"{100000 + i}" for i in range(21))
    assert client.get(f"/api/market/quotes?symbols={many}").status_code == 422


def test_risk_histogram_matches_observations(client, monkeypatch):
    from app.api.routes import risk as risk_routes
    monkeypatch.setattr(risk_routes, "get_price_history", lambda s, period="2y", **_: synthetic_history(s))
    monkeypatch.setattr(risk_routes, "get_benchmark_history", lambda period="2y", **_: synthetic_history("^NSEI", scale=20))
    body = client.post("/api/risk/analyze", json={"symbols": ["RELIANCE", "TCS"], "period": "6mo"}).json()
    for sym, dist in body["distribution"].items():
        assert sum(b["count"] for b in dist["bins"]) == dist["observations"]
        assert dist["observations"] == body["symbols"][sym]["window"]["observations"]
        assert len(dist["bins"]) == risk_routes.HISTOGRAM_BINS
