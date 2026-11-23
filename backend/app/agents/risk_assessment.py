"""Agent 4: Risk Assessment.

Responsibility: measure the HISTORICAL risk of each stock and of the set of stocks together.
It reuses the prices the Market Research Agent already fetched (shared workflow state), so
nothing is downloaded twice. All metrics are computed in Python (app/analysis/risk_metrics.py);
the LLM only explains them. Historical risk is not a forecast.
"""

import logging
import time
from typing import Any

import pandas as pd
from pymongo.database import Database

from app.agents.common import LLMClient, save_agent_result
from app.agents.market_research import analysis_window
from app.analysis import risk_metrics as rm
from app.config import Settings, get_settings
from app.llm import prompts as p
from app.schemas.agents import DataSource, RiskPortfolioOutput, RiskSymbolOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.risk_assessment")
AGENT_NAME = "risk_assessment"


def frame_from_records(records: list[dict]) -> pd.DataFrame:
    """Workflow-state price records -> DataFrame indexed by trading date."""
    frame = pd.DataFrame.from_records(records)
    frame.index = pd.to_datetime(frame.pop("date"))
    return frame.sort_index()


def readings(out: RiskSymbolOutput) -> dict[str, str]:
    r: dict[str, str] = {}
    if out.annualized_volatility_pct is not None:
        r["risk_reading"] = (f"historical risk is {out.risk_classification} "
                             f"(annualised volatility {out.annualized_volatility_pct}%)")
    if out.market_sensitivity:
        r["beta_reading"] = {
            "defensive": "the stock moved less than the NIFTY 50 on average (defensive)",
            "market-like": "the stock moved roughly in line with the NIFTY 50 (market-like)",
            "aggressive": "the stock moved more than the NIFTY 50 on average (aggressive)",
        }[out.market_sensitivity]
    md = out.max_drawdown
    if md.get("max_drawdown_pct") is not None and md["max_drawdown_pct"] < 0:
        r["drawdown_reading"] = (f"its largest fall from a peak was {md['max_drawdown_pct']}% "
                                 f"({md['peak_date']} to {md['trough_date']}), "
                                 + ("and it later recovered" if md["recovered"] else "and it has not yet recovered"))
    if out.sharpe.get("value") is not None:
        r["sharpe_reading"] = ("returns did not exceed the risk-free rate after accounting for risk"
                               if out.sharpe["value"] < 0 else
                               "returns exceeded the risk-free rate after accounting for risk")
    return r


def analyse_symbol(symbol: str, frame: pd.DataFrame, bench_returns: pd.Series | None,
                   risk_free_rate: dict | None, period: str = "1y") -> RiskSymbolOutput:
    out = RiskSymbolOutput(symbol=symbol, status="failed", generated_at=utc_now(), risk_free_rate=risk_free_rate,
                           rules=rm.RISK_RULES)
    window = analysis_window(frame, period)
    returns = rm.daily_returns(window["adjusted_close"])
    out.window = {"from": window.index[0].strftime("%Y-%m-%d") if len(window) else None,
                  "to": window.index[-1].strftime("%Y-%m-%d") if len(window) else None,
                  "observations": int(len(returns)), "period": period}
    if len(returns) < rm.MIN_OBSERVATIONS:
        out.errors.append(f"Only {len(returns)} daily returns available (need {rm.MIN_OBSERVATIONS}).")
        return out
    out.annualized_volatility_pct = rm.annualized_volatility_pct(returns)
    out.annualized_return_pct = rm.annualized_return_pct(returns)
    out.return_distribution = rm.return_distribution(returns)
    out.max_drawdown = rm.max_drawdown(window["adjusted_close"])
    out.sharpe = rm.sharpe_ratio(returns, risk_free_rate)
    if bench_returns is not None:
        out.beta = rm.beta(returns, bench_returns)
    else:
        out.beta = {"value": None, "reason": "NIFTY 50 prices unavailable"}
    out.market_sensitivity = rm.market_sensitivity(out.beta.get("value"))
    out.risk_classification = rm.classify_risk(out.annualized_volatility_pct, out.max_drawdown.get("max_drawdown_pct"))
    out.readings = readings(out)

    # Risk warnings in plain language
    if out.risk_classification == "high":
        out.warnings.append("High historical risk: large price swings were common in this period.")
    md = out.max_drawdown.get("max_drawdown_pct")
    if md is not None and md < -30:
        out.warnings.append(f"Deep fall from a previous peak ({md}%).")
    if out.beta.get("value") is not None and out.beta["value"] > 1.2:
        out.warnings.append("The stock tended to amplify market moves (beta above 1.2).")
    if out.beta.get("reason"):
        out.warnings.append(f"Beta unavailable: {out.beta['reason']}.")
    if out.sharpe.get("reason"):
        out.warnings.append(f"Sharpe ratio unavailable: {out.sharpe['reason']}.")
    out.status = "partial" if (out.beta.get("value") is None or out.sharpe.get("value") is None) else "completed"
    return out


