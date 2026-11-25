"""Phase 13 guards (tasks 13.3.4 and 13.3.5): key observations that attach a fact to the wrong
stock or skip a stock, and a stated gap to the NIFTY 50 that is not the computed difference.
Both cases were found in the 2026-11-23 live runs with the 0.6B model."""

import json

import httpx
import pytest

from app.llm import prompts as p
from app.llm.guards import StockFacts, benchmark_gap_problem, observations_problem
from app.llm.ollama_client import OllamaClient
from app.services import report_generator as rg
from tests.test_llm_client import Recorder, chat_response, settings

# The readings of the 2026-11-23 run (shape as built by report_generator.observation_facts).
REL = StockFacts(
    symbol="RELIANCE.NS", aliases=("RELIANCE.NS", "RELIANCE", "Reliance Industries"),
    facts=("RELIANCE.NS: the stock outperformed the NIFTY 50 over the period (4.12% for the stock vs -1.98% "
           "for the NIFTY 50)",
           "RELIANCE.NS: historical risk is moderate (annualised volatility 22.4%)",
           "RELIANCE.NS: the financial statements look mixed overall"),
    relative_pct=6.1)
TCS = StockFacts(
    symbol="TCS.NS", aliases=("TCS.NS", "TCS", "Tata Consultancy Services"),
    facts=("TCS.NS: the stock underperformed the NIFTY 50 over the period (-18.31% for the stock vs -1.98% "
           "for the NIFTY 50)",
           "TCS.NS: historical risk is low (annualised volatility 18.9%)",
           "TCS.NS: the financial statements look solid overall"),
    relative_pct=-16.33)
STOCKS = [REL, TCS]


# ---------------------------------------------------------------- 13.3.5 benchmark gap
def test_the_recorded_gap_mistake_is_rejected():
    # -18.31% is TCS's own return; the gap is 16.33 points (-18.31% vs -1.98%).
    reason = benchmark_gap_problem("TCS underperformed the NIFTY 50 by 18.31%.", -16.33)
    assert reason and "16.33" in reason and "18.31" in reason


@pytest.mark.parametrize("text", [
    "TCS underperformed the NIFTY 50 by 16.33 percentage points.",
    "TCS underperformed the NIFTY 50 by about 16.3 points.",
    "It trailed the benchmark by 16 points over the year.",
    "TCS returned -18.31% against -1.98% for the NIFTY 50, so it underperformed.",  # no stated gap
    "TCS fell 18.31%, which was 16.33 percentage points below the NIFTY 50.",
    "Its return exceeded the risk-free rate by 3.2 points.",  # not about the benchmark
])
def test_correct_or_absent_gaps_pass(text):
    assert benchmark_gap_problem(text, -16.33) is None


@pytest.mark.parametrize("text", [
    "TCS lagged the NIFTY 50 by 1.98%.",
    "It beat the index by 4 points.",
    "TCS was 18.31% below the NIFTY 50.",
])
def test_wrong_gaps_fail(text):
    assert benchmark_gap_problem(text, -16.33) is not None


def test_no_comparison_no_check():
    assert benchmark_gap_problem("TCS underperformed the NIFTY 50 by 18.31%.", None) is None


def test_market_explanation_with_a_wrong_gap_goes_to_the_template():
    facts = {"symbol": "TCS.NS", "trend": "bearish", "period_return_pct": -18.31, "gap_vs_nifty_pct_points": -16.33,
             "benchmark_reading": "the stock underperformed the NIFTY 50 over the period (-18.31% for the stock "
                                  "vs -1.98% for the NIFTY 50)"}
    bad = json.dumps({"explanation": "TCS is bearish. TCS underperformed the NIFTY 50 by 18.31% over the period."})
    mock = Recorder(*[chat_response(bad)] * 4)  # 2 attempts x 2 models, all wrong
    with OllamaClient(settings(), transport=httpx.MockTransport(mock), ram_probe=lambda: 4000) as client:
        result = client.generate_structured(p.market_explanation_prompt(facts), p.MarketExplanationOutput,
                                            p.market_explanation_fallback(facts))
    assert result.source == "template" and len(result.attempts) == 4
    assert all("gap of 18.31" in a["reason"] for a in result.attempts)
    assert [r["model"] for r in mock.requests] == ["qwen3:1.7b", "qwen3:1.7b", "qwen3:0.6b", "qwen3:0.6b"]
    assert "rejected" in mock.requests[1]["messages"][-1]["content"]  # repair hint


