"""Failure paths that had no test before Phase 13 (task 13.1.1-13.1.3): Yahoo rate limits and
errors, unexpected responses, the stock routes' 404/502 answers, health checks while MongoDB or
Ollama is down, a database user without the dbAdmin role, and the global error handlers.
Nothing here touches the network or a real database."""

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pymongo.errors import OperationFailure, PyMongoError, ServerSelectionTimeoutError

from app.config import get_settings
from app.data import financial_data as fd
from app.data import stock_data as sd
from app.data.errors import DataSourceError, NoDataError
from app.database import schema_validators as sv
from app.main import create_app

OHLCV = pd.DataFrame({"Open": [1.0, 2.0], "High": [1.5, 2.5], "Low": [0.5, 1.5], "Close": [1.2, 2.2],
                      "Adj Close": [1.2, 2.2], "Volume": [100, 200]},
                     index=pd.to_datetime(["2026-11-19", "2026-11-20"]).tz_localize("Asia/Kolkata"))


class FakeTicker:
    """yf.Ticker stand-in: `history` replies from a list (an exception is raised)."""

    def __init__(self, replies=(), info=None, statements=None):
        self.replies, self._info, self.statements = list(replies), info, statements or {}

    def __call__(self, symbol):
        return self

    def history(self, **_):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def info(self):
        if isinstance(self._info, Exception):
            raise self._info
        return self._info

    def __getattr__(self, name):
        if name in ("income_stmt", "balance_sheet", "cashflow"):
            value = self.statements.get(name)
            if isinstance(value, Exception):
                raise value
            return value
        raise AttributeError(name)


@pytest.fixture
def no_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(sd.time, "sleep", waits.append)
    return waits


# ---------------------------------------------------------------- Yahoo downloads
def test_rate_limit_is_retried_then_succeeds(monkeypatch, no_sleep):
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker([sd.yf.exceptions.YFRateLimitError(), OHLCV]))
    frame = sd._download("RELIANCE.NS", "1y")
    assert list(frame.columns) == ["open", "high", "low", "close", "adjusted_close", "volume"]
    assert no_sleep == [2]


def test_repeated_network_errors_become_a_data_source_error(monkeypatch, no_sleep):
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker([ConnectionError()] * 3))
    with pytest.raises(DataSourceError, match="Yahoo Finance unavailable for RELIANCE.NS: ConnectionError"):
        sd._download("RELIANCE.NS", "1y")
    assert no_sleep == [2, 5]


def test_an_empty_answer_means_no_data(monkeypatch, no_sleep):
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker([pd.DataFrame()]))
    with pytest.raises(NoDataError, match="invalid or delisted"):
        sd._download("NOTREAL.NS", "1y")


def test_a_changed_response_format_is_reported(monkeypatch, no_sleep):
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker([OHLCV.drop(columns=["Adj Close"])]))
    with pytest.raises(DataSourceError, match="missing columns"):
        sd._download("RELIANCE.NS", "1y")


def test_company_profile_fetch_cache_and_errors(monkeypatch, tmp_path):
    settings = get_settings().model_copy(update={"data_cache_dir": tmp_path})
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker(info={"longName": "Reliance Industries Limited",
                                                          "sector": "Energy", "currency": "INR"}))
    first = sd.get_company_profile("RELIANCE", settings=settings)
    assert first["company_name"] == "Reliance Industries Limited" and first["exchange"] == "NSE"
    assert not first["from_cache"]
    assert sd.get_company_profile("RELIANCE.NS", settings=settings)["from_cache"]

    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker(info={"symbol": "X"}))
    with pytest.raises(NoDataError):
        sd.get_company_profile("TCS.NS", use_cache=False, settings=settings)
    monkeypatch.setattr(sd.yf, "Ticker", FakeTicker(info=TimeoutError()))
    with pytest.raises(DataSourceError, match="TimeoutError"):
        sd.get_company_profile("TCS.NS", use_cache=False, settings=settings)


