"""Supervisor rules (Phase 10): input validation, routing, retries, output validation, and
the contradiction guard."""

from datetime import timedelta

import pytest

from app.config import Settings
from app.llm.guards import contradicted_reading
from app.orchestration import supervisor as sup
from app.schemas.agents import MarketResearchOutput
from app.utils.timing import utc_now

S = Settings(_env_file=None, agent_retry_attempts=1, agent_retry_delay_seconds=0)
UNDER = "the stock underperformed the NIFTY 50 over the period (-11.44% for the stock vs -1.98% for the NIFTY 50)"


# ---------------------------------------------------------------- contradiction guard
@pytest.mark.parametrize("text, bad", [
    ("The benchmark underperformed the NIFTY 50.", True),  # the Phase 9 review case
    ("The stock outperformed the NIFTY 50 this year.", True),
    ("Reliance underperformed the NIFTY 50.", False),
    ("Reliance Industries outperformed the NIFTY 50 over the year.", True),  # company name as subject
    ("Compared with the index, the stock underperformed.", False),
    ("It is a market-like stock that underperformed the benchmark.", False),
    ("The stock underperformed the NIFTY 50.", False),
    ("The NIFTY 50 outperformed the stock.", False),  # same fact, other subject
    ("The NIFTY 50 underperformed the stock.", True),
])
def test_performance_contradictions(text, bad):
    assert (contradicted_reading(text, [UNDER]) is not None) == bad


def test_opposite_phrase_contradictions():
    readings = ["MACD is above its signal line (momentum strengthening)", "the price is below its 200-day average"]
    assert contradicted_reading("MACD is below its signal line.", readings)
    assert contradicted_reading("The price is above its 200-day average.", readings)
    assert contradicted_reading("MACD is above its signal line and the price is below its 200-day average.",
                                readings) is None
    assert contradicted_reading("anything", []) is None


# ---------------------------------------------------------------- input validation + plan
def test_validate_request_builds_plan():
    out = sup.validate_request({"raw_symbols": ["reliance", "tcs", "bad!"], "investment_amount": 50000,
                                "risk_preference": "aggressive", "portfolio_options": {"method": "hrp"}}, "sequential")
    assert out["stock_symbols"] == ["RELIANCE.NS", "TCS.NS"] and out["request_type"] == "portfolio"
    assert out["execution_plan"]["agents"]["portfolio_optimization"] == {"run": True, "reason": None}
    assert [e["symbol"] for e in out["errors"]] == ["bad!"] and out["workflow_started_at"]


@pytest.mark.parametrize("state, message", [
    ({"raw_symbols": ["TCS"], "investment_amount": 1000}, "at least 2 valid stocks"),
    ({"raw_symbols": ["TCS", "INFY"], "investment_amount": -5}, "Investment amount must be"),
    ({"raw_symbols": ["TCS", "INFY"], "risk_preference": "yolo"}, "Unknown risk preference"),
    ({"raw_symbols": ["TCS", "INFY"], "investment_amount": 1000,
      "portfolio_options": {"constraints": {"allow_short": True}}}, "Invalid portfolio settings"),
])
def test_validate_request_rejects_bad_input(state, message):
    out = sup.validate_request(state, "sequential")
    assert any(message in e["message"] for e in out["errors"]) and out["request_type"] == "single_stock"
    assert out["execution_plan"]["agents"]["portfolio_optimization"]["run"] is False


def test_routing():
    assert sup.route_after_validation({"stock_symbols": []}) == "report"
    ok = {"agent_status": {"market_research": "partial"}, "execution_plan": {"mode": "sequential"}}
    assert sup.route_after_market_research(ok) == "financial_news"
    assert sup.route_after_market_research({**ok, "execution_plan": {"mode": "parallel"}}) == sup.MIDDLE_AGENTS
    assert sup.route_after_market_research({"agent_status": {"market_research": "failed"}}) == "report"
    assert sup.route_after_output_validation({"request_type": "portfolio", "validation": {"portfolio_ready": True}}) \
        == "portfolio_optimization"
    assert sup.route_after_output_validation({"request_type": "portfolio", "validation": {}}) == "report"


# ---------------------------------------------------------------- retries
def _out(status, retryable):
    return MarketResearchOutput(symbol="TCS.NS", status=status, generated_at=utc_now(), retryable=retryable,
                                errors=["Yahoo Finance unreachable"] if status == "failed" else [])


