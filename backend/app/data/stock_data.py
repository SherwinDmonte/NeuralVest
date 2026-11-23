"""Historical market data from Yahoo Finance (via yfinance), validated, cached and stored.

Source: Yahoo Finance through the unofficial yfinance library. Data can be delayed or
revised and is for personal/educational use (docs/architecture.md §11). Every result
carries its source and fetch time.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf
from pymongo.database import Database

from app.config import Settings, get_settings
from app.data.cache import FileCache
from app.data.data_validator import REQUIRED_COLUMNS, ValidationReport, validate_ohlcv
from app.data.errors import DataSourceError, NoDataError
from app.data.symbols import exchange_of, normalize_symbol
from app.database.models import MarketDataDocument
from app.database.repository import bulk_upsert

logger = logging.getLogger("neuralvest.data.prices")
# yfinance prints its own errors for unknown symbols; we report them ourselves.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

SOURCE = "yahoo_finance_via_yfinance"
ALLOWED_PERIODS = ("1mo", "3mo", "6mo", "1y", "2y", "5y")
_COLUMN_MAP = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
               "Adj Close": "adjusted_close", "Volume": "volume"}
_RETRY_WAITS = (2, 5)  # seconds; Yahoo rate limits are not documented


@dataclass
class PriceHistory:
    symbol: str
    period: str
    frame: pd.DataFrame  # index: trading date (tz-naive), columns: REQUIRED_COLUMNS
    report: ValidationReport
    fetched_at: datetime
    from_cache: bool
    source: str = SOURCE
    warnings: list[str] = field(default_factory=list)

    def to_records(self) -> list[dict[str, Any]]:
        return [{"date": d.strftime("%Y-%m-%d"), **{c: row[c] for c in REQUIRED_COLUMNS}}
                for d, row in self.frame.iterrows()]

    def provenance(self) -> dict[str, Any]:
        return {"source": self.source, "fetched_at": self.fetched_at.isoformat(),
                "data_as_of": self.report.last_date, "from_cache": self.from_cache}


def _download(symbol: str, period: str) -> pd.DataFrame:
    """Raw download with retries. Returns renamed columns; raises NoDataError if empty."""
    last_exc: Exception | None = None
    for attempt, wait in enumerate((0, *_RETRY_WAITS)):
        if wait:
            time.sleep(wait)
        try:
            raw = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False, actions=False)
        except yf.exceptions.YFRateLimitError as exc:
            last_exc = exc
            logger.warning("Yahoo rate limit for %s (attempt %d)", symbol, attempt + 1)
            continue
        except Exception as exc:  # network errors, format changes
            last_exc = exc
            logger.warning("Yahoo download failed for %s: %s", symbol, exc.__class__.__name__)
            continue
        if raw is None or raw.empty:
            raise NoDataError(f"No price data for {symbol}. The symbol may be invalid or delisted.")
        missing = [c for c in _COLUMN_MAP if c not in raw.columns]
        if missing:
            raise DataSourceError(f"Unexpected Yahoo response for {symbol}: missing columns {missing}")
        return raw.rename(columns=_COLUMN_MAP)[REQUIRED_COLUMNS]
    raise DataSourceError(f"Yahoo Finance unavailable for {symbol}: {last_exc.__class__.__name__}")


def _frame_from_records(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(records)
    frame.index = pd.to_datetime(frame.pop("date"))
    return frame


def get_price_history(
    symbol: str,
    period: str = "1y",
    use_cache: bool = True,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> PriceHistory:
    """Daily OHLCV for one symbol, validated. Uses the file cache when it is fresh."""
    settings = settings or get_settings()
    symbol = normalize_symbol(symbol)
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period must be one of {ALLOWED_PERIODS}")

    cache = FileCache(settings.data_cache_dir)
    cached = cache.read("prices", f"{symbol}_{period}", timedelta(hours=settings.price_cache_hours)) if use_cache else None
    if cached:
        raw, fetched_at = _frame_from_records(cached[0]), cached[1]
        from_cache = True
    else:
        raw = _download(symbol, period)
        records = [{"date": d.strftime("%Y-%m-%d %H:%M:%S%z"), **{c: (None if pd.isna(v) else float(v))
                    for c, v in row.items()}} for d, row in raw.iterrows()]
        fetched_at = cache.write("prices", f"{symbol}_{period}", records)
        raw = _frame_from_records(records)
        from_cache = False

    # Validation always runs (also on cached data) because freshness depends on "now".
    frame, report = validate_ohlcv(raw, symbol, now=now, min_rows=20)
    if report.rows_valid == 0:
        raise NoDataError(f"No valid price rows for {symbol} after validation.")
    return PriceHistory(symbol=symbol, period=period, frame=frame, report=report,
                        fetched_at=fetched_at, from_cache=from_cache, warnings=list(report.warnings))


def get_benchmark_history(period: str = "1y", **kwargs) -> PriceHistory:
    """NIFTY 50 (^NSEI), used for benchmark comparison and beta."""
    return get_price_history("^NSEI", period=period, **kwargs)


def store_price_history(db: Database, history: PriceHistory) -> dict[str, int]:
    """Upsert validated bars into market_data (unique per symbol + trading date)."""
    docs = [
        MarketDataDocument(
            symbol=history.symbol,
            date=datetime(d.year, d.month, d.day, tzinfo=UTC),  # trading date at 00:00 UTC
            open=row["open"], high=row["high"], low=row["low"], close=row["close"],
            adjusted_close=row["adjusted_close"], volume=int(row["volume"]),
            source=history.source, fetched_at=history.fetched_at,
        )
        for d, row in history.frame.iterrows()
    ]
    return bulk_upsert(db, docs, ["symbol", "date"])


def get_company_profile(symbol: str, use_cache: bool = True, settings: Settings | None = None) -> dict[str, Any]:
    """Company name, sector, industry and currency from Yahoo Finance."""
    settings = settings or get_settings()
    symbol = normalize_symbol(symbol)
    cache = FileCache(settings.data_cache_dir)
    max_age = timedelta(days=settings.fundamentals_cache_days)
    if use_cache and (hit := cache.read("profile", symbol, max_age)):
        return {**hit[0], "fetched_at": hit[1].isoformat(), "from_cache": True}

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        raise DataSourceError(f"Yahoo Finance profile unavailable for {symbol}: {exc.__class__.__name__}") from exc
    name = info.get("longName") or info.get("shortName")
    if not name:
        raise NoDataError(f"No company profile for {symbol}.")
    profile = {
        "symbol": symbol,
        "company_name": name,
        "short_name": info.get("shortName"),
        "exchange": exchange_of(symbol),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "source": SOURCE,
    }
    fetched_at = cache.write("profile", symbol, profile)
    return {**profile, "fetched_at": fetched_at.isoformat(), "from_cache": False}
