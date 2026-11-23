"""Supervisor: the "manager" rules of the workflow (Phase 10).

It decides, but never calculates:
  * Input validation: symbols, investment amount, risk preference and portfolio options are
    checked once, at the start, and turned into an EXECUTION PLAN (which agents run and why
    an agent is skipped). Bad input fails fast with a clear message.
  * Routing: which node comes next (single stock vs portfolio, nothing usable -> report).
  * Retries, in three layers (only the third is new here):
      1. data fetchers retry network calls twice with backoff (Phase 3);
      2. the LLM client retries, then uses the fallback model, then a template (Phase 4);
      3. the supervisor runs an agent ONCE more for a symbol when it failed because a data
         source was temporarily unavailable (`retryable`), after a short delay and only
         within the workflow time budget. Unknown symbols or missing data are never retried.
     LangGraph's RetryPolicy also re-runs a node when an unexpected transient exception
     (network, database reconnect, timeout) escapes it.
  * Output validation (before Portfolio Optimization and the report): every agent output is
    checked for impossible values (NaN, negative volatility, RSI outside 0-100, counts that do
    not add up) and AI text that contradicts a rule-based reading. Problems are repaired
    conservatively (value -> null, text -> rule-based sentences) and recorded, never hidden.
"""

import logging
import math
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError
from pymongo.database import Database
from pymongo.errors import AutoReconnect, PyMongoError

from app.config import Settings
from app.data.errors import DataSourceError, InvalidSymbolError
from app.data.symbols import normalize_symbol
from app.database.models import AGENT_RESULTS, REQUEST_SCOPE_KEY
from app.llm.guards import contradicted_reading
from app.schemas.agents import MAX_INVESTMENT_INR, PortfolioOptimizationInput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.supervisor")

MAX_SYMBOLS = 10
OK_STATUSES = ("completed", "partial")
PREFERENCES = ("conservative", "moderate", "aggressive")
MIDDLE_AGENTS = ["financial_news", "stock_analysis", "risk_assessment"]
TREND_CLASSES = {"bullish", "bearish", "sideways", "insufficient_data"}
SENTIMENTS = {"positive", "negative", "neutral", "mixed", "insufficient_data"}
RISK_CLASSES = {"low", "moderate", "high", "insufficient_data"}
FUNDAMENTAL_OVERALL = {"solid", "mixed", "weak", "insufficient_data"}


def transient_exception(exc: Exception) -> bool:
    """LangGraph node RetryPolicy: retry only temporary problems, never programming errors."""
    return isinstance(exc, (DataSourceError, httpx.TransportError, AutoReconnect, TimeoutError, ConnectionError))


# ---------------------------------------------------------------- 10.1.1 input validation
def validate_request(state: dict[str, Any], mode: str) -> dict[str, Any]:
    symbols, errors = [], []

    def error(message: str, symbol: str | None = None) -> None:
        errors.append({"agent": "validate_input", "symbol": symbol, "message": message})

    for raw in state.get("raw_symbols", []):
        try:
            symbol = normalize_symbol(raw)
        except InvalidSymbolError as exc:
            error(str(exc), str(raw))
            continue
        if symbol not in symbols:
            symbols.append(symbol)
    if len(symbols) > MAX_SYMBOLS:
        error(f"At most {MAX_SYMBOLS} symbols per analysis; extra symbols ignored.")
        symbols = symbols[:MAX_SYMBOLS]
    if not symbols:
        error("No valid stock symbol provided.")

    amount = state.get("investment_amount")
    if amount is not None and not (isinstance(amount, (int, float)) and 0 < amount <= MAX_INVESTMENT_INR):
        error(f"Investment amount must be between 0 and {MAX_INVESTMENT_INR:,} INR; it was ignored.")
        amount = None
    preference = state.get("risk_preference") or "moderate"
    if preference not in PREFERENCES:
        error(f"Unknown risk preference '{preference}'; 'moderate' was used.")
        preference = "moderate"
    options = dict(state.get("portfolio_options") or {})

    plan: dict[str, Any] = {"mode": mode, "agents": {}}
    for agent in ["market_research", *MIDDLE_AGENTS]:
        plan["agents"][agent] = {"run": bool(symbols), "reason": None if symbols else "no valid symbol"}
    portfolio_reason = None
    if amount is None:
        portfolio_reason = "no investment amount given"
    elif len(symbols) < 2:
        portfolio_reason = "a portfolio needs at least 2 valid stocks"
        error("A portfolio needs at least 2 valid stocks; the amount was ignored.")
    else:
        try:  # validate the options now, not after five minutes of analysis
            PortfolioOptimizationInput(symbols=symbols, investment_amount=amount, risk_preference=preference, **options)
        except ValidationError as exc:
            portfolio_reason = "invalid portfolio settings: " + "; ".join(e["msg"] for e in exc.errors())
            error(portfolio_reason[0].upper() + portfolio_reason[1:] + ".")
    plan["agents"]["portfolio_optimization"] = {"run": portfolio_reason is None, "reason": portfolio_reason}
    request_type = "portfolio" if portfolio_reason is None else "single_stock"
    return {"stock_symbols": symbols, "investment_amount": amount, "risk_preference": preference,
            "portfolio_options": options, "request_type": request_type, "execution_plan": plan,
            "workflow_started_at": utc_now().isoformat(), "errors": errors,
            "agent_status": {"validate_input": "completed" if symbols else "failed"}}


