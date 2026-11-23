"""Background runner + analysis API, against the test database with fake data/LLM."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.agents import market_research as mr
from app.agents import stock_analysis as sa
from app.api.routes import stocks as stocks_routes
from app.config import get_settings
from app.data import news_data as nd
from app.database import models as m
from app.database.repository import insert_document
from app.main import create_app
from app.orchestration.graph import build_graph
from app.services import analysis_runner as ar
from tests.agent_fakes import FakeLLM, news_transport, patch_fundamentals, patch_market_data, synthetic_history

pytestmark = pytest.mark.integration


@pytest.fixture
def runner(clean_db, tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    patch_fundamentals(monkeypatch, sa)
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    settings = get_settings().model_copy(update={"data_cache_dir": tmp_path})
    llm = FakeLLM()
    r = ar.AnalysisRunner(clean_db, settings, llm=llm, workflow_factory=lambda include_gdelt: build_graph(
        llm=llm, db=clean_db, settings=settings, include_gdelt=False, news_transport=news_transport()))
    yield r
    r.shutdown()


def job(db, status, request_id=None, history=None):
    rid = request_id or uuid.uuid4().hex
    insert_document(db, m.AnalysisReportDocument(
        report_id=uuid.uuid4().hex, request_id=rid, symbols=["RELIANCE.NS"],
        request_params={"symbols": ["RELIANCE.NS"], "include_gdelt": False}, status=status,
        status_history=[m.StatusEvent(status=s) for s in (history or [status])],
        interrupted_reason="server_restart_during_run" if status == "interrupted" else None))
    return rid


# ---------------------------------------------------------------- runner
def test_submit_runs_in_background_and_writes_report(runner, clean_db):
    started = runner.submit(["reliance"])
    assert started["status"] == "queued" and started["symbols"] == ["RELIANCE.NS"]
    runner.wait_idle()
    status = runner.status(started["request_id"])
    assert status["status"] == "completed"
    assert status["agents"] == {"market_research": "completed", "financial_news": "completed",
                                "stock_analysis": "completed"}
    assert [e["status"] for e in status["status_history"]] == ["queued", "running", "completed"]
    doc = clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": started["request_id"]})
    assert doc["market_analysis"]["agent_result_ids"] and doc["news_analysis"]["agent_result_ids"]
    assert doc["market_analysis"]["headline"]["RELIANCE.NS"]["trend"]  # small headline, not a copy
    assert doc["final_summary"]["status"] == "completed" and doc["completed_at"]
    assert doc["fundamental_analysis"]["headline"]["RELIANCE.NS"]["overall"] == "solid"


def test_unexpected_error_marks_job_failed(clean_db, tmp_path):
    def broken_factory(include_gdelt):
        raise RuntimeError("boom")
    r = ar.AnalysisRunner(clean_db, get_settings(), llm=None, workflow_factory=broken_factory)
    rid = r.submit(["TCS"])["request_id"]
    r.wait_idle()
    status = r.status(rid)
    assert status["status"] == "failed" and "RuntimeError" in status["status_history"][-1]["reason"]
    assert set(status["agents"].values()) == {"skipped"}
    r.shutdown()


def test_queue_limit(runner, monkeypatch):
    monkeypatch.setattr(ar, "MAX_PENDING_JOBS", 0)
    with pytest.raises(ar.AppError) as exc:
        runner.submit(["TCS"])
    assert exc.value.status_code == 429


def test_startup_recovery(runner, clean_db):
    running = job(clean_db, "running", history=["queued", "running"])
    insert_document(clean_db, m.AgentResultDocument(request_id=running, agent_name="market_research", scope="symbol",
                                                    scope_key="RELIANCE.NS", symbol="RELIANCE.NS",
                                                    execution_status="completed"))
    insert_document(clean_db, m.AgentResultDocument(request_id=running, agent_name="financial_news", scope="symbol",
                                                    scope_key="RELIANCE.NS", symbol="RELIANCE.NS",
                                                    execution_status="running"))
    queued = job(clean_db, "queued")

    assert runner.recover() == {"interrupted": 1, "requeued": 1}
    runner.wait_idle()

    doc = clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": running})
    assert doc["status"] == "interrupted" and doc["interrupted_reason"] == "server_restart_during_run"
    results = {r["agent_name"]: r["execution_status"] for r in clean_db[m.AGENT_RESULTS].find({"request_id": running})}
    assert results == {"market_research": "completed", "financial_news": "interrupted"}  # finished work kept

    requeued = clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": queued})
    assert requeued["status"] == "completed"
    assert any(e.get("reason") == "requeued_after_restart" for e in requeued["status_history"])


def test_status_after_restart_comes_from_database(runner, clean_db):
    rid = runner.submit(["RELIANCE"])["request_id"]
    runner.wait_idle()
    fresh = ar.AnalysisRunner(clean_db, runner.settings)  # new process: no live progress
    assert fresh.status(rid)["agents"] == {"market_research": "completed", "financial_news": "completed",
                                           "stock_analysis": "completed"}
    fresh.shutdown()


def test_rerun_links_new_request(runner, clean_db):
    old = job(clean_db, "interrupted", history=["queued", "running", "interrupted"])
    new = runner.rerun(old)
    runner.wait_idle()
    doc = clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": new["request_id"]})
    assert doc["retry_of"] == old and doc["status"] == "completed"
    assert clean_db[m.ANALYSIS_REPORTS].find_one({"request_id": old})["status"] == "interrupted"  # unchanged
    with pytest.raises(ar.AppError) as exc:
        runner.rerun(new["request_id"])
    assert exc.value.status_code == 409


# ---------------------------------------------------------------- API
@pytest.fixture
def client(runner, monkeypatch):
    monkeypatch.setattr(stocks_routes, "get_price_history", lambda symbol, period="1y", **_: synthetic_history(symbol))
    with TestClient(create_app(get_settings(), runner=runner)) as c:
        yield c


def test_api_full_flow(client, runner):
    assert client.post("/api/analysis/start", json={"symbols": ["not a symbol!"]}).status_code == 422
    resp = client.post("/api/analysis/start", json={"symbols": ["RELIANCE"]})
    assert resp.status_code == 202
    rid = resp.json()["request_id"]
    assert resp.json()["status_url"] == f"/api/analysis/{rid}/status"
    runner.wait_idle()

    status = client.get(f"/api/analysis/{rid}/status").json()
    assert status["status"] == "completed" and status["queue_position"] is None

    result = client.get(f"/api/analysis/{rid}").json()
    assert result["market_research"]["RELIANCE.NS"]["trend"]["classification"]
    assert result["stock_analysis"]["RELIANCE.NS"]["overall"] == "solid"
    news = result["financial_news"]["RELIANCE.NS"]
    assert news["articles"] and news["articles"][0]["article_url"].startswith("https://")  # joined from financial_news

    stored_news = client.get("/api/news/RELIANCE.NS?page_size=2").json()
    assert stored_news["total"] == len(news["articles"]) and len(stored_news["items"]) <= 2
    assert "original article" in stored_news["disclaimer"]

    history = client.get("/api/stocks/RELIANCE.NS/history?period=2y").json()
    assert len(history["records"]) == 250 and history["data_as_of"] == "2025-12-16"


def test_api_errors(client):
    assert client.get(f"/api/analysis/{'0' * 32}/status").status_code == 404
    assert client.get("/api/analysis/not-an-id/status").status_code == 422
    assert client.post(f"/api/analysis/{'0' * 32}/rerun").status_code == 404


def test_api_indicators(client):
    data = client.get("/api/stocks/RELIANCE.NS/indicators?period=6mo").json()
    assert data["series"] and {"close", "sma_20", "sma_50", "sma_200", "rsi_14", "macd_histogram"} <= set(data["series"][-1])
    assert data["latest"]["rsi_14"] == round(data["series"][-1]["rsi_14"], 2)
    assert data["trend"]["classification"] in {"bullish", "bearish", "sideways"}
    assert data["settings"]["rsi"] == 14


def test_analysis_endpoints_need_database(no_db_settings):
    with TestClient(create_app(no_db_settings)) as c:
        r = c.post("/api/analysis/start", json={"symbols": ["TCS"]})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_not_configured"
