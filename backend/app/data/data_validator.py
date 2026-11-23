"""Validation and cleaning of daily price data (OHLCV).

Rules (documented so results are reproducible and explainable):
  * Prices are NEVER invented. A row with a missing price is removed and reported;
    it is not forward-filled, because a filled price would look like real data.
  * Missing volume is set to 0 and counted. Yahoo reports no volume for some index rows.
  * Duplicate dates keep the last row. Future dates are removed.
  * A row whose prices are <= 0, or whose open/close lie outside [low, high], is removed.
    Exception: differences within floating-point noise (<= 1e-6 relative) are corrected
    by widening high/low, because they are rounding artefacts, not real price errors.
  * Large daily moves (> outlier threshold) are FLAGGED, never removed: they can be real
    (results day, market crash) or a data error, and the user should see them.
  * Freshness: the data is stale if the last bar is older than N business days.
  * A bar dated today, before market close (15:30 IST), is flagged as possibly incomplete.
"""

from datetime import datetime, time, timedelta, timezone

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_IST = time(15, 30)
PRICE_COLUMNS = ["open", "high", "low", "close", "adjusted_close"]
REQUIRED_COLUMNS = [*PRICE_COLUMNS, "volume"]
FLOAT_NOISE = 1e-6


class Outlier(BaseModel):
    date: str
    return_pct: float


class ValidationReport(BaseModel):
    symbol: str
    rows_received: int
    rows_valid: int
    duplicates_removed: int = 0
    future_rows_removed: int = 0
    missing_price_dates_removed: list[str] = Field(default_factory=list)
    invalid_price_dates_removed: list[str] = Field(default_factory=list)
    float_noise_corrected: int = 0
    volume_missing_filled: int = 0
    outliers_flagged: list[Outlier] = Field(default_factory=list)
    first_date: str | None = None
    last_date: str | None = None
    business_days_since_last: int | None = None
    is_stale: bool = False
    last_bar_may_be_incomplete: bool = False
    warnings: list[str] = Field(default_factory=list)


def _to_trading_dates(index: pd.Index) -> pd.DatetimeIndex:
    """Index -> tz-naive dates representing the Indian trading day."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    return idx.normalize()


def _dates(index: pd.Index) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in index]


def validate_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    now: datetime | None = None,
    outlier_threshold_pct: float = 20.0,
    stale_after_business_days: int = 3,
    min_rows: int = 1,
) -> tuple[pd.DataFrame, ValidationReport]:
    """Return (clean DataFrame, report). Input columns: open, high, low, close, adjusted_close, volume."""
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"missing columns: {missing_cols}")

    now_ist = (now or datetime.now(timezone.utc)).astimezone(IST)
    today = pd.Timestamp(now_ist.date())
    report = ValidationReport(symbol=symbol, rows_received=len(df), rows_valid=0)

    data = df[REQUIRED_COLUMNS].copy()
    data.index = _to_trading_dates(data.index)
    # Stable sort keeps the original order of rows with the same date, so "keep last" below
    # really keeps the row that arrived last.
    data = data.sort_index(kind="stable")
    for col in REQUIRED_COLUMNS:
        data[col] = pd.to_numeric(data[col], errors="coerce").astype("float64")

    # 1. Duplicate dates (keep the most recent row for that date).
    dup = data.index.duplicated(keep="last")
    report.duplicates_removed = int(dup.sum())
    data = data[~dup]

    # 2. Future dates.
    future = data.index > today
    report.future_rows_removed = int(future.sum())
    data = data[~future]

    # 3. Missing prices: removed, never filled.
    missing = data[PRICE_COLUMNS].isna().any(axis=1)
    report.missing_price_dates_removed = _dates(data.index[missing])
    data = data[~missing]

    # 4. Missing volume -> 0 (counted).
    vol_na = data["volume"].isna()
    report.volume_missing_filled = int(vol_na.sum())
    data.loc[vol_na, "volume"] = 0.0

    # 5. Invalid prices / ordering.
    body_hi = data[["open", "close"]].max(axis=1)
    body_lo = data[["open", "close"]].min(axis=1)
    tol = body_hi.abs() * FLOAT_NOISE
    noise = ((body_hi > data["high"]) & (body_hi - data["high"] <= tol)) | (
        (body_lo < data["low"]) & (data["low"] - body_lo <= tol)
    )
    report.float_noise_corrected = int(noise.sum())
    data.loc[noise, "high"] = np.maximum(data.loc[noise, "high"], body_hi[noise])
    data.loc[noise, "low"] = np.minimum(data.loc[noise, "low"], body_lo[noise])

    invalid = (
        (data[PRICE_COLUMNS] <= 0).any(axis=1)
        | (data["volume"] < 0)
        | (data["low"] > data["high"])
        | (data[["open", "close"]].max(axis=1) > data["high"])
        | (data[["open", "close"]].min(axis=1) < data["low"])
    )
    report.invalid_price_dates_removed = _dates(data.index[invalid])
    data = data[~invalid]
    data["volume"] = data["volume"].round().astype("int64")

    # 6. Outliers: flagged only.
    returns = data["adjusted_close"].pct_change() * 100
    flagged = returns[returns.abs() > outlier_threshold_pct]
    report.outliers_flagged = [
        Outlier(date=d.strftime("%Y-%m-%d"), return_pct=round(float(r), 2)) for d, r in flagged.items()
    ]

    # 7. Summary + freshness.
    report.rows_valid = len(data)
    if report.rows_valid:
        last = data.index[-1]
        report.first_date = data.index[0].strftime("%Y-%m-%d")
        report.last_date = last.strftime("%Y-%m-%d")
        # Weekdays after the last bar up to and including today (holidays not modelled).
        report.business_days_since_last = int(
            np.busday_count((last + pd.Timedelta(days=1)).date(), (today + pd.Timedelta(days=1)).date())
        )
        report.is_stale = report.business_days_since_last > stale_after_business_days
        report.last_bar_may_be_incomplete = last == today and now_ist.time() < MARKET_CLOSE_IST

    # 8. Warnings in plain language.
    if report.rows_valid < min_rows:
        report.warnings.append(f"Only {report.rows_valid} valid rows (expected at least {min_rows}).")
    if report.missing_price_dates_removed or report.invalid_price_dates_removed:
        n = len(report.missing_price_dates_removed) + len(report.invalid_price_dates_removed)
        report.warnings.append(f"{n} row(s) removed because of missing or invalid prices.")
    if report.outliers_flagged:
        report.warnings.append(
            f"{len(report.outliers_flagged)} daily move(s) above {outlier_threshold_pct:.0f}% flagged for review."
        )
    if report.is_stale:
        report.warnings.append(
            f"Data may be stale: last bar is {report.business_days_since_last} business days old."
        )
    if report.last_bar_may_be_incomplete:
        report.warnings.append("The latest bar is from today's open session and may change until market close.")
    return data, report