# ---------------------------------------------------------------- 10.1.2 / 10.1.3 routing
def route_after_validation(state: dict[str, Any]) -> str:
    return "market_research" if state.get("stock_symbols") else "report"


def route_after_market_research(state: dict[str, Any]) -> str | list[str]:
    """Nothing usable -> straight to the report (dependent agents are skipped). Otherwise the
    middle agents: one after another (sequential) or all at once (parallel fan-out)."""
    if state.get("agent_status", {}).get("market_research") not in OK_STATUSES:
        return "report"
    if (state.get("execution_plan") or {}).get("mode") == "parallel":
        return list(MIDDLE_AGENTS)
    return MIDDLE_AGENTS[0]


def route_after_output_validation(state: dict[str, Any]) -> str:
    ready = (state.get("validation") or {}).get("portfolio_ready")
    return "portfolio_optimization" if state.get("request_type") == "portfolio" and ready else "report"


# ---------------------------------------------------------------- 10.1.4 retries
def _elapsed_seconds(state: dict[str, Any]) -> float:
    started = state.get("workflow_started_at")
    if not started:
        return 0.0
    return (utc_now() - datetime.fromisoformat(started)).total_seconds()


def run_with_retry(call: Callable[[], Any], output_of: Callable[[Any], Any], *, agent: str, symbol: str | None,
                   state: dict[str, Any], settings: Settings,
                   sleep: Callable[[float], None] = time.sleep) -> tuple[Any, list[dict]]:
    """Run an agent; repeat it when it failed TEMPORARILY. Returns (result, retry events)."""
    events: list[dict] = []
    result = call()
    attempt = 1
    while True:
        out = output_of(result)
        if out.status != "failed" or not out.retryable or attempt > settings.agent_retry_attempts:
            break
        if _elapsed_seconds(state) > settings.workflow_time_budget_seconds:
            events.append({"agent": agent, "symbol": symbol, "attempt": attempt + 1, "retried": False,
                           "reason": "workflow time budget used up", "at": utc_now().isoformat()})
            break
        reason = "; ".join(out.errors[-1:]) or "temporary data-source error"
        logger.warning("Retrying %s for %s after a temporary failure: %s", agent, symbol, reason)
        events.append({"agent": agent, "symbol": symbol, "attempt": attempt + 1, "retried": True,
                       "reason": reason, "at": utc_now().isoformat()})
        sleep(settings.agent_retry_delay_seconds)
        result = call()
        attempt += 1
    output_of(result).attempts = attempt
    return result, events


