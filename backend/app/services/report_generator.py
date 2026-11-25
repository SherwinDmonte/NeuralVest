"""Report Generation (Phase 10): one unified financial intelligence report per request.

Rules:
  * Every section is assembled from agent outputs in the workflow state. Python copies the
    values; nothing is recalculated and nothing is invented. A section without data is marked
    unavailable with the reason, and listed under "data limitations".
  * The only AI-written part is "key observations": 3-5 sentences built from the rule-based
    readings, checked by the same guards as every other AI text (no invented numbers, no
    contradiction of a reading). If the model fails, the observations are the readings.
  * Traceability (task 10.3.3): after assembly, every number in the report is looked up in the
    agent outputs. Untraced numbers are listed; untraced numbers in AI text replace that text
    with the template.
  * A glossary explains, in plain language, only the metrics that appear in the report.
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.data.errors import InvalidSymbolError
from app.data.symbols import exchange_of
from app.llm import prompts as p
from app.llm.guards import StockFacts, _is_supported, extract_numbers
from app.schemas.agents import PORTFOLIO_DISCLAIMER, RISK_DISCLAIMER
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.report")

REPORT_VERSION = "1.0"
OK = ("completed", "partial")
MAX_LLM_SYMBOLS = 5  # the key-observation prompt must fit the 2048-token context
MAX_LIMITATIONS = 40

GLOSSARY = {
    "trend": "Trend: whether the price sits above its 20-, 50- and 200-day averages in order (bullish), below "
             "them in order (bearish), or neither (sideways).",
    "sma": "Simple moving average (SMA): the average closing price over the last 20, 50 or 200 trading days.",
    "rsi": "RSI (14): a 0-100 gauge of recent gains vs losses. Above 70 is often called overbought, below 30 "
           "oversold. It describes the past, not the future.",
    "macd": "MACD: the gap between a fast and a slow average of prices. Above its signal line means upward "
            "momentum has recently been strengthening.",
    "benchmark": "NIFTY 50 comparison: the stock's price change over the period next to India's main index.",
    "sentiment": "News sentiment: whether recent headlines about the company read as positive, negative or "
                 "neutral, as judged by a small local AI model. It can be wrong.",
    "pe": "P/E ratio: share price divided by yearly earnings per share; how many years of current profit "
          "the price represents.",
    "pb": "P/B ratio: share price divided by book value (shareholders' equity) per share.",
    "roe": "Return on equity (ROE): yearly profit as a percentage of shareholders' money in the company.",
    "roa": "Return on assets (ROA): yearly profit as a percentage of everything the company owns.",
    "debt_to_equity": "Debt-to-equity: borrowed money compared with shareholders' money. Higher means more "
                      "reliance on debt (normal for banks, which are assessed differently).",
    "current_ratio": "Current ratio: short-term assets divided by short-term debts; above 1 means near-term "
                     "bills are covered.",
    "margins": "Operating and net margin: the share of revenue left after operating costs, and after all "
               "costs and taxes.",
    "growth": "Revenue / profit growth: change against the previous year (YoY) or the average yearly rate over "
              "several years (CAGR).",
    "volatility": "Volatility: how much the price usually swings in a year, from daily price changes. Higher "
                  "means a bumpier ride.",
    "beta": "Beta: how strongly the stock moved with the NIFTY 50. 1 means in step, below 0.8 calmer "
            "(defensive), above 1.2 more extreme (aggressive).",
    "max_drawdown": "Maximum drawdown: the largest fall from a previous high to a later low in the period.",
    "sharpe": "Sharpe ratio: return above the risk-free rate (91-day Treasury bill) per unit of volatility. "
              "Negative means the stock did worse than the risk-free rate.",
    "correlation": "Correlation: how similarly two stocks moved, from -1 (opposite) to 1 (identical). Low "
                   "correlation helps diversification.",
    "effective_stocks": "Effective number of stocks: how many equally sized holdings the portfolio behaves like.",
    "optimisation": "Portfolio optimisation: choosing weights from past returns and volatilities. Minimum "
                    "volatility seeks the smallest swings; maximum Sharpe the best past return per unit of risk.",
    "backtest": "Backtest: replaying the allocation rule on past prices it did not use when deciding. "
                "CAGR is the average yearly growth, after the assumed trading costs.",
}


class ReportSummaryOutput(BaseModel):
    observations: list[str] = Field(min_length=2, max_length=5)


# ---------------------------------------------------------------- helpers
def _pick(d: dict | None, keys: tuple[str, ...]) -> dict:
    d = d or {}
    return {k: d.get(k) for k in keys}


def _metric_values(metrics: dict) -> dict:
    return {k: (v or {}).get("value") for k, v in (metrics or {}).items()}


def _exchange(symbol: str) -> str | None:
    try:
        return exchange_of(symbol)
    except InvalidSymbolError:
        return None


def _unavailable(reason: str | None) -> dict:
    return {"available": False, "reason": reason or "the agent produced no result"}


def overall_status(state: dict[str, Any]) -> str:
    statuses = {k: v for k, v in state.get("agent_status", {}).items()
                if k not in ("validate_input", "output_validation", "report")}
    if not state.get("stock_symbols") or statuses.get("market_research") in (None, "failed", "skipped"):
        return "failed"
    if all(v in ("completed", "skipped") for v in statuses.values()):
        return "completed"
    return "partial"


# ---------------------------------------------------------------- sections (10.3.1)
def build_sections(state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    symbols = state.get("stock_symbols", [])
    market, news = state.get("market_analysis") or {}, state.get("news_analysis") or {}
    fundamentals = state.get("stock_analysis") or {}
    risk = state.get("risk_analysis") or {}
    risk_symbols = risk.get("per_symbol") or {}
    limitations: list[str] = []
    s: dict[str, Any] = {k: {} for k in ("company_overview", "market_summary", "technical_analysis", "news_summary",
                                         "sentiment", "fundamentals", "financial_health")}

    for sym in symbols:
        mr, nw, sa, rk = market.get(sym) or {}, news.get(sym) or {}, fundamentals.get(sym) or {}, risk_symbols.get(sym) or {}
        mr_ok = mr.get("status") in OK
        s["company_overview"][sym] = {
            "company_name": mr.get("company_name") or sa.get("company_name"), "exchange": _exchange(sym),
            "sector": sa.get("sector"), "industry": sa.get("industry"),
            "last_close": mr.get("last_close"), "last_close_date": mr.get("last_close_date"),
        }
        if mr_ok:
            s["market_summary"][sym] = {
                **_pick(mr, ("last_close", "last_close_date", "period_return_pct", "last_bar_may_be_incomplete")),
                "benchmark_comparison": _pick(mr.get("benchmark_comparison"),
                                              ("stock_return_pct", "benchmark_return_pct", "relative_pct", "outperformed")),
                "volume": _pick(mr.get("volume"), ("last_volume", "avg_volume_20d", "last_vs_avg_ratio")),
            }
            ind = mr.get("indicators") or {}
            s["technical_analysis"][sym] = {
                "trend": (mr.get("trend") or {}).get("classification"),
                "trend_rule": ((mr.get("trend") or {}).get("rules_triggered") or [None])[0],
                "indicators": {"sma_20": ind.get("sma_20"), "sma_50": ind.get("sma_50"), "sma_200": ind.get("sma_200"),
                               "rsi_14": ind.get("rsi_14"),
                               "macd": _pick(ind.get("macd"), ("macd", "signal", "histogram"))},
                "rsi_zone": mr.get("rsi_zone"), "readings": mr.get("readings") or {},
                "explanation": mr.get("explanation"), "explanation_source": (mr.get("llm") or {}).get("source"),
            }
        else:
            reason = "; ".join(mr.get("errors") or []) or "no price data"
            for key in ("market_summary", "technical_analysis"):
                s[key][sym] = _unavailable(reason)
            limitations.append(f"{sym}: market data unavailable ({reason}); the other sections for it are skipped.")

        if nw.get("status") in OK:
            s["news_summary"][sym] = {
                "articles_collected": nw.get("articles_collected"), "articles_analyzed": nw.get("articles_analyzed"),
                "lookback_days": nw.get("lookback_days"), "digest": nw.get("digest"),
                "digest_source": nw.get("digest_source"),
                "top_headlines": [_pick(a, ("headline", "publisher", "url", "published_at", "sentiment", "category"))
                                  for a in (nw.get("articles") or [])[:5]],
            }
            s["sentiment"][sym] = {"overall_sentiment": nw.get("overall_sentiment"),
                                   "breakdown": nw.get("sentiment_breakdown"), "disclaimer": nw.get("disclaimer")}
        else:
            reason = "; ".join(nw.get("errors") or []) or ("not run: market data unavailable" if not mr_ok else
                                                           "no news result")
            s["news_summary"][sym] = s["sentiment"][sym] = _unavailable(reason)
            if mr_ok:
                limitations.append(f"{sym}: news unavailable ({reason}).")

        if sa.get("status") in OK:
            s["fundamentals"][sym] = {"statement_periods": sa.get("statement_periods"), "is_bank": sa.get("is_bank"),
                                      "price_used": sa.get("price_used"), "metrics": _metric_values(sa.get("metrics")),
                                      "unavailable_metrics": sa.get("unavailable") or [],
                                      "explanation": sa.get("explanation"),
                                      "explanation_source": (sa.get("llm") or {}).get("source")}
            s["financial_health"][sym] = _pick(sa, ("overall", "assessments", "strengths", "weaknesses"))
            if sa.get("statements_stale"):
                limitations.append(f"{sym}: the latest annual statements are more than a year old.")
        else:
            reason = ("indices have no financial statements" if sa.get("status") == "skipped"
                      else "; ".join(sa.get("errors") or []) or "no fundamentals result")
            s["fundamentals"][sym] = s["financial_health"][sym] = _unavailable(reason)
            if mr_ok and sa.get("status") != "skipped":
                limitations.append(f"{sym}: fundamentals unavailable ({reason}).")

    s["risk"] = {"per_symbol": {}, "portfolio": None, "disclaimer": RISK_DISCLAIMER}
    for sym in symbols:
        rk = risk_symbols.get(sym) or {}
        if rk.get("status") in OK:
            s["risk"]["per_symbol"][sym] = {
                **_pick(rk, ("risk_classification", "annualized_volatility_pct", "annualized_return_pct",
                             "market_sensitivity", "readings", "explanation")),
                "beta": (rk.get("beta") or {}).get("value"),
                "max_drawdown_pct": (rk.get("max_drawdown") or {}).get("max_drawdown_pct"),
                "sharpe": (rk.get("sharpe") or {}).get("value"),
                "sharpe_reason": (rk.get("sharpe") or {}).get("reason"),
                "window": rk.get("window"),
            }
        elif (market.get(sym) or {}).get("status") in OK:
            reason = "; ".join(rk.get("errors") or []) or "no risk result"
            s["risk"]["per_symbol"][sym] = _unavailable(reason)
            limitations.append(f"{sym}: risk could not be measured ({reason}).")
    pr = risk.get("portfolio")
    if pr:
        s["risk"]["portfolio"] = {"correlation": (pr.get("correlation") or {}).get("matrix"),
                                  "diversification": pr.get("diversification"),
                                  "concentration": pr.get("concentration"),
                                  "weights_assumption": pr.get("weights_assumption")}

    s["portfolio"] = None
    po = state.get("portfolio_analysis") or {}
    plan = ((state.get("execution_plan") or {}).get("agents") or {}).get("portfolio_optimization") or {}
    if po.get("status") in OK:
        bk = po.get("backtest") or {}
        s["portfolio"] = {
            **_pick(po, ("portfolio_id", "investment_amount", "risk_preference", "method", "method_label",
                         "fallback_reason", "constraints", "allocations", "invested_inr", "leftover_cash_inr",
                         "readings", "explanation")),
            "expected_metrics": _pick(po.get("expected_metrics"), ("annual_return_pct", "annual_volatility_pct",
                                                                   "sharpe_ratio", "basis")),
            "backtest": ({**_pick(bk, ("period", "cagr_pct", "volatility_pct", "sharpe", "max_drawdown_pct",
                                       "total_costs_inr", "fallbacks_used")),
                          "equal_weight_cagr_pct": ((bk.get("vs_benchmark") or {}).get("equal_weight") or {}).get("cagr_pct"),
                          "nifty50_cagr_pct": ((bk.get("vs_benchmark") or {}).get("nifty50") or {}).get("cagr_pct"),
                          "limitations": bk.get("limitations")} if bk else None),
            "backtest_reason": po.get("backtest_reason"),
            "disclaimer": po.get("disclaimer") or PORTFOLIO_DISCLAIMER,
        }
    elif state.get("request_type") == "portfolio":
        reason = ("; ".join(po.get("errors") or []) or (state.get("validation") or {}).get("portfolio_skip_reason")
                  or "the portfolio step did not run")
        s["portfolio"] = _unavailable(reason)
        limitations.append(f"Portfolio unavailable: {reason}.")
    elif plan.get("reason") and state.get("investment_amount") is not None:
        limitations.append(f"Portfolio not built: {plan['reason']}.")
    return s, limitations


# ---------------------------------------------------------------- key observations
def observation_facts(state: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    """Only rule-based readings and labels (each figure inside its sentence)."""
    facts: dict[str, Any] = {}
    market = state.get("market_analysis") or {}
    risk = (state.get("risk_analysis") or {}).get("per_symbol") or {}
    fund = state.get("stock_analysis") or {}
    news = state.get("news_analysis") or {}
    for i, sym in enumerate(symbols):
        mr, rk, sa, nw = market.get(sym) or {}, risk.get(sym) or {}, fund.get(sym) or {}, news.get(sym) or {}
        tag = sym.split(".")[0].lower()
        for key in ("benchmark_reading", "long_term_reading"):
            if (mr.get("readings") or {}).get(key):
                facts[f"{tag}_{key}"] = f"{sym}: " + mr["readings"][key]
        if (mr.get("trend") or {}).get("classification"):
            facts[f"{tag}_trend_reading"] = f"{sym}: the moving-average trend is {mr['trend']['classification']}"
        if (rk.get("readings") or {}).get("risk_reading"):
            facts[f"{tag}_risk_reading"] = f"{sym}: " + rk["readings"]["risk_reading"]
        if sa.get("overall") and sa.get("status") in OK:
            facts[f"{tag}_fundamentals_reading"] = (f"{sym}: the financial statements look "
                                                    f"{sa['overall'].replace('_', ' ')} overall")
        if nw.get("overall_sentiment") and nw.get("status") in OK:
            facts[f"{tag}_news_reading"] = (f"{sym}: recent news sentiment is "
                                            f"{nw['overall_sentiment'].replace('_', ' ')} "
                                            f"({nw.get('articles_analyzed', 0)} articles)")
    po = state.get("portfolio_analysis") or {}
    for key in ("method_reading", "backtest_reading"):
        if (po.get("readings") or {}).get(key):
            facts[f"portfolio_{key}"] = "portfolio: " + po["readings"][key]
    div = ((state.get("risk_analysis") or {}).get("portfolio") or {}).get("diversification") or {}
    if div.get("assessment") and div.get("average_pairwise_correlation") is not None:
        facts["diversification_reading"] = (f"diversification across the stocks is {div['assessment']} (average "
                                            f"correlation {div['average_pairwise_correlation']})")
    return facts


_PREFERRED = ("benchmark_reading", "risk_reading", "fundamentals_reading")


def template_observations(facts: dict[str, Any]) -> list[str]:
    """Up to 5 readings, most important first. Phase 13: taken in turn from each stock (its
    benchmark, risk and fundamentals readings first), so every stock appears when it fits;
    before, five stocks' preferred readings could fill all five places with two stocks."""
    groups: dict[str, list[str]] = {}
    for key in facts:
        owner = "portfolio" if key.startswith(("portfolio_", "diversification_")) else str(facts[key]).split(":")[0]
        groups.setdefault(owner, []).append(key)
    queues = [sorted(keys, key=lambda k: (not k.endswith(_PREFERRED), list(facts).index(k)))
              for owner, keys in groups.items() if owner != "portfolio"] + [groups.get("portfolio", [])]
    picked: list[str] = []
    while len(picked) < 5 and any(queues):
        for queue in queues:
            if queue and len(picked) < 5:
                picked.append(queue.pop(0))
    return [facts[k][0].upper() + facts[k][1:] + "." for k in picked] or ["No observations could be made."]