def run_risk_assessment(
    price_records: dict[str, list[dict]],
    *,
    benchmark_frame: pd.DataFrame | None = None,
    llm: LLMClient | None = None,
    db: Database | None = None,
    request_id: str | None = None,
    period: str = "1y",
    weights: dict[str, float] | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, RiskSymbolOutput], RiskPortfolioOutput | None]:
    """`price_records`: {symbol: [{date, open, ..., adjusted_close, volume}]} from the workflow state."""
    settings = settings or get_settings()
    rfr = settings.risk_free_rate
    bench_returns = None
    if benchmark_frame is not None and len(benchmark_frame):
        bench_returns = rm.daily_returns(analysis_window(benchmark_frame, period)["adjusted_close"])

    results: dict[str, RiskSymbolOutput] = {}
    window_returns: dict[str, pd.Series] = {}
    for symbol, records in price_records.items():
        started = time.perf_counter()
        frame = frame_from_records(records)
        out = analyse_symbol(symbol, frame, bench_returns, rfr, period)
        out.data_sources.append(DataSource(source="workflow state (prices fetched by the Market Research Agent)",
                                           detail=f"daily adjusted close, {period} window",
                                           data_as_of=out.window.get("to")))
        if bench_returns is not None:
            out.data_sources.append(DataSource(source="yahoo_finance_via_yfinance", detail="NIFTY 50 benchmark"))
        if rfr:
            out.data_sources.append(DataSource(source=rfr["source"], detail=f"risk-free rate {rfr['value_pct']}%",
                                               data_as_of=rfr["as_of_date"]))
        if out.status != "failed":
            window_returns[symbol] = rm.daily_returns(analysis_window(frame, period)["adjusted_close"])
            facts = {"symbol": symbol, "window": out.window, "annualised_volatility_pct": out.annualized_volatility_pct,
                     "annualised_return_pct": out.annualized_return_pct, "risk_class": out.risk_classification,
                     "beta": out.beta.get("value"), "max_drawdown_pct": out.max_drawdown.get("max_drawdown_pct"),
                     "sharpe": out.sharpe.get("value"), **out.readings}
            if llm is not None:
                res = llm.generate_structured(p.risk_explanation_prompt(facts), p.RiskExplanationOutput,
                                              p.risk_explanation_fallback(facts))
                out.explanation, out.llm = res.value.explanation, res.metadata()
            else:
                out.explanation = p.risk_explanation_fallback(facts)().explanation
                out.llm = {"source": "template", "model": None, "used_fallback": True}
        out.execution_seconds = time.perf_counter() - started
        if warning := save_agent_result(db, request_id, out, {"symbol": symbol, "period": period,
                                                              "risk_free_rate": rfr}):
            out.warnings.append(warning)
        results[symbol] = out

    portfolio = None
    if len(price_records) >= 2:
        portfolio = RiskPortfolioOutput(status="failed", generated_at=utc_now(), symbols=list(price_records),
                                        risk_free_rate=rfr)
        portfolio.correlation = rm.correlation_matrix(window_returns)
        given = {s: w for s, w in (weights or {s: 1.0 for s in window_returns}).items() if s in window_returns}
        portfolio.concentration = (rm.concentration(given) if given
                                   else {"hhi": None, "reason": "no stock had enough price history"})
        if weights:
            portfolio.weights_assumption = "weights provided by the caller"
        portfolio.diversification = rm.diversification(portfolio.correlation, portfolio.concentration)
        matrix = portfolio.correlation.get("matrix") or {}
        symbols = list(matrix)
        for i, a in enumerate(symbols):
            for b in symbols[i + 1:]:
                if (matrix[a][b] or 0) > 0.8:
                    portfolio.warnings.append(f"{a} and {b} moved very similarly (correlation {matrix[a][b]}); "
                                              "together they add little diversification.")
        if portfolio.correlation.get("reason"):
            portfolio.warnings.append(f"Correlation unavailable: {portfolio.correlation['reason']}.")
        portfolio.status = "completed" if matrix else "partial"
        if warning := save_agent_result(db, request_id, portfolio, {"symbols": portfolio.symbols, "period": period},
                                        scope="request"):
            portfolio.warnings.append(warning)
    return results, portfolio


def risk_report_fields(results: dict[str, Any], portfolio: dict[str, Any] | None) -> dict[str, Any]:
    """Projection for the `risk_reports` collection (written once by the runner)."""
    ok = {s: r for s, r in results.items() if r.get("status") in ("completed", "partial")}
    classification = {s: r["risk_classification"] for s, r in ok.items()
                      if r["risk_classification"] in ("low", "moderate", "high")}
    matrix = (portfolio or {}).get("correlation", {}).get("matrix") or {}
    return {
        "symbols": list(results),
        "volatility": {s: r["annualized_volatility_pct"] for s, r in ok.items() if r["annualized_volatility_pct"] is not None},
        "beta": {s: r["beta"].get("value") for s, r in ok.items()},
        "sharpe_ratio": {s: r["sharpe"].get("value") for s, r in ok.items()},
        "maximum_drawdown": {s: r["max_drawdown"]["max_drawdown_pct"] for s, r in ok.items()
                             if r["max_drawdown"].get("max_drawdown_pct") is not None},
        "correlation": {a: {b: v for b, v in row.items() if v is not None} for a, row in matrix.items()},
        "risk_classification": classification,
    }
