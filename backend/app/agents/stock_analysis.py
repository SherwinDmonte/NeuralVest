"""Agent 3: Stock Analysis (fundamentals).

Responsibility: judge a company's financial health from its annual statements. Python
computes every ratio (app/analysis/fundamentals.py) and applies fixed, documented rules for
the assessments. The LLM only explains those results in plain language.
"""

import logging
import time

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.agents.common import LLMClient, save_agent_result
from app.analysis import fundamentals as fa
from app.config import Settings, get_settings
from app.data.errors import DataError, DataSourceError, InvalidSymbolError
from app.data.financial_data import FinancialStatements, get_financial_statements
from app.data.stock_data import get_company_profile
from app.data.symbols import exchange_of, normalize_symbol
from app.database.models import STOCKS, StockDocument
from app.database.repository import upsert_document
from app.llm import prompts as p
from app.schemas.agents import DataSource, StockAnalysisOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.stock_analysis")
AGENT_NAME = "stock_analysis"

# Headline metrics passed to the LLM (the full set is stored and shown).
FACT_METRICS = ["revenue_growth_yoy_pct", "revenue_cagr_pct", "net_profit_growth_yoy_pct", "eps", "pe", "pb",
                "roe_pct", "roa_pct", "debt_to_equity", "current_ratio", "operating_margin_pct", "net_margin_pct"]


def is_bank(profile: dict) -> bool:
    industry = (profile.get("industry") or "").lower()
    return "bank" in industry


def build_facts(out: StockAnalysisOutput) -> dict:
    # For banks, debt-to-equity is not comparable and not assessed; leaving it out stops a
    # small model from calling it "low" or "high" (seen in the Phase 7 live run).
    skip = {"debt_to_equity"} if out.is_bank else set()
    metrics = {k: (out.metrics[k]["value"] if out.metrics[k]["value"] is not None
                   else f"unavailable: {out.metrics[k]['reason']}")
               for k in FACT_METRICS if k in out.metrics and k not in skip}
    caveats = {k: out.metrics[k]["reason"] for k in FACT_METRICS
               if k in out.metrics and k not in skip and out.metrics[k]["value"] is not None and out.metrics[k]["reason"]}
    return {
        "company": out.company_name, "symbol": out.symbol, "sector": out.sector, "is_bank": out.is_bank,
        "period": out.statement_periods.get("income_statement"), "price_used": out.price_used,
        "metrics": metrics, "metric_caveats": caveats, "assessments": out.assessments, "overall": out.overall,
        "strengths": out.strengths, "weaknesses": out.weaknesses,
    }