def test_market_explanation_with_the_right_gap_is_accepted():
    facts = {"symbol": "TCS.NS", "period_return_pct": -18.31, "gap_vs_nifty_pct_points": -16.33,
             "benchmark_reading": "the stock underperformed the NIFTY 50 over the period"}
    good = json.dumps({"explanation": "TCS underperformed the NIFTY 50 by 16.33 percentage points over the period."})
    with OllamaClient(settings(), transport=httpx.MockTransport(Recorder(chat_response(good))),
                      ram_probe=lambda: 4000) as client:
        result = client.generate_structured(p.market_explanation_prompt(facts), p.MarketExplanationOutput,
                                            p.market_explanation_fallback(facts))
    assert result.source == "llm"


# ---------------------------------------------------------------- 13.3.4 key observations
def test_the_recorded_misattribution_is_rejected():
    obs = ["RELIANCE.NS: the financial statements look solid overall.", "TCS.NS has low historical risk."]
    reason = observations_problem(obs, STOCKS)
    assert reason == "attaches 'solid' to RELIANCE.NS, but that reading belongs to TCS.NS"


def test_correct_observations_pass():
    obs = ["RELIANCE outperformed the NIFTY 50 (4.12% vs -1.98%), and its risk is moderate.",
           "Reliance Industries' financial statements look mixed overall.",
           "TCS underperformed the NIFTY 50 over the period.",
           "Tata Consultancy Services has low risk, with annualised volatility of 18.9%. Its statements look solid."]
    assert observations_problem(obs, STOCKS) is None


def test_a_figure_of_another_stock_is_rejected():
    reason = observations_problem(["RELIANCE has an annualised volatility of 18.9%.", "TCS has low risk."], STOCKS)
    assert reason == "attaches 18.9 to RELIANCE.NS, but that figure belongs to TCS.NS"


def test_a_later_sentence_keeps_the_subject():
    # "Its" in the second sentence still means RELIANCE.
    reason = observations_problem(["RELIANCE outperformed the NIFTY 50. Its statements look solid.", "TCS has low risk."],
                                  STOCKS)
    assert reason and "RELIANCE.NS" in reason and "solid" in reason


def test_each_stock_is_checked_against_its_own_performance_reading():
    # Before Phase 13 the combined readings made "TCS underperformed" look like a contradiction
    # (the first reading, RELIANCE's, says "outperformed"). Now only a real contradiction fails.
    ok = ["RELIANCE outperformed the NIFTY 50.", "TCS underperformed the NIFTY 50."]
    assert observations_problem(ok, STOCKS) is None
    reason = observations_problem(["RELIANCE outperformed the NIFTY 50.", "TCS outperformed the NIFTY 50."], STOCKS)
    assert reason and reason.startswith("about TCS.NS")


def test_a_wrong_gap_inside_an_observation_is_rejected():
    reason = observations_problem(["RELIANCE has moderate risk.", "TCS underperformed the NIFTY 50 by 18.31%."], STOCKS)
    assert reason and "16.33" in reason


def test_comparisons_of_two_stocks_are_not_misread():
    obs = ["RELIANCE did better than TCS against the NIFTY 50.", "TCS has low risk and RELIANCE moderate risk."]
    assert observations_problem(obs, STOCKS) is None


def test_every_stock_must_be_mentioned_for_2_to_5_stocks():
    assert observations_problem(["RELIANCE outperformed the NIFTY 50.", "Its risk is moderate."], STOCKS) == \
        "no observation about TCS.NS"
    # one stock: nothing to cover
    assert observations_problem(["The financial statements look mixed overall.", "Risk is moderate."], [REL]) is None


def test_a_stock_without_readings_need_not_be_mentioned():
    empty = StockFacts(symbol="INFY.NS", aliases=("INFY.NS", "INFY"), facts=())
    assert observations_problem(["RELIANCE has moderate risk.", "TCS has low risk."], [REL, TCS, empty]) is None


