import pytest

from app.agents import market_research as mr
from app.config import Settings
from app.database import models as m
from tests.agent_fakes import NOW, FakeLLM, patch_market_data


def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_cache_dir=tmp_path)


def run(tmp_path, llm=None, **kw):
    return mr.run_market_research("reliance", llm=llm, settings=settings(tmp_path), now=NOW, **kw)


def test_complete_analysis(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    llm = FakeLLM()
    out, history = run(tmp_path, llm=llm)
    assert out.status == "completed" and out.symbol == "RELIANCE.NS" and history is not None
    assert out.company_name == "Reliance Industries Limited"
    assert out.last_close_date == "2025-12-16" and out.last_close > 0
    assert set(out.indicators) >= {"sma_20", "sma_50", "sma_200", "rsi_14", "macd", "bollinger"}
    assert out.indicators["sma_200"] is not None  # 250 rows
    assert out.trend["classification"] in {"bullish", "bearish", "sideways"} and out.trend["rules_triggered"]
    assert out.benchmark_comparison["available"] and out.benchmark_comparison["trading_days"] == 250
    assert out.explanation == "The trend is described using the given facts." and out.llm["source"] == "llm"
    assert llm.calls == ["market_explanation"]
    # Indicators use a 2-year lookback; the analysis window (returns, benchmark) is 1 year.
    assert {s.detail for s in out.data_sources} == {"company profile", "daily prices (2y)", "NIFTY 50 benchmark"}
    assert out.validation["rows_valid"] == 250


def test_facts_sent_to_llm_contain_only_computed_values(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    out, _ = run(tmp_path)
    facts = mr.build_facts(out)
    assert facts["last_close"] == out.last_close and facts["rsi_14"] == out.indicators["rsi_14"]
    assert facts["trend"] == out.trend["classification"]


def test_python_readings_match_the_numbers(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    out, _ = run(tmp_path)
    facts = mr.build_facts(out)
    hist = out.indicators["macd"]["histogram"]
    assert ("above its signal" in facts["macd_reading"]) == (hist > 0)
    assert ("outperformed" in facts["benchmark_reading"]) == out.benchmark_comparison["outperformed"]
    assert ("above its 200-day" in facts["long_term_reading"]) == (out.last_close > out.indicators["sma_200"])
    assert out.rsi_zone in facts["rsi_reading"]
    assert out.readings == mr.interpret(out)  # the same readings are stored for the dashboard


def test_without_llm_uses_template(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    out, _ = run(tmp_path, llm=None)
    assert "without the AI model" in out.explanation and out.llm["source"] == "template"


def test_invalid_symbol_fails_cleanly(tmp_path):
    out, history = mr.run_market_research("NOT A SYMBOL!", settings=settings(tmp_path))
    assert out.status == "failed" and history is None and out.errors


def test_no_prices_fails(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr, fail_prices=True)
    out, history = run(tmp_path)
    assert out.status == "failed" and history is None and "No price data" in out.errors[0]


@pytest.mark.parametrize("kw, warning", [({"fail_benchmark": True}, "Benchmark comparison unavailable"),
                                         ({"fail_profile": True}, "Company profile unavailable")])
def test_optional_parts_missing_gives_partial(tmp_path, monkeypatch, kw, warning):
    patch_market_data(monkeypatch, mr, **kw)
    out, _ = run(tmp_path)
    assert out.status == "partial" and any(warning in w for w in out.warnings)


def test_short_history(tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr, rows=120)
    out, _ = run(tmp_path)
    assert out.trend["basis"] == "short_history" and out.indicators["sma_200"] is None
    patch_market_data(monkeypatch, mr, rows=30)
    out, _ = run(tmp_path)
    assert out.trend["classification"] == "insufficient_data" and out.status == "partial"


@pytest.mark.integration
def test_results_are_saved(tmp_path, monkeypatch, clean_db):
    patch_market_data(monkeypatch, mr)
    out, _ = run(tmp_path, db=clean_db, request_id="a" * 32)
    doc = clean_db[m.AGENT_RESULTS].find_one({"request_id": "a" * 32})
    assert doc["agent_name"] == "market_research" and doc["scope_key"] == "RELIANCE.NS"
    assert doc["execution_status"] == "completed" and doc["output"]["trend"] == out.trend
    assert clean_db[m.MARKET_DATA].count_documents({"symbol": "RELIANCE.NS"}) == 250
    assert clean_db[m.MARKET_DATA].count_documents({"symbol": "^NSEI"}) == 250