def run_stock_analysis(
    symbol: str,
    *,
    last_close: float | None = None,
    price_date: str | None = None,
    llm: LLMClient | None = None,
    db: Database | None = None,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> tuple[StockAnalysisOutput, FinancialStatements | None]:
    settings = settings or get_settings()
    started = time.perf_counter()
    out = StockAnalysisOutput(symbol=str(symbol), status="failed", generated_at=utc_now(),
                              price_used=last_close, price_date=price_date)

    try:
        out.symbol = normalize_symbol(symbol)
    except InvalidSymbolError as exc:
        out.errors.append(str(exc))
        return _done(out, started), None
    if exchange_of(out.symbol) == "INDEX":
        out.status = "skipped"
        out.warnings.append("Indices have no financial statements; fundamental analysis does not apply.")
        return _done(out, started), None

    # 1. Company profile (sector/industry decide bank handling; currency check for P/E and P/B)
    profile: dict = {}
    try:
        profile = get_company_profile(out.symbol, settings=settings)
        out.company_name, out.sector, out.industry = profile.get("company_name"), profile.get("sector"), profile.get("industry")
    except DataError as exc:
        out.warnings.append(f"Company profile unavailable: {exc}")
    out.is_bank = is_bank(profile)
    fin_ccy, px_ccy = profile.get("financial_currency"), profile.get("currency")
    currencies_match = None if not (fin_ccy and px_ccy) else fin_ccy == px_ccy
    if currencies_match is None:
        out.warnings.append("Statement currency could not be verified against the price currency.")

    # 2. Statements (required)
    try:
        fs = get_financial_statements(out.symbol, settings=settings)
    except DataError as exc:
        out.errors.append(str(exc))
        out.retryable = isinstance(exc, DataSourceError)
        _persist(db, request_id, out)
        return _done(out, started), None
    out.statement_periods = fs.latest_period
    out.statements_stale = fs.is_stale
    out.warnings.extend(fs.warnings)
    out.data_sources.append(DataSource(source=fs.source, detail="annual financial statements",
                                       fetched_at=fs.fetched_at, data_as_of=fs.latest_period.get("income_statement")))
    if last_close is None:
        out.warnings.append("No price from the Market Research Agent: P/E and P/B cannot be computed.")

    # 3. Ratios, rule-based assessments, strengths and weaknesses
    metrics = fa.compute_fundamentals(fs.statements, last_close, is_bank=out.is_bank,
                                      currencies_match=currencies_match)
    out.metrics = {k: m.as_dict() for k, m in metrics.items()}
    out.unavailable = [k for k, m in metrics.items() if m.value is None]
    out.assessments = fa.assess(metrics, out.is_bank)
    out.assessment_rules = fa.THRESHOLDS
    out.overall = fa.overall(out.assessments)
    out.strengths, out.weaknesses = fa.strengths_and_weaknesses(metrics, out.assessments)
    if out.is_bank:
        out.warnings.append("Bank: current ratio, operating margin and debt-to-equity are not assessed "
                            "(banks report differently from other companies).")

    # 4. Plain-language explanation
    facts = build_facts(out)
    if llm is not None:
        result = llm.generate_structured(p.stock_analysis_prompt(facts), p.FundamentalExplanationOutput,
                                         p.stock_analysis_fallback(facts))
        out.explanation, out.llm = result.value.explanation, result.metadata()
    else:
        out.explanation = p.stock_analysis_fallback(facts)().explanation
        out.llm = {"source": "template", "model": None, "used_fallback": True}

    core_missing = [k for k in ("roe_pct", "net_margin_pct", "revenue_growth_yoy_pct") if k in out.unavailable]
    out.status = "partial" if (core_missing or fs.is_stale or not profile) else "completed"
    _persist(db, request_id, out)
    _save_snapshot(db, out, profile)
    return _done(out, started), fs


def _done(out: StockAnalysisOutput, started: float) -> StockAnalysisOutput:
    out.execution_seconds = time.perf_counter() - started
    return out


def _persist(db: Database | None, request_id: str | None, out: StockAnalysisOutput) -> None:
    if warning := save_agent_result(db, request_id, out, {"symbol": out.symbol, "last_close": out.price_used}):
        out.warnings.append(warning)


def _save_snapshot(db: Database | None, out: StockAnalysisOutput, profile: dict) -> None:
    """Latest fundamentals snapshot per company in `stocks` (agent_results keeps the per-request version)."""
    if db is None or not out.company_name:
        return
    try:
        existing = db[STOCKS].find_one({"symbol": out.symbol}) or {}
        info = dict(existing.get("company_information") or {})
        info["fundamentals"] = {
            "statement_periods": out.statement_periods, "metrics": {k: v["value"] for k, v in out.metrics.items()},
            "assessments": out.assessments, "overall": out.overall, "price_used": out.price_used,
            "computed_at": out.generated_at.isoformat(), "source": "yahoo_finance_via_yfinance",
        }
        doc = StockDocument(symbol=out.symbol, company_name=out.company_name, exchange=exchange_of(out.symbol),
                            sector=out.sector, industry=out.industry, company_information=info)
        upsert_document(db, doc, ["symbol"])
    except (PyMongoError, ValueError) as exc:
        out.warnings.append(f"Fundamentals snapshot could not be saved ({exc.__class__.__name__}).")
