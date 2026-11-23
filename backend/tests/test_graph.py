"""LangGraph workflow, offline: synthetic prices, fake LLM, fixture news (task 5.4.4)."""

from datetime import UTC, datetime

import pytest

from app.agents import market_research as mr
from app.config import Settings
from app.data import news_data as nd
from app.database import models as m
from app.orchestration.graph import build_graph, initial_state
from tests.agent_fakes import FakeLLM, news_transport, patch_market_data


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))


def graph(tmp_path, llm=None, db=None):
    return build_graph(llm=llm or FakeLLM(), db=db, settings=Settings(_env_file=None, data_cache_dir=tmp_path),
                       include_gdelt=False, news_transport=news_transport())


def test_reliance_end_to_end(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path).invoke(initial_state(["RELIANCE"]))
    assert final["stock_symbols"] == ["RELIANCE.NS"] and final["request_type"] == "single_stock"
    assert final["agent_status"] == {"validate_input": "completed", "market_research": "completed",
                                     "financial_news": "completed", "report": "completed"}
    assert len(final["market_data"]["RELIANCE.NS"]["records"]) == 250  # shared with later agents
    assert final["market_analysis"]["RELIANCE.NS"]["trend"]["classification"]
    assert final["news_analysis"]["RELIANCE.NS"]["articles_analyzed"] > 0
    assert set(final["timestamps"]) == {"validate_input", "market_research", "financial_news"}
    assert {s["agent"] for s in final["data_sources"]} == {"market_research", "financial_news"}
    report = final["final_report"]
    assert report["status"] == "completed" and report["request_id"] == final["request_id"]
    assert report["sections"]["RELIANCE.NS"]["financial_news"]["digest"]
    assert "stub" in report["note"]


def test_invalid_input_goes_straight_to_report(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    llm = FakeLLM()
    final = graph(tmp_path, llm=llm).invoke(initial_state(["not valid!", ""]))
    assert final["stock_symbols"] == [] and final["final_report"]["status"] == "failed"
    assert "market_research" not in final["agent_status"] and llm.calls == []
    assert any("No valid stock symbol" in e["message"] for e in final["errors"])


def test_market_failure_skips_news(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr, fail_prices=True)
    final = graph(tmp_path).invoke(initial_state(["RELIANCE"]))
    assert final["agent_status"]["market_research"] == "failed"
    assert "financial_news" not in final["agent_status"] and final["final_report"]["status"] == "failed"


def test_symbols_deduplicated_and_portfolio_detected(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path).invoke(initial_state(["reliance", "RELIANCE.NS", "NSE:TCS"], investment_amount=100000))
    assert final["stock_symbols"] == ["RELIANCE.NS", "TCS.NS"] and final["request_type"] == "portfolio"


@pytest.mark.integration
def test_graph_persists_agent_results(tmp_path, monkeypatch, clean_db):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path, db=clean_db).invoke(initial_state(["RELIANCE"]))
    agents = {d["agent_name"] for d in clean_db[m.AGENT_RESULTS].find({"request_id": final["request_id"]})}
    assert agents == {"market_research", "financial_news"}