# ---------------------------------------------------------------- 10.1.5 output validation
def _sanitize(value: Any, path: str, issues: list[str]) -> Any:
    """Replace NaN/inf (anywhere in a nested output) by None and record where."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        issues.append(f"{path} was not a finite number and was removed")
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v, f"{path}.{k}", issues) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v, f"{path}[{i}]", issues) for i, v in enumerate(value)]
    return value


def _rule_text(readings: dict[str, str], note: str) -> str:
    parts = [r[0].upper() + r[1:] + "." for r in readings.values() if r]
    return " ".join(parts + [note])


def _check_text(out: dict, issues: list[str], corrections: list[dict], agent: str, symbol: str) -> dict:
    """AI text that contradicts a rule-based reading is replaced by the readings themselves."""
    readings = out.get("readings") or {}
    text = out.get("explanation") or ""
    if not text or (out.get("llm") or {}).get("source") != "llm":
        return out
    conflict = contradicted_reading(text, list(readings.values()))
    if not conflict:
        return out
    issues.append(f"AI explanation {conflict}; replaced by the rule-based readings")
    note = ("The AI explanation was withheld because it contradicted a computed reading; "
            "these sentences come from NeuralVest's rules.")
    fixed = {**out, "explanation": _rule_text(readings, note),
             "llm": {**(out.get("llm") or {}), "source": "template", "replaced_by_validation": conflict},
             "warnings": [*out.get("warnings", []), f"AI explanation replaced: it {conflict}."]}
    corrections.append({"agent": agent, "symbol": symbol, "explanation": fixed["explanation"], "llm": fixed["llm"],
                        "warning": fixed["warnings"][-1]})
    return fixed


def _validate_market(out: dict, issues: list[str]) -> bool:
    ok = True
    if out.get("last_close") is None or out["last_close"] <= 0:
        issues.append("last close is missing or not positive")
        ok = False
    rsi = (out.get("indicators") or {}).get("rsi_14")
    if rsi is not None and not 0 <= rsi <= 100:
        issues.append(f"RSI {rsi} is outside 0-100")
        out["indicators"]["rsi_14"] = None
    if (out.get("trend") or {}).get("classification") not in TREND_CLASSES:
        issues.append("unknown trend classification")
    return ok


def _validate_news(out: dict, issues: list[str]) -> bool:
    breakdown = out.get("sentiment_breakdown") or {}
    if breakdown and sum(breakdown.values()) != out.get("articles_analyzed", 0):
        issues.append(f"sentiment counts add up to {sum(breakdown.values())}, not {out.get('articles_analyzed')}")
    if out.get("overall_sentiment") not in SENTIMENTS:
        issues.append("unknown overall sentiment")
    return True


def _validate_fundamentals(out: dict, issues: list[str]) -> bool:
    if out.get("overall") not in FUNDAMENTAL_OVERALL:
        issues.append("unknown overall fundamental assessment")
    return True


def _validate_risk(out: dict, issues: list[str]) -> bool:
    ok = True
    vol = out.get("annualized_volatility_pct")
    if vol is None or vol < 0:
        issues.append("annualised volatility is missing or negative")
        ok = False
    if out.get("risk_classification") not in RISK_CLASSES:
        issues.append("unknown risk classification")
    mdd = (out.get("max_drawdown") or {}).get("max_drawdown_pct")
    if mdd is not None and not -100 <= mdd <= 0:
        issues.append(f"maximum drawdown {mdd}% is outside -100..0")
        ok = False
    return ok


def validate_outputs(state: dict[str, Any]) -> dict[str, Any]:
    """Check every agent output. Returns state updates: corrected outputs, a `validation`
    summary and the stocks that may enter the portfolio."""
    report: dict[str, dict] = {}
    corrections: list[dict] = []
    updates: dict[str, Any] = {}
    checks = [("market_analysis", "market_research", _validate_market),
              ("news_analysis", "financial_news", _validate_news),
              ("stock_analysis", "stock_analysis", _validate_fundamentals)]
    valid: dict[str, dict[str, bool]] = {}
    for key, agent, check in checks:
        fixed_section = {}
        for symbol, out in (state.get(key) or {}).items():
            issues: list[str] = []
            out = _sanitize(out, f"{agent}.{symbol}", issues)
            ok = out.get("status") in OK_STATUSES and check(out, issues)
            if agent == "market_research":
                out = _check_text(out, issues, corrections, agent, symbol)
            fixed_section[symbol] = out
            valid.setdefault(symbol, {})[agent] = ok
            report.setdefault(agent, {})[symbol] = {"valid": ok, "issues": issues}
        if fixed_section:
            updates[key] = fixed_section

    risk = state.get("risk_analysis") or {}
    per_symbol = {}
    for symbol, out in (risk.get("per_symbol") or {}).items():
        issues = []
        out = _sanitize(out, f"risk_assessment.{symbol}", issues)
        ok = out.get("status") in OK_STATUSES and _validate_risk(out, issues)
        out = _check_text(out, issues, corrections, "risk_assessment", symbol)
        per_symbol[symbol] = out
        valid.setdefault(symbol, {})["risk_assessment"] = ok
        report.setdefault("risk_assessment", {})[symbol] = {"valid": ok, "issues": issues}
    if per_symbol:
        portfolio_risk = risk.get("portfolio")
        if portfolio_risk:
            portfolio_risk = _sanitize(portfolio_risk, "risk_assessment.__request__", [])
        updates["risk_analysis"] = {"per_symbol": per_symbol, "portfolio": portfolio_risk}

    # A stock may enter the portfolio only with valid prices AND a valid risk measurement.
    candidates = [s for s in state.get("stock_symbols", [])
                  if valid.get(s, {}).get("market_research") and valid.get(s, {}).get("risk_assessment")]
    excluded = {s: "its prices or risk measurement did not pass validation"
                for s in state.get("stock_symbols", []) if s not in candidates}
    issue_count = sum(len(v["issues"]) for by_symbol in report.values() for v in by_symbol.values())
    summary = {"checked_at": utc_now().isoformat(), "agents": report, "issue_count": issue_count,
               "portfolio_candidates": candidates, "excluded_from_portfolio": excluded,
               "portfolio_ready": state.get("request_type") == "portfolio" and len(candidates) >= 2,
               "text_replacements": len(corrections)}
    if state.get("request_type") == "portfolio" and len(candidates) < 2:
        summary["portfolio_skip_reason"] = (f"only {len(candidates)} stock(s) passed validation; "
                                            "a portfolio needs at least 2")
    return {**updates, "validation": summary, "_corrections": corrections}


def persist_corrections(db: Database | None, request_id: str | None, corrections: list[dict]) -> None:
    """Keep agent_results (the authoritative store) in line with the corrected text."""
    if db is None or not request_id:
        return
    for c in corrections:
        try:
            db[AGENT_RESULTS].update_one(
                {"request_id": request_id, "agent_name": c["agent"], "scope_key": c["symbol"] or REQUEST_SCOPE_KEY},
                {"$set": {"output.explanation": c["explanation"], "output.llm": c["llm"], "updated_at": utc_now()},
                 "$push": {"status_detail.warnings": c["warning"], "output.warnings": c["warning"]}})
        except PyMongoError as exc:  # the in-memory report is still corrected
            logger.error("Could not store a validation correction: %s", exc.__class__.__name__)