def stock_facts(state: dict[str, Any], symbols: list[str], facts: dict[str, Any]) -> tuple[list[StockFacts], list[str]]:
    """Each stock's own readings (they start with "SYMBOL: ") and the shared portfolio readings,
    for the per-stock observation check (Phase 13, task 13.3.4)."""
    market = state.get("market_analysis") or {}
    stocks = []
    for sym in symbols:
        mr = market.get(sym) or {}
        name = re.sub(r"\s+(Limited|Ltd\.?)$", "", (mr.get("company_name") or "").strip(), flags=re.IGNORECASE)
        stocks.append(StockFacts(
            symbol=sym, aliases=tuple(a for a in (sym, sym.split(".")[0], name if len(name) >= 4 else "") if a),
            facts=tuple(v for v in facts.values() if str(v).startswith(f"{sym}: ")),
            relative_pct=(mr.get("benchmark_comparison") or {}).get("relative_pct"),
        ))
    owned = {f for s in stocks for f in s.facts}
    return stocks, [str(v) for v in facts.values() if v not in owned]


def key_observations(state: dict[str, Any], llm, use_llm: bool) -> dict[str, Any]:
    symbols = [s for s in state.get("stock_symbols", [])
               if ((state.get("market_analysis") or {}).get(s) or {}).get("status") in OK]
    facts = observation_facts(state, symbols[:MAX_LLM_SYMBOLS])
    template = template_observations(facts)
    if not facts:
        return {"items": template, "source": "template", "model": None, "reason": "no readings available"}
    if llm is None or not use_llm or len(symbols) > MAX_LLM_SYMBOLS:
        reason = ("AI summary disabled" if (llm is None or not use_llm)
                  else f"more than {MAX_LLM_SYMBOLS} stocks: readings shown directly")
        return {"items": template, "source": "template", "model": None, "reason": reason}
    stocks, shared = stock_facts(state, symbols, facts)
    res = llm.generate_structured(p.report_summary_prompt(facts, stocks, shared), ReportSummaryOutput,
                                  lambda: ReportSummaryOutput(observations=template[:5] if len(template) >= 2
                                                              else template + ["See the sections below."]))
    meta = res.metadata()
    failed = [a.get("reason") for a in meta.get("attempts", []) if not a.get("ok")]
    out = {"items": res.value.observations, "source": meta.get("source"), "model": meta.get("model"), "facts": facts}
    if failed:  # why the AI text was retried or replaced, so it is never a silent fallback
        out["rejected_attempts"] = failed
    if meta.get("source") != "llm":
        out["reason"] = "the AI model could not produce valid observations" + (f" ({failed[-1]})" if failed else "")
    return out