def test_retry_only_temporary_failures():
    calls = iter([_out("failed", True), _out("completed", False)])
    result, events = sup.run_with_retry(lambda: next(calls), lambda r: r, agent="market_research", symbol="TCS.NS",
                                        state={"workflow_started_at": utc_now().isoformat()}, settings=S,
                                        sleep=lambda _: None)
    assert result.status == "completed" and result.attempts == 2 and events[0]["retried"]

    permanent = sup.run_with_retry(lambda: _out("failed", False), lambda r: r, agent="m", symbol="X", state={},
                                   settings=S, sleep=lambda _: None)
    assert permanent[0].attempts == 1 and permanent[1] == []  # unknown symbol / no data: never retried

    always = sup.run_with_retry(lambda: _out("failed", True), lambda r: r, agent="m", symbol="X", state={},
                                settings=S, sleep=lambda _: None)
    assert always[0].attempts == 2  # limited by AGENT_RETRY_ATTEMPTS


def test_no_retry_after_time_budget():
    old = (utc_now() - timedelta(hours=1)).isoformat()
    result, events = sup.run_with_retry(lambda: _out("failed", True), lambda r: r, agent="m", symbol="X",
                                        state={"workflow_started_at": old}, settings=S, sleep=lambda _: None)
    assert result.attempts == 1 and events[0]["retried"] is False and "budget" in events[0]["reason"]


def test_transient_exception_classifier():
    from app.data.errors import DataSourceError, NoDataError
    assert sup.transient_exception(DataSourceError("x")) and sup.transient_exception(TimeoutError())
    assert not sup.transient_exception(NoDataError("x")) and not sup.transient_exception(KeyError("x"))


# ---------------------------------------------------------------- output validation
def _market(**kw):
    base = {"status": "completed", "last_close": 100.0, "indicators": {"rsi_14": 55.0}, "trend": {"classification": "bullish"},
            "readings": {"benchmark_reading": UNDER}, "explanation": "The stock underperformed the NIFTY 50.",
            "llm": {"source": "llm", "model": "fake"}, "warnings": []}
    return {**base, **kw}


def _risk(**kw):
    base = {"status": "completed", "annualized_volatility_pct": 20.0, "risk_classification": "moderate",
            "max_drawdown": {"max_drawdown_pct": -10.0}, "readings": {}, "explanation": "ok", "llm": {"source": "llm"}}
    return {**base, **kw}


def test_output_validation_repairs_and_records():
    state = {"stock_symbols": ["A.NS", "B.NS", "C.NS"], "request_type": "portfolio",
             "market_analysis": {"A.NS": _market(explanation="The benchmark underperformed the NIFTY 50."),
                                 "B.NS": _market(indicators={"rsi_14": float("nan")}),
                                 "C.NS": _market()},
             "risk_analysis": {"per_symbol": {"A.NS": _risk(), "B.NS": _risk(),
                                              "C.NS": _risk(annualized_volatility_pct=-1.0)}, "portfolio": None}}
    out = sup.validate_outputs(state)
    a = out["market_analysis"]["A.NS"]
    assert a["llm"]["source"] == "template" and "withheld" in a["explanation"] and "Underperformed" not in a["explanation"]
    assert a["explanation"].startswith("The stock underperformed")
    assert out["market_analysis"]["B.NS"]["indicators"]["rsi_14"] is None  # NaN removed
    v = out["validation"]
    assert v["portfolio_candidates"] == ["A.NS", "B.NS"] and "C.NS" in v["excluded_from_portfolio"]
    assert v["portfolio_ready"] and v["text_replacements"] == 1 and v["issue_count"] >= 3
    assert out["_corrections"][0]["agent"] == "market_research"


def test_portfolio_not_ready_with_one_valid_stock():
    state = {"stock_symbols": ["A.NS", "B.NS"], "request_type": "portfolio",
             "market_analysis": {"A.NS": _market(), "B.NS": _market(status="failed")},
             "risk_analysis": {"per_symbol": {"A.NS": _risk()}}}
    v = sup.validate_outputs(state)["validation"]
    assert not v["portfolio_ready"] and "only 1 stock" in v["portfolio_skip_reason"]
