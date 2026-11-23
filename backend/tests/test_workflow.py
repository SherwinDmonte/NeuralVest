"""Phase 10 integration tests (task 10.4.1): the full supervisor workflow offline, with
synthetic prices, fixture news and fake LLMs."""

from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents import market_research as mr
from app.agents import stock_analysis as sa
from app.config import Settings
from app.data import news_data as nd
from app.data.errors import DataSourceError
from app.llm.ollama_client import LLMResult
from app.orchestration import graph as graph_module
from app.orchestration.graph import build_graph, initial_state, run_config
from app.services import report_generator as rg
from tests.agent_fakes import (FakeLLM, news_transport, patch_benchmark, patch_fundamentals, patch_market_data,
                               synthetic_history)

RFR = dict(risk_free_rate_pct=6.0, risk_free_rate_date="2026-11-20", risk_free_rate_source="test rate")


class TemplateLLM:
    """The LLM is down: every call ends with the deterministic template (as OllamaClient does)."""

    def __init__(self):
        self.calls = []

    def generate_structured(self, spec, schema, fallback):
        self.calls.append(spec.name)
        return LLMResult(value=fallback(), source="template", model=None, attempts=[])


class NumberInventingLLM(FakeLLM):
    """Passes the client's guards in this test double, so the REPORT's own trace check must catch it."""

    def generate_structured(self, spec, schema, fallback):
        if spec.name == "report_summary":
            self.calls.append(spec.name)
            return LLMResult(value=schema(observations=["Profits will rise 42% next year.", "Risk is fine."]),
                             source="llm", model="fake-model", attempts=[])
        return super().generate_structured(spec, schema, fallback)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    patch_benchmark(monkeypatch, graph_module)


def run(tmp_path, monkeypatch, symbols, *, llm=None, mode=None, fundamentals_fail=False, checkpointer=None, **state_kw):
    patch_market_data(monkeypatch, mr)
    patch_fundamentals(monkeypatch, sa, fail=fundamentals_fail)
    g = build_graph(llm=llm if llm is not None else FakeLLM(),
                    settings=Settings(_env_file=None, data_cache_dir=tmp_path, agent_retry_delay_seconds=0, **RFR),
                    include_gdelt=False, news_transport=news_transport(), mode=mode, checkpointer=checkpointer,
                    sleep=lambda _: None)
    state = initial_state(symbols, **state_kw)
    return g.invoke(state, config=run_config(state["request_id"]) if checkpointer else None)


def test_full_five_agent_run(tmp_path, monkeypatch):
    final = run(tmp_path, monkeypatch, ["RELIANCE", "TCS"], investment_amount=100000, risk_preference="conservative")
    st = final["agent_status"]
    assert all(st[a] in ("completed", "partial") for a in ("market_research", "financial_news", "stock_analysis",
                                                           "risk_assessment", "portfolio_optimization"))
    assert st["output_validation"] == st["report"] == "completed"
    report = final["final_report"]
    sec = report["sections"]
    for name in ("company_overview", "market_summary", "technical_analysis", "news_summary", "sentiment",
                 "fundamentals", "financial_health"):
        assert set(sec[name]) == {"RELIANCE.NS", "TCS.NS"}, name
    assert sec["company_overview"]["TCS.NS"]["exchange"] == "NSE"
    assert sec["risk"]["portfolio"]["correlation"] and sec["portfolio"]["allocations"]
    assert report["traceability"]["ok"] and report["traceability"]["numbers_checked"] > 50
    assert {"optimisation", "backtest", "correlation"} <= set(report["glossary"])
    assert report["key_observations"]["source"] == "llm" and report["source_references"]
    assert any("Yahoo Finance" in x for x in report["data_limitations"])
    assert report["execution"]["plan"]["agents"]["portfolio_optimization"]["run"] is True


def test_parallel_mode_gives_the_same_results(tmp_path, monkeypatch):
    seq = run(tmp_path / "s", monkeypatch, ["RELIANCE", "TCS"])
    par = run(tmp_path / "p", monkeypatch, ["RELIANCE", "TCS"], mode="parallel")
    assert par["execution_plan"]["mode"] == "parallel"
    assert {k: v for k, v in par["agent_status"].items()} == seq["agent_status"]
    for key in ("market_analysis", "stock_analysis"):
        for sym in ("RELIANCE.NS", "TCS.NS"):
            a, b = dict(seq[key][sym]), dict(par[key][sym])
            for volatile in ("generated_at", "execution_seconds"):
                a.pop(volatile, None), b.pop(volatile, None)
            assert a == b, (key, sym)
    assert par["risk_analysis"]["per_symbol"]["TCS.NS"]["annualized_volatility_pct"] == \
        seq["risk_analysis"]["per_symbol"]["TCS.NS"]["annualized_volatility_pct"]
    assert len(par["data_sources"]) == len(seq["data_sources"])  # reducers merged all branches


