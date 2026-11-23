"""Agent 1: Market Research.

Responsibility: understand how a stock's price has behaved. Python fetches and validates
the prices, computes the indicators, classifies the trend and compares the stock with
NIFTY 50. The LLM only explains those computed facts in plain language.
"""

import logging
import time
from datetime import datetime

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.agents.common import LLMClient, save_agent_result
from app.analysis import technical_indicators as ti
from app.config import Settings, get_settings
from app.data.errors import DataError, InvalidSymbolError
from app.data.stock_data import PriceHistory, get_benchmark_history, get_company_profile, get_price_history, store_price_history
from app.data.symbols import BENCHMARK_SYMBOL, normalize_symbol
from app.llm import prompts as p
from app.schemas.agents import DataSource, MarketResearchOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.market_research")
AGENT_NAME = "market_research"


def build_facts(out: MarketResearchOutput) -> dict:
    """The ONLY information the LLM receives: values computed above, nothing else."""
    ind = out.indicators
    bench = out.benchmark_comparison or {}
    return {
        "symbol": out.symbol, "company": out.company_name, "as_of": out.last_close_date,
        "last_close": out.last_close, "period_return_pct": out.period_return_pct,
        "trend": out.trend.get("classification"), "trend_rule": (out.trend.get("rules_triggered") or [None])[0],
        "sma_20": ind.get("sma_20"), "sma_50": ind.get("sma_50"), "sma_200": ind.get("sma_200"),
        "rsi_14": ind.get("rsi_14"), "rsi_zone": out.rsi_zone,
        "macd": (ind.get("macd") or {}).get("macd"), "macd_signal": (ind.get("macd") or {}).get("signal"),
        "macd_histogram": (ind.get("macd") or {}).get("histogram"),
        "benchmark": "NIFTY 50" if bench.get("available") else None,
        "benchmark_return_pct": bench.get("benchmark_return_pct"), "relative_to_benchmark_pct": bench.get("relative_pct"),
        "volume_vs_20d_avg": out.volume.get("last_vs_avg_ratio"),
        # Indicator settings, so the model may mention "20-day SMA" or "14-day RSI".
        "indicator_settings": "SMA 20/50/200 days, EMA 12/26, RSI 14 days, MACD 12/26/9, Bollinger 20 days 2 std",
    }


def run_market_research(
    symbol: str,
    *,
    llm: LLMClient | None = None,
    db: Database | None = None,
    request_id: str | None = None,
    period: str = "1y",
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[MarketResearchOutput, PriceHistory | None]:
    """Returns (output, price history). The history is shared with later agents via the
    workflow state, so prices are fetched only once per analysis."""
    settings = settings or get_settings()
    started = time.perf_counter()
    out = MarketResearchOutput(symbol=str(symbol), status="failed", generated_at=utc_now())

    # 1. Symbol
    try:
        out.symbol = normalize_symbol(symbol)
    except InvalidSymbolError as exc:
        out.errors.append(str(exc))
        out.execution_seconds = time.perf_counter() - started
        return out, None

    # 2. Company profile (optional: the analysis continues without it)
    try:
        profile = get_company_profile(out.symbol, settings=settings)
        out.company_name = profile["company_name"]
        out.data_sources.append(DataSource(source=profile["source"], detail="company profile",
                                           fetched_at=profile.get("fetched_at")))
    except DataError as exc:
        out.warnings.append(f"Company profile unavailable: {exc}")

    # 3. Prices (required)
    try:
        history = get_price_history(out.symbol, period=period, settings=settings, now=now)
    except DataError as exc:
        out.errors.append(str(exc))
        out.execution_seconds = time.perf_counter() - started
        _persist(db, request_id, out, period)
        return out, None
    out.data_sources.append(DataSource(source=history.source, detail=f"daily prices ({period})",
                                       fetched_at=history.fetched_at, data_as_of=history.report.last_date))
    out.validation = history.report.model_dump()
    out.warnings.extend(history.report.warnings)

    # 4. Indicators, trend, volume
    ind = ti.compute_indicators(history.frame)
    last = ind.iloc[-1]
    out.last_close = round(float(last["close"]), 2)
    out.last_close_date = history.report.last_date
    out.last_bar_may_be_incomplete = history.report.last_bar_may_be_incomplete
    out.period_return_pct = ti.period_return_pct(history.frame["adjusted_close"])
    out.indicators = ti.latest_snapshot(ind)
    out.rsi_zone = ti.rsi_zone(out.indicators["rsi_14"])
    out.trend = ti.classify_trend(ind)
    out.volume = ti.volume_analysis(history.frame)
    if out.trend["classification"] == "insufficient_data":
        out.warnings.append("Not enough price history to classify the trend.")
    elif out.trend["basis"] == "short_history":
        out.warnings.append("Less than 200 trading days: trend uses SMA20/SMA50 instead of SMA50/SMA200.")
    if warning := ti.corporate_action_warning(history.frame):
        out.warnings.append(warning)

    # 5. Benchmark comparison (optional)
    bench_history = None
    try:
        bench_history = get_benchmark_history(period=period, settings=settings, now=now)
        out.benchmark_comparison = ti.benchmark_comparison(history.frame, bench_history.frame, BENCHMARK_SYMBOL)
        out.data_sources.append(DataSource(source=bench_history.source, detail="NIFTY 50 benchmark",
                                           fetched_at=bench_history.fetched_at,
                                           data_as_of=bench_history.report.last_date))
    except DataError as exc:
        out.warnings.append(f"Benchmark comparison unavailable: {exc}")

    # 6. Plain-language explanation (LLM explains facts; template if the LLM is unavailable)
    facts = build_facts(out)
    if llm is not None:
        result = llm.generate_structured(p.market_explanation_prompt(facts), p.MarketExplanationOutput,
                                         p.market_explanation_fallback(facts))
        out.explanation = result.value.explanation
        out.llm = result.metadata()
    else:
        out.explanation = p.market_explanation_fallback(facts)().explanation
        out.llm = {"source": "template", "model": None, "used_fallback": True}

    partial = out.company_name is None or bench_history is None or out.trend["classification"] == "insufficient_data"
    out.status = "partial" if partial else "completed"
    out.execution_seconds = time.perf_counter() - started

    # 7. Persistence (never fails the agent)
    if db is not None:
        try:
            store_price_history(db, history)
            if bench_history is not None:
                store_price_history(db, bench_history)
        except PyMongoError as exc:
            out.warnings.append(f"Prices could not be saved to the database ({exc.__class__.__name__}).")
    _persist(db, request_id, out, period)
    return out, history


def _persist(db, request_id, out: MarketResearchOutput, period: str) -> None:
    if warning := save_agent_result(db, request_id, out, {"symbol": out.symbol, "period": period}):
        out.warnings.append(warning)