# ---------------------------------------------------------------- traceability (10.3.3)
def _numbers(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        out.extend(extract_numbers(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, out)


def _leaves(obj: Any, path: str, out: list[tuple[str, float]]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append((path, float(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _leaves(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _leaves(v, f"{path}[{i}]", out)


def trace_numbers(sections: dict[str, Any], observations: list[str], state: dict[str, Any]) -> dict[str, Any]:
    """Every numeric value in the sections must appear in an agent output; every number in the
    AI observations must appear (up to rounding) in an agent output."""
    allowed: list[float] = []
    for key in ("market_analysis", "news_analysis", "stock_analysis", "risk_analysis", "portfolio_analysis"):
        _numbers(state.get(key), allowed)
    _numbers({"amount": state.get("investment_amount")}, allowed)
    exact = set(allowed)
    leaves: list[tuple[str, float]] = []
    _leaves(sections, "sections", leaves)
    untraced = [path for path, v in leaves if v not in exact]
    text_numbers = [n for text in observations for n in extract_numbers(text)]
    untraced_text = [n for n in text_numbers if not _is_supported(n, allowed)]
    return {"numbers_checked": len(leaves) + len(text_numbers), "untraced_values": untraced[:20],
            "untraced_in_observations": untraced_text[:20], "ok": not untraced and not untraced_text}


# ---------------------------------------------------------------- glossary (10.3.2)
def glossary_for(sections: dict[str, Any]) -> dict[str, str]:
    terms = []
    if any(v.get("available", True) for v in sections["technical_analysis"].values()):
        terms += ["trend", "sma", "rsi", "macd", "benchmark"]
    if any(v.get("available", True) for v in sections["sentiment"].values()):
        terms.append("sentiment")
    if any(v.get("available", True) for v in sections["fundamentals"].values()):
        terms += ["pe", "pb", "roe", "roa", "debt_to_equity", "current_ratio", "margins", "growth"]
    if sections["risk"]["per_symbol"]:
        terms += ["volatility", "beta", "max_drawdown", "sharpe"]
    if sections["risk"]["portfolio"]:
        terms += ["correlation", "effective_stocks"]
    if sections.get("portfolio") and sections["portfolio"].get("available", True):
        terms += ["optimisation", "backtest"]
    return {t: GLOSSARY[t] for t in dict.fromkeys(terms)}


# ---------------------------------------------------------------- sources + limitations
def source_references(state: dict[str, Any]) -> list[dict[str, Any]]:
    seen, refs = set(), []
    for d in state.get("data_sources", []):
        key = (d.get("source"), d.get("detail"), d.get("symbol"))
        if key in seen:
            continue
        seen.add(key)
        refs.append({k: d.get(k) for k in ("agent", "symbol", "source", "detail", "data_as_of", "fetched_at")})
    return refs


STANDARD_LIMITATIONS = [
    "Prices come from Yahoo Finance via the unofficial yfinance library: end-of-day data that can be delayed, "
    "revised or occasionally wrong.",
    "Financial statements are annual figures from the same source; they lag the company's latest quarter.",
    "News comes from public RSS feeds (and GDELT when enabled); coverage is incomplete and sentiment is judged by "
    "a small local AI model.",
    "Every metric describes the past. Nothing in this report is a forecast or personalised investment advice.",
]


def build_report(state: dict[str, Any], llm=None, use_llm: bool = True) -> dict[str, Any]:
    sections, limitations = build_sections(state)
    observations = key_observations(state, llm, use_llm)
    trace = trace_numbers(sections, observations["items"], state)
    if trace["untraced_in_observations"] and observations["source"] == "llm":
        observations = {"items": template_observations(observations.get("facts") or {}), "source": "template",
                        "model": None, "reason": f"AI text used numbers not in the data: "
                                                 f"{trace['untraced_in_observations'][:3]}"}
        trace = trace_numbers(sections, observations["items"], state)
    if not trace["ok"]:
        limitations.append(f"Traceability check: {len(trace['untraced_values'])} value(s) could not be traced to "
                           "an agent output (listed under traceability).")
        logger.warning("Report numbers not traced: %s", trace["untraced_values"][:5])
    observations.pop("facts", None)

    validation = state.get("validation") or {}
    for agent, by_symbol in (validation.get("agents") or {}).items():
        for sym, v in by_symbol.items():
            for issue in v.get("issues", []):
                limitations.append(f"{sym} ({agent.replace('_', ' ')}): {issue}.")
    for r in state.get("retries", []):
        if r.get("retried"):
            limitations.append(f"{r['symbol']}: the {r['agent'].replace('_', ' ')} step was retried after a temporary "
                               f"error ({r['reason']}).")
    for e in state.get("errors", []):
        if e.get("agent") == "validate_input":
            limitations.append(f"Input: {e['message']}")
    limitations = list(dict.fromkeys(limitations))
    if len(limitations) > MAX_LIMITATIONS:
        limitations = limitations[:MAX_LIMITATIONS] + [f"... and {len(limitations) - MAX_LIMITATIONS} more."]

    unavailable = sorted({f"{name}:{sym}" for name, by_symbol in sections.items() if isinstance(by_symbol, dict)
                          for sym, v in by_symbol.items() if isinstance(v, dict) and v.get("available") is False})
    return {
        "report_version": REPORT_VERSION,
        "status": overall_status(state),
        "request_id": state.get("request_id"),
        "generated_at": utc_now().isoformat(),
        "request": {"symbols": state.get("stock_symbols", []), "request_type": state.get("request_type"),
                    "investment_amount": state.get("investment_amount"),
                    "risk_preference": state.get("risk_preference")},
        "key_observations": observations,
        "sections": sections,
        "unavailable_sections": unavailable,
        "data_limitations": STANDARD_LIMITATIONS + limitations,
        "source_references": source_references(state),
        "glossary": glossary_for(sections),
        "traceability": trace,
        "execution": {"agent_status": state.get("agent_status", {}), "timings": state.get("timestamps", {}),
                      "retries": state.get("retries", []), "plan": state.get("execution_plan"),
                      "validation_issue_count": validation.get("issue_count", 0)},
        "errors": state.get("errors", []),
        "disclaimers": [RISK_DISCLAIMER, PORTFOLIO_DISCLAIMER] if sections.get("portfolio") else [RISK_DISCLAIMER],
    }