def test_single_agent_failure_gives_partial_report(tmp_path, monkeypatch):
    final = run(tmp_path, monkeypatch, ["RELIANCE"], fundamentals_fail=True)
    assert final["agent_status"]["stock_analysis"] == "failed"
    assert final["agent_status"]["risk_assessment"] in ("completed", "partial")  # others still ran
    report = final["final_report"]
    assert report["status"] == "partial"
    assert report["sections"]["fundamentals"]["RELIANCE.NS"] == {
        "available": False, "reason": "No financial statements available for RELIANCE.NS."}
    assert "fundamentals:RELIANCE.NS" in report["unavailable_sections"]
    assert any("fundamentals unavailable" in x for x in report["data_limitations"])
    assert "pe" not in report["glossary"]  # glossary only explains what the report shows


def test_llm_unavailable_uses_templates(tmp_path, monkeypatch):
    llm = TemplateLLM()
    final = run(tmp_path, monkeypatch, ["RELIANCE"], llm=llm)
    report = final["final_report"]
    # articles analysed without the AI get "uncertain" sentiment, so the News agent is partial (by design)
    assert report["status"] == "partial" and final["agent_status"]["financial_news"] == "partial"
    assert "report_summary" in llm.calls
    assert report["key_observations"]["source"] == "template" and report["key_observations"]["items"]
    assert final["market_analysis"]["RELIANCE.NS"]["llm"]["source"] == "template"
    assert report["traceability"]["ok"]


def test_invalid_symbol_is_reported_and_others_continue(tmp_path, monkeypatch):
    final = run(tmp_path, monkeypatch, ["RELIANCE", "not valid!"])
    assert final["stock_symbols"] == ["RELIANCE.NS"]
    assert any(x.startswith("Input:") for x in final["final_report"]["data_limitations"])


def test_temporary_source_failure_is_retried(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    calls = {"n": 0}

    def flaky(symbol, period="1y", settings=None, now=None, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise DataSourceError("Yahoo Finance did not respond")
        return synthetic_history(symbol)

    monkeypatch.setattr(mr, "get_price_history", flaky)
    patch_fundamentals(monkeypatch, sa)
    g = build_graph(llm=FakeLLM(), settings=Settings(_env_file=None, data_cache_dir=tmp_path, agent_retry_delay_seconds=0),
                    include_gdelt=False, news_transport=news_transport(), sleep=lambda _: None)
    final = g.invoke(initial_state(["RELIANCE"]))
    assert calls["n"] == 2 and final["agent_status"]["market_research"] == "completed"
    assert final["retries"][0]["agent"] == "market_research" and final["retries"][0]["retried"]
    assert final["market_analysis"]["RELIANCE.NS"]["attempts"] == 2
    assert any("retried after a temporary error" in x for x in final["final_report"]["data_limitations"])


def test_checkpointer_records_the_run(tmp_path, monkeypatch):
    saver = InMemorySaver()
    final = run(tmp_path, monkeypatch, ["RELIANCE"], checkpointer=saver)
    g = build_graph(llm=FakeLLM(), settings=Settings(_env_file=None, data_cache_dir=tmp_path), checkpointer=saver)
    snapshot = g.get_state(run_config(final["request_id"]))
    assert snapshot.values["final_report"]["status"] == final["final_report"]["status"] and not snapshot.next


def test_report_replaces_ai_text_with_untraced_numbers(tmp_path, monkeypatch):
    final = run(tmp_path, monkeypatch, ["RELIANCE"], llm=NumberInventingLLM())
    obs = final["final_report"]["key_observations"]
    assert obs["source"] == "template" and "42" in obs["reason"]
    assert not any("42%" in x for x in obs["items"]) and final["final_report"]["traceability"]["ok"]


def test_trace_numbers_flags_values_not_in_agent_outputs():
    state = {"market_analysis": {"A.NS": {"last_close": 100.0}}}
    ok = rg.trace_numbers({"m": {"A.NS": {"last_close": 100.0}}}, ["The close was 100."], state)
    bad = rg.trace_numbers({"m": {"A.NS": {"last_close": 101.5}}}, ["It may reach 250."], state)
    assert ok["ok"] and not bad["ok"]
    assert bad["untraced_values"] == ["sections.m.A.NS.last_close"] and bad["untraced_in_observations"] == [250.0]
