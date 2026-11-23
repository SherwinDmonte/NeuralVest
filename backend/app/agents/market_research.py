"""Agent 1: Market Research.

Responsibility: understand how a stock's price has behaved. Python fetches and validates
the prices, computes the indicators, classifies the trend and compares the stock with
NIFTY 50. The LLM only explains those computed facts in plain language.
"""

import logging
import time
from datetime import datetime

import pandas as pd
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.agents.common import LLMClient, save_agent_result
from app.analysis import technical_indicators as ti
from app.config import Settings, get_settings
from app.data.errors import DataError, DataSourceError, InvalidSymbolError
from app.data.stock_data import PriceHistory, get_benchmark_history, get_company_profile, get_price_history, store_price_history
from app.data.symbols import BENCHMARK_SYMBOL, normalize_symbol
from app.llm import prompts as p
from app.schemas.agents import DataSource, MarketResearchOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.market_research")
AGENT_NAME = "market_research"
# Indicators are computed on a longer history than the analysis window: SMA200 needs 200
# days, and recursive indicators (EMA, RSI, MACD) need warm-up to converge. The same
# lookback is used by the chart endpoint, so dashboard tiles and charts always agree.
INDICATOR_LOOKBACK = "2y"
WINDOW_DAYS = {"6mo": 183, "1y": 366, "2y": 731, "5y": 1827}


def analysis_window(frame, period: str):
    """Rows of the analysis window (e.g. the last year) for returns, benchmark and volume."""
    cutoff = frame.index[-1] - pd.Timedelta(days=WINDOW_DAYS[period])
    return frame[frame.index > cutoff]


def interpret(out: MarketResearchOutput) -> dict[str, str]:
    """Plain-language readings computed by Python. A small model misreads raw numbers
    (e.g. "MACD signal is positive" when MACD is below its signal), so it is given the
    correct reading and only has to put it into words."""
    ind, bench, readings = out.indicators, out.benchmark_comparison or {}, {}
    macd = ind.get("macd") or {}
    if macd.get("histogram") is not None:
        readings["macd_reading"] = ("MACD is above its signal line (momentum strengthening)"
                                    if macd["histogram"] > 0 else
                                    "MACD is below its signal line (momentum weakening)")
    if ind.get("sma_200") is not None and out.last_close is not None:
        readings["long_term_reading"] = ("the price is above its 200-day average" if out.last_close > ind["sma_200"]
                                         else "the price is below its 200-day average")
    if bench.get("available") and bench.get("outperformed") is not None:
        # The figures live INSIDE the sentence: given loose benchmark fields, the 0.6B model once
        # wrote "the benchmark underperformed the NIFTY 50" (Phase 9 review).
        figures = ""
        if bench.get("stock_return_pct") is not None and bench.get("benchmark_return_pct") is not None:
            figures = (f" ({bench['stock_return_pct']}% for the stock vs {bench['benchmark_return_pct']}% "
                       f"for the NIFTY 50)")
        readings["benchmark_reading"] = (("the stock outperformed the NIFTY 50 over the period" if bench["outperformed"]
                                          else "the stock underperformed the NIFTY 50 over the period") + figures)
    if out.rsi_zone:
        readings["rsi_reading"] = {"overbought": "RSI is in the overbought zone (above 70)",
                                   "oversold": "RSI is in the oversold zone (below 30)",
                                   "neutral": "RSI is in the neutral zone (between 30 and 70)"}[out.rsi_zone]
    return readings


def build_facts(out: MarketResearchOutput) -> dict:
    """The ONLY information the LLM receives: values computed above, nothing else."""
    ind = out.indicators
    return {
        **interpret(out),
        "symbol": out.symbol, "company": out.company_name, "as_of": out.last_close_date,
        "last_close": out.last_close, "period_return_pct": out.period_return_pct,
        "trend": out.trend.get("classification"), "trend_rule": (out.trend.get("rules_triggered") or [None])[0],
        "sma_20": ind.get("sma_20"), "sma_50": ind.get("sma_50"), "sma_200": ind.get("sma_200"),
        "rsi_14": ind.get("rsi_14"), "rsi_zone": out.rsi_zone,
        "macd": (ind.get("macd") or {}).get("macd"), "macd_signal": (ind.get("macd") or {}).get("signal"),
        "macd_histogram": (ind.get("macd") or {}).get("histogram"),
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

    # 3. Prices (required): the longer of the analysis window and the indicator lookback
    lookback = period if WINDOW_DAYS[period] >= WINDOW_DAYS[INDICATOR_LOOKBACK] else INDICATOR_LOOKBACK
    try:
        history = get_price_history(out.symbol, period=lookback, settings=settings, now=now)
    except DataError as exc:
        out.errors.append(str(exc))
        out.retryable = isinstance(exc, DataSourceError)
        out.execution_seconds = time.perf_counter() - started
        _persist(db, request_id, out, period)
        return out, None
    out.data_sources.append(DataSource(source=history.source, detail=f"daily prices ({lookback})",
                                       fetched_at=history.fetched_at, data_as_of=history.report.last_date))
    out.validation = history.report.model_dump()
    out.warnings.extend(history.report.warnings)
    window = analysis_window(history.frame, period)

    # 4. Indicators (full lookback), trend; return and volume over the analysis window
    ind = ti.compute_indicators(history.frame)
    last = ind.iloc[-1]
    out.last_close = round(float(last["close"]), 2)
    out.last_close_date = history.report.last_date
    out.last_bar_may_be_incomplete = history.report.last_bar_may_be_incomplete
    out.period_return_pct = ti.period_return_pct(window["adjusted_close"])
    out.indicators = ti.latest_snapshot(ind)
    out.rsi_zone = ti.rsi_zone(out.indicators["rsi_14"])
    out.trend = ti.classify_trend(ind)
    out.volume = ti.volume_analysis(window)
    if out.trend["classification"] == "insufficient_data":
        out.warnings.append("Not enough price history to classify the trend.")
    elif out.trend["basis"] == "short_history":
        out.warnings.append("Less than 200 trading days: trend uses SMA20/SMA50 instead of SMA50/SMA200.")
    if warning := ti.corporate_action_warning(history.frame):
        out.warnings.append(warning)

    # 5. Benchmark comparison (optional)
    bench_history = None
    try:
        bench_history = get_benchmark_history(period=lookback, settings=settings, now=now)
        out.benchmark_comparison = ti.benchmark_comparison(window, bench_history.frame, BENCHMARK_SYMBOL)
        out.data_sources.append(DataSource(source=bench_history.source, detail="NIFTY 50 benchmark",
                                           fetched_at=bench_history.fetched_at,
                                           data_as_of=bench_history.report.last_date))
    except DataError as exc:
        out.warnings.append(f"Benchmark comparison unavailable: {exc}")

    # 6. Rule-based readings (always shown) + plain-language explanation by the LLM
    out.readings = interpret(out)
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
