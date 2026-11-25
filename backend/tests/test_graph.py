"""LangGraph workflow, offline: synthetic prices, fake LLM, fixture news (task 5.4.4)."""

from datetime import UTC, datetime

import pytest

from app.agents import market_research as mr
from app.agents import stock_analysis as sa
from app.config import Settings
from app.data import news_data as nd
from app.database import models as m
from app.orchestration import graph as graph_module
from app.orchestration.graph import build_graph, initial_state
from tests.agent_fakes import FakeLLM, news_transport, patch_benchmark, patch_fundamentals, patch_market_data


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    patch_fundamentals(monkeypatch, sa)  # no network for the Stock Analysis agent
    patch_benchmark(monkeypatch, graph_module)  # no network for the Risk Assessment agent


def graph(tmp_path, llm=None, db=None):
    return build_graph(llm=llm or FakeLLM(), db=db, settings=Settings(_env_file=None, data_cache_dir=tmp_path),
                       include_gdelt=False, news_transport=news_transport())


def test_reliance_end_to_end(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path).invoke(initial_state(["RELIANCE"]))
    assert final["stock_symbols"] == ["RELIANCE.NS"] and final["request_type"] == "single_stock"
    assert final["agent_status"] == {"validate_input": "completed", "market_research": "completed",
                                     "financial_news": "completed", "stock_analysis": "completed",
                                     "risk_assessment": "partial", "output_validation": "completed",
                                     "report": "completed"}  # no risk-free rate
    assert len(final["market_data"]["RELIANCE.NS"]["records"]) == 250  # shared with later agents
    assert final["market_analysis"]["RELIANCE.NS"]["trend"]["classification"]
    assert final["news_analysis"]["RELIANCE.NS"]["articles_analyzed"] > 0
    assert set(final["timestamps"]) == {"validate_input", "market_research", "financial_news", "stock_analysis",
                                        "risk_assessment", "output_validation", "report"}
    assert {s["agent"] for s in final["data_sources"]} == {"market_research", "financial_news", "stock_analysis",
                                                           "risk_assessment"}
    risk = final["risk_analysis"]["per_symbol"]["RELIANCE.NS"]
    assert risk["beta"]["value"] == 1.0  # synthetic benchmark = same returns, scaled
    assert risk["window"]["observations"] == 249 and final["risk_analysis"]["portfolio"] is None
    assert final["stock_analysis"]["RELIANCE.NS"]["metrics"]["pe"]["value"] is not None  # price from Agent 1
    assert final["financial_data"]["RELIANCE.NS"]["latest_period"]["income_statement"] == "2026-03-31"
    report = final["final_report"]
    assert report["status"] == "partial" and report["request_id"] == final["request_id"]  # Sharpe unavailable
    assert report["sections"]["news_summary"]["RELIANCE.NS"]["digest"]
    assert report["key_observations"]["source"] == "llm" and len(report["key_observations"]["items"]) >= 2
    assert report["traceability"]["ok"], report["traceability"]
    assert {"rsi", "pe", "volatility", "sharpe"} <= set(report["glossary"]) and "backtest" not in report["glossary"]
    assert final["validation"]["issue_count"] == 0 and final["execution_plan"]["mode"] == "sequential"


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
    assert "stock_analysis" not in final["agent_status"] and "risk_assessment" not in final["agent_status"]


def test_symbols_deduplicated_and_portfolio_detected(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path).invoke(initial_state(["reliance", "RELIANCE.NS", "NSE:TCS"], investment_amount=100000))
    assert final["stock_symbols"] == ["RELIANCE.NS", "TCS.NS"] and final["request_type"] == "portfolio"
    assert final["risk_analysis"]["portfolio"]["correlation"]["matrix"]  # two stocks: portfolio view
    po = final["portfolio_analysis"]  # amount + 2 stocks: the Portfolio Optimization branch ran
    assert final["agent_status"]["portfolio_optimization"] in ("completed", "partial")
    assert sum(x["weight_pct"] for x in po["allocations"]) == pytest.approx(100)
    section = final["final_report"]["sections"]["portfolio"]
    assert section["portfolio_id"] == po["portfolio_id"] and "equity_curve" not in (section["backtest"] or {})
    assert final["validation"]["portfolio_candidates"] == ["RELIANCE.NS", "TCS.NS"]


def test_single_stock_skips_portfolio_branch(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path).invoke(initial_state(["RELIANCE"], investment_amount=50000))
    assert final["request_type"] == "single_stock" and "portfolio_optimization" not in final["agent_status"]
    assert final["portfolio_analysis"] == {} and final["final_report"]["sections"]["portfolio"] is None
    assert final["execution_plan"]["agents"]["portfolio_optimization"]["run"] is False
    assert any("at least 2 valid stocks" in e["message"] for e in final["errors"])


@pytest.mark.integration
def test_graph_persists_agent_results(tmp_path, monkeypatch, clean_db):
    patch_market_data(monkeypatch, mr)
    final = graph(tmp_path, db=clean_db).invoke(initial_state(["RELIANCE"]))
    agents = {d["agent_name"] for d in clean_db[m.AGENT_RESULTS].find({"request_id": final["request_id"]})}
    assert agents == {"market_research", "financial_news", "stock_analysis", "risk_assessment"}


@pytest.mark.parametrize("failure", ["connection_refused", "timeout", "server_error"])
def test_ollama_failing_mid_run_still_gives_a_full_report(tmp_path, monkeypatch, failure):
    """Phase 13 (13.1.2, LLM failures): the REAL Ollama client with a transport that fails every
    call. Every agent still finishes with its rule-based template, says so, and the report is built."""
    import httpx

    from app.llm.ollama_client import OllamaClient

    def broken(request):
        if failure == "connection_refused":
            raise httpx.ConnectError("refused", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(500, json={"error": "model runner crashed"})

    patch_market_data(monkeypatch, mr)
    settings = Settings(_env_file=None, data_cache_dir=tmp_path, llm_min_free_ram_mb=0)
    with OllamaClient(settings, transport=httpx.MockTransport(broken), ram_probe=lambda: 4000) as llm:
        final = build_graph(llm=llm, db=None, settings=settings, include_gdelt=False,
                            news_transport=news_transport()).invoke(initial_state(["RELIANCE", "TCS"], investment_amount=100_000))
    assert final["final_report"]["status"] in ("completed", "partial") and not final["errors"]
    for key in ("market_analysis", "stock_analysis"):
        for sym, out in final[key].items():
            assert out["llm"]["source"] == "template" and out["explanation"], (key, sym)
            assert "without the AI model" in out["explanation"]
    for out in final["news_analysis"].values():
        assert out["articles"] and all(a["sentiment"] == "uncertain" for a in out["articles"])  # nothing guessed
        assert out["digest_source"] == "template" and not out["llm"]["models"]
    portfolio = final["portfolio_analysis"]
    assert portfolio["llm"]["source"] == "template" and portfolio["allocations"]
    obs = final["final_report"]["key_observations"]
    assert obs["source"] == "template" and "could not produce" in obs["reason"]
    assert final["final_report"]["traceability"]["ok"]
