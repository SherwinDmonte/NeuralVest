"""Company financial statements (annual) from Yahoo Finance via yfinance.

What this module does NOT do: compute ratios (Phase 7, Stock Analysis Agent) or fill gaps.
Missing line items stay missing and are listed, so later phases can say "unavailable"
instead of guessing (spec §5, Agent 3).

Why not NSE/BSE filings directly? NSE's Terms of Use prohibit automated data collection
(docs/architecture.md §11). Official annual reports can be downloaded MANUALLY into
data/financial_reports/ and read with app/data/pdf_text.py.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from app.config import Settings, get_settings
from app.data.cache import FileCache
from app.data.errors import DataSourceError, NoDataError
from app.data.symbols import normalize_symbol
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.data.financials")

SOURCE = "yahoo_finance_via_yfinance"
STATEMENTS = {"income_statement": "income_stmt", "balance_sheet": "balance_sheet", "cash_flow": "cashflow"}
# Line items the Stock Analysis Agent (Phase 7) needs. Banks lack some (e.g. Operating Income).
KEY_LINE_ITEMS: dict[str, list[str]] = {
    "income_statement": ["Total Revenue", "Net Income", "Operating Income", "Diluted EPS", "Basic EPS"],
    "balance_sheet": ["Total Assets", "Stockholders Equity", "Current Assets", "Current Liabilities", "Total Debt"],
    "cash_flow": ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
}
# Indian companies mostly report for the year ending 31 March; a new annual report is
# expected within ~6 months, so data older than 18 months is flagged as stale.
STALE_AFTER = timedelta(days=548)


@dataclass
class FinancialStatements:
    symbol: str
    statements: dict[str, dict[str, dict[str, float | None]]]  # statement -> period -> item -> value
    latest_period: dict[str, str | None]
    missing_key_items: dict[str, list[str]]
    is_stale: bool
    fetched_at: datetime
    from_cache: bool
    source: str = SOURCE
    warnings: list[str] = field(default_factory=list)


def _clean_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) or math.isinf(number) else number


def statement_to_periods(df: pd.DataFrame | None) -> dict[str, dict[str, float | None]]:
    """yfinance statement (rows = line items, columns = period end dates) -> plain dict.

    Periods where every value is missing are dropped (Yahoo often returns an empty oldest year).
    """
    if df is None or df.empty:
        return {}
    periods: dict[str, dict[str, float | None]] = {}
    for column in df.columns:
        values = {str(item): _clean_number(v) for item, v in df[column].items()}
        if any(v is not None for v in values.values()):
            period = pd.Timestamp(column).date().isoformat()
            periods[period] = values
    return dict(sorted(periods.items(), reverse=True))  # newest first


def summarize(statements: dict[str, dict[str, dict]], today: date) -> tuple[dict, dict, bool, list[str]]:
    latest: dict[str, str | None] = {}
    missing: dict[str, list[str]] = {}
    warnings: list[str] = []
    for name, periods in statements.items():
        latest[name] = next(iter(periods), None)
        newest = periods.get(latest[name], {}) if latest[name] else {}
        missing[name] = [item for item in KEY_LINE_ITEMS[name] if newest.get(item) is None]
        if not periods:
            warnings.append(f"No {name.replace('_', ' ')} data available.")
        elif missing[name]:
            warnings.append(f"{name.replace('_', ' ').capitalize()} {latest[name]}: missing {', '.join(missing[name])}.")
    dates = [date.fromisoformat(p) for p in latest.values() if p]
    is_stale = bool(dates) and today - max(dates) > STALE_AFTER
    if is_stale:
        warnings.append(f"Latest annual statements ({max(dates).isoformat()}) are more than 18 months old.")
    return latest, missing, is_stale, warnings


def get_financial_statements(
    symbol: str, use_cache: bool = True, settings: Settings | None = None
) -> FinancialStatements:
    settings = settings or get_settings()
    symbol = normalize_symbol(symbol)
    cache = FileCache(settings.data_cache_dir)
    hit = cache.read("financials", symbol, timedelta(days=settings.fundamentals_cache_days)) if use_cache else None
    if hit:
        statements, fetched_at, from_cache = hit[0], hit[1], True
    else:
        try:
            ticker = yf.Ticker(symbol)
            statements = {name: statement_to_periods(getattr(ticker, attr)) for name, attr in STATEMENTS.items()}
        except Exception as exc:
            raise DataSourceError(f"Yahoo Finance statements unavailable for {symbol}: {exc.__class__.__name__}") from exc
        if not any(statements.values()):
            raise NoDataError(f"No financial statements available for {symbol}.")
        fetched_at, from_cache = cache.write("financials", symbol, statements), False

    latest, missing, is_stale, warnings = summarize(statements, utc_now().date())
    return FinancialStatements(symbol=symbol, statements=statements, latest_period=latest,
                               missing_key_items=missing, is_stale=is_stale, fetched_at=fetched_at,
                               from_cache=from_cache, warnings=warnings)