def test_the_nifty_50_name_is_not_a_figure():
    solo = StockFacts(symbol="SBIN.NS", aliases=("SBIN",), facts=("SBIN.NS: historical risk is moderate",))
    assert observations_problem(["SBIN has moderate risk compared with the NIFTY 50.", "TCS has low risk."],
                                [solo, TCS]) is None


# ---------------------------------------------------------------- report generator wiring
def two_stock_state():
    def market(sym, name, s, b):
        return {"status": "completed", "company_name": name, "trend": {"classification": "sideways"},
                "readings": {"benchmark_reading": f"the stock {'out' if s > b else 'under'}performed the NIFTY 50 over the "
                                                  f"period ({s}% for the stock vs {b}% for the NIFTY 50)"},
                "benchmark_comparison": {"relative_pct": round(s - b, 2)}}
    return {
        "stock_symbols": ["RELIANCE.NS", "TCS.NS"],
        "market_analysis": {"RELIANCE.NS": market("RELIANCE.NS", "Reliance Industries Limited", 4.12, -1.98),
                            "TCS.NS": market("TCS.NS", "Tata Consultancy Services Limited", -18.31, -1.98)},
        "stock_analysis": {"RELIANCE.NS": {"status": "completed", "overall": "mixed"},
                           "TCS.NS": {"status": "completed", "overall": "solid"}},
    }


def test_stock_facts_split_readings_by_stock():
    state = two_stock_state()
    facts = rg.observation_facts(state, state["stock_symbols"])
    stocks, shared = rg.stock_facts(state, state["stock_symbols"], facts)
    rel, tcs = stocks
    assert rel.aliases == ("RELIANCE.NS", "RELIANCE", "Reliance Industries") and tcs.relative_pct == -16.33
    assert all(f.startswith("RELIANCE.NS: ") for f in rel.facts) and len(tcs.facts) == 3 and shared == []


class ScriptedLLM:
    """Runs the real Ollama client against canned answers (all guards active)."""

    def __init__(self, *answers):
        self.mock = Recorder(*[chat_response(json.dumps({"observations": a})) for a in answers])

    def generate_structured(self, spec, schema, fallback):
        with OllamaClient(settings(), transport=httpx.MockTransport(self.mock), ram_probe=lambda: 4000) as client:
            return client.generate_structured(spec, schema, fallback)


def test_report_retries_a_misattribution_then_accepts_the_repair():
    bad = ["RELIANCE.NS: the financial statements look solid overall.", "TCS underperformed the NIFTY 50."]
    good = ["RELIANCE.NS: the financial statements look mixed overall.", "TCS underperformed the NIFTY 50."]
    out = rg.key_observations(two_stock_state(), ScriptedLLM(bad, good), use_llm=True)
    assert out["source"] == "llm" and out["items"] == good
    assert "belongs to TCS.NS" in out["rejected_attempts"][0]


def test_report_falls_back_to_readings_that_cover_every_stock():
    skipped = ["RELIANCE outperformed the NIFTY 50.", "Reliance Industries' statements look mixed overall."]
    out = rg.key_observations(two_stock_state(), ScriptedLLM(*[skipped] * 4), use_llm=True)
    assert out["source"] == "template" and "no observation about TCS.NS" in out["reason"]
    assert any(i.startswith("RELIANCE.NS") for i in out["items"]) and any(i.startswith("TCS.NS") for i in out["items"])


def test_template_takes_readings_from_each_stock_in_turn():
    facts = {}
    for sym in ("A.NS", "B.NS", "C.NS"):
        tag = sym[0].lower()
        facts[f"{tag}_benchmark_reading"] = f"{sym}: bench"
        facts[f"{tag}_long_term_reading"] = f"{sym}: long"
        facts[f"{tag}_risk_reading"] = f"{sym}: risk"
    facts["portfolio_method_reading"] = "portfolio: method"
    items = rg.template_observations(facts)
    assert items == ["A.NS: bench.", "B.NS: bench.", "C.NS: bench.", "Portfolio: method.", "A.NS: risk."]
    # one stock: the earlier order (benchmark, risk, fundamentals first) is unchanged
    one = {"x_long_term_reading": "X.NS: long", "x_benchmark_reading": "X.NS: bench", "x_risk_reading": "X.NS: risk"}
    assert rg.template_observations(one) == ["X.NS: bench.", "X.NS: risk.", "X.NS: long."]
