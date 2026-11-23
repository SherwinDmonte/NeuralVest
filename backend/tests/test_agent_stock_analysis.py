import pytest

from app.agents import stock_analysis as sa
from app.config import Settings
from app.database import models as m
from tests.agent_fakes import FakeLLM, patch_fundamentals


def run(tmp_path, llm=None, symbol="RELIANCE", last_close=180.0, **kw):
    return sa.run_stock_analysis(symbol, last_close=last_close, price_date="2026-11-20", llm=llm,
                                 settings=Settings(_env_file=None, data_cache_dir=tmp_path), **kw)


def test_company_analysis(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa)
    llm = FakeLLM()
    out, fs = run(tmp_path, llm=llm)
    assert out.status == "completed" and fs is not None and not out.is_bank
    assert out.metrics["pe"]["value"] == 15.0 and out.metrics["roe_pct"]["value"] == 16.0
    assert out.overall == "solid" and out.strengths and out.weaknesses == []
    assert out.statement_periods["income_statement"] == "2026-03-31"
    assert out.assessment_rules["profitability"].startswith("ROE")
    assert out.explanation and llm.calls == ["stock_analysis"]
    assert out.data_sources[0].detail == "annual financial statements"


def test_facts_contain_only_computed_values_and_reasons(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa, bank=True)
    out, _ = run(tmp_path, symbol="HDFCBANK")
    facts = sa.build_facts(out)
    assert facts["metrics"]["pe"] == 15.0 and facts["is_bank"] is True
    assert str(facts["metrics"]["current_ratio"]).startswith("unavailable: not applicable")


def test_bank_stock(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa, bank=True)
    out, _ = run(tmp_path, symbol="HDFCBANK")
    assert out.is_bank and out.status == "completed"
    assert {"current_ratio", "operating_margin_pct"} <= set(out.unavailable)
    assert out.assessments["leverage"] == "not_applicable"
    assert any("Bank:" in w for w in out.warnings)


def test_missing_statements_fail(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa, fail=True)
    out, fs = run(tmp_path)
    assert out.status == "failed" and fs is None and "No financial statements" in out.errors[0]


def test_no_price_still_analyses_statements(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa)
    out, _ = run(tmp_path, last_close=None)
    assert out.metrics["pe"]["value"] is None and out.metrics["roe_pct"]["value"] == 16.0
    assert any("P/E and P/B cannot be computed" in w for w in out.warnings)


def test_currency_mismatch(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa, financial_currency="USD")
    out, _ = run(tmp_path)
    assert out.metrics["pe"]["value"] is None and "currencies" in out.metrics["pe"]["reason"]


def test_index_is_skipped(tmp_path):
    out, fs = run(tmp_path, symbol="^NSEI")
    assert out.status == "skipped" and fs is None


def test_without_llm_uses_template(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa)
    out, _ = run(tmp_path)
    assert "without the AI model" in out.explanation and "solid" in out.explanation


@pytest.mark.integration
def test_results_and_snapshot_saved(tmp_path, monkeypatch, clean_db):
    patch_fundamentals(monkeypatch, sa)
    out, _ = run(tmp_path, llm=FakeLLM(), db=clean_db, request_id="c" * 32)
    doc = clean_db[m.AGENT_RESULTS].find_one({"request_id": "c" * 32, "agent_name": "stock_analysis"})
    assert doc["scope_key"] == "RELIANCE.NS" and doc["output"]["metrics"]["pe"]["value"] == 15.0
    stock = clean_db[m.STOCKS].find_one({"symbol": "RELIANCE.NS"})
    assert stock["company_information"]["fundamentals"]["overall"] == "solid"
    assert stock["company_name"] == "Example Industries Limited"


def test_bank_facts_leave_out_debt_to_equity(tmp_path, monkeypatch):
    patch_fundamentals(monkeypatch, sa, bank=True)
    out, _ = run(tmp_path, symbol="HDFCBANK")
    facts = sa.build_facts(out)
    assert "debt_to_equity" not in facts["metrics"] and "debt_to_equity" in out.metrics  # still shown in the UI