def statement_frame(values: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(values, index=pd.to_datetime(["2026-03-31", "2025-03-31"])).T


def test_financial_statements_fetch_cache_and_errors(monkeypatch, tmp_path):
    settings = get_settings().model_copy(update={"data_cache_dir": tmp_path})
    good = {"income_stmt": statement_frame({"Total Revenue": [120.0, 100.0], "Net Income": [12.0, 10.0]}),
            "balance_sheet": statement_frame({"Total Assets": [500.0, 450.0]}),
            "cashflow": statement_frame({"Operating Cash Flow": [20.0, 18.0]})}
    monkeypatch.setattr(fd.yf, "Ticker", FakeTicker(statements=good))
    fs = fd.get_financial_statements("TCS", settings=settings)
    assert fs.symbol == "TCS.NS" and not fs.from_cache
    assert list(fs.statements["income_statement"]) == ["2026-03-31", "2025-03-31"]  # newest first
    assert fd.get_financial_statements("TCS.NS", settings=settings).from_cache

    monkeypatch.setattr(fd.yf, "Ticker", FakeTicker(statements={"income_stmt": pd.DataFrame(),
                                                                "balance_sheet": None, "cashflow": pd.DataFrame()}))
    with pytest.raises(NoDataError):
        fd.get_financial_statements("INFY.NS", use_cache=False, settings=settings)
    monkeypatch.setattr(fd.yf, "Ticker", FakeTicker(statements={"income_stmt": ConnectionError()}))
    with pytest.raises(DataSourceError, match="ConnectionError"):
        fd.get_financial_statements("INFY.NS", use_cache=False, settings=settings)


# ---------------------------------------------------------------- stock routes
@pytest.fixture
def client(no_db_settings):
    with TestClient(create_app(no_db_settings)) as c:
        yield c


def raise_(exc):
    def fn(*_, **__):
        raise exc
    return fn


@pytest.mark.parametrize("exc, status, code", [
    (NoDataError("No financial statements available for TCS.NS."), 404, "financials_not_found"),
    (DataSourceError("Yahoo Finance statements unavailable"), 502, "data_source_unavailable"),
])
def test_financials_route_errors(client, monkeypatch, exc, status, code):
    from app.api.routes import stocks
    monkeypatch.setattr(stocks, "get_financial_statements", raise_(exc))
    r = client.get("/api/stocks/TCS.NS/financials")
    assert r.status_code == status and r.json()["error"]["code"] == code


@pytest.mark.parametrize("exc, status, code", [
    (NoDataError("No price data"), 404, "stock_not_found"),
    (DataSourceError("Yahoo Finance unavailable"), 502, "data_source_unavailable"),
])
def test_indicators_route_errors(client, monkeypatch, exc, status, code):
    from app.api.routes import stocks
    monkeypatch.setattr(stocks, "get_price_history", raise_(exc))
    r = client.get("/api/stocks/TCS.NS/indicators")
    assert r.status_code == status and r.json()["error"]["code"] == code


def test_search_still_works_when_stored_companies_cannot_be_read(monkeypatch, no_db_settings):
    from app.api.routes import stocks
    configured = no_db_settings.model_copy(update={"mongodb_uri": SecretStr("mongodb+srv://user:secret@example.invalid/")})
    monkeypatch.setattr(stocks, "get_settings", lambda: configured)
    monkeypatch.setattr(stocks, "get_database", raise_(ServerSelectionTimeoutError("down")))
    with TestClient(create_app(no_db_settings)) as c:
        body = c.get("/api/stocks/search", params={"q": "RELI"}).json()
    assert body["items"][0]["symbol"] == "RELIANCE.NS" and body["items"][0]["source"] == "curated_list"
    assert "could not be searched (ServerSelectionTimeoutError)" in body["note"]


# ---------------------------------------------------------------- health checks
def test_db_health_reports_an_unreachable_cluster(monkeypatch, no_db_settings):
    from app.api.routes import health
    configured = no_db_settings.model_copy(update={"mongodb_uri": SecretStr("mongodb+srv://user:secret@example.invalid/")})
    monkeypatch.setattr(health, "get_settings", lambda: configured)
    monkeypatch.setattr(health, "ping", raise_(PyMongoError("timeout")))
    r = TestClient(create_app(no_db_settings)).get("/api/health/db")  # no lifespan: no real connection
    assert r.status_code == 503 and r.json()["connected"] is False
    assert "secret" not in r.text and "IP allowlist" in r.json()["message"]


@pytest.mark.parametrize("available, installed, free_mb, would_use", [
    (False, [], 4000, None),
    (True, ["qwen3:1.7b", "qwen3:0.6b"], 4000, "qwen3:1.7b"),
    (True, ["qwen3:1.7b", "qwen3:0.6b"], 800, "qwen3:0.6b"),  # too little RAM for the primary model
    (True, ["qwen3:1.7b"], 800, "qwen3:1.7b"),  # no fallback installed: the primary is still tried
    (True, ["llama3"], 4000, None),
])
def test_llm_health_says_which_model_would_answer(client, monkeypatch, available, installed, free_mb, would_use):
    from app.llm import ollama_client
    fake = SimpleNamespace(is_available=lambda: available, installed_models=lambda: installed)
    monkeypatch.setattr(ollama_client, "get_llm_client", lambda: fake)
    monkeypatch.setattr(ollama_client, "available_ram_mb", lambda: free_mb)
    body = client.get("/api/health/llm").json()
    assert body["available"] is available and body["would_use"] == would_use
    assert (body["note"] is None) == available


# ---------------------------------------------------------------- validators without dbAdmin
class FakeDb:
    """The existing Atlas user may lack dbAdmin, so collMod fails with code 13 (Unauthorized)."""

    def __init__(self, existing, error_code):
        self.existing, self.error_code, self.created = existing, error_code, []

    def list_collection_names(self):
        return list(self.existing)

    def create_collection(self, name, **_):
        self.created.append(name)

    def command(self, cmd):
        raise OperationFailure("not allowed", code=self.error_code)


@pytest.mark.parametrize("code, outcome", [(13, "unchanged_no_permission"), (2, "failed")])
def test_apply_validators_keeps_going_without_permission(code, outcome):
    names = list(sv.VALIDATORS)
    db = FakeDb(existing=names[:2], error_code=code)
    result = sv.apply_validators(db)
    assert result[names[0]] == result[names[1]] == outcome
    assert all(result[n] == "created" for n in names[2:]) and db.created == names[2:]


# ---------------------------------------------------------------- global error handlers
@pytest.mark.parametrize("exc, status, code", [
    (ServerSelectionTimeoutError("no primary"), 503, "database_unavailable"),
    (OperationFailure("bad"), 500, "database_error"),
    (RuntimeError("bug"), 500, "internal_error"),
])
def test_unhandled_errors_get_the_standard_envelope(no_db_settings, exc, status, code):
    app = create_app(no_db_settings)

    @app.get("/api/boom")
    def boom():
        raise exc

    origin = no_db_settings.cors_origin_list[0]
    r = TestClient(app).get("/api/boom", headers={"Origin": origin})
    assert r.status_code == status
    assert r.headers["access-control-allow-origin"] == origin  # the web app can read the error
    body = r.json()["error"]
    assert body["code"] == code and body["request_id"] == r.headers["X-Request-ID"]
    assert "no primary" not in r.text and "bug" not in body["message"]  # internals are not leaked
