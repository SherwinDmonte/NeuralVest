"""Data validation rules, tested on the synthetic fixture (no network)."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.data.data_validator import validate_ohlcv

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_prices_1y.csv"
# 2025-12-17 10:00 IST: the day after the fixture's last bar, during market hours.
NOW = datetime(2025, 12, 17, 4, 30, tzinfo=UTC)


@pytest.fixture
def prices() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, index_col="date", parse_dates=True)


def test_clean_fixture_passes_unchanged(prices):
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert report.rows_received == report.rows_valid == 250
    assert not report.missing_price_dates_removed and not report.invalid_price_dates_removed
    assert report.first_date == "2025-01-01" and report.last_date == "2025-12-16"
    assert report.business_days_since_last == 1 and not report.is_stale
    assert clean["volume"].dtype == "int64"
    pd.testing.assert_series_equal(clean["close"], prices["close"], check_names=False, check_freq=False)


def test_duplicates_and_future_dates_removed(prices):
    dup = prices.iloc[[10]].copy()
    dup["close"] = dup["high"]  # same date, different (valid) values: the last one is kept
    future = prices.iloc[[0]].copy()
    future.index = pd.DatetimeIndex([pd.Timestamp("2030-01-01")])
    clean, report = validate_ohlcv(pd.concat([prices, dup, future]), "TEST.NS", now=NOW)
    assert report.duplicates_removed == 1 and report.future_rows_removed == 1
    assert clean.loc[prices.index[10], "close"] == dup["close"].iloc[0]
    assert report.rows_valid == 250


def test_missing_prices_are_removed_never_filled(prices):
    prices.loc[prices.index[5], "close"] = np.nan
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert report.missing_price_dates_removed == [prices.index[5].strftime("%Y-%m-%d")]
    assert prices.index[5] not in clean.index  # not forward-filled
    assert any("removed" in w for w in report.warnings)


def test_missing_volume_is_zero_and_counted(prices):
    prices.loc[prices.index[3], "volume"] = np.nan
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert report.volume_missing_filled == 1 and clean.loc[prices.index[3], "volume"] == 0


@pytest.mark.parametrize(
    "column, value",
    [("close", -1.0), ("low", 1e9), ("high", 1.0), ("adjusted_close", 0.0)],
)
def test_invalid_rows_removed(prices, column, value):
    prices.loc[prices.index[7], column] = value
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert report.invalid_price_dates_removed == [prices.index[7].strftime("%Y-%m-%d")]
    assert len(clean) == 249


def test_float_noise_is_corrected_not_removed(prices):
    d = prices.index[20]
    prices.loc[d, "close"] = prices.loc[d, "high"] * (1 + 1e-9)
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert report.float_noise_corrected == 1 and d in clean.index
    assert clean.loc[d, "high"] >= clean.loc[d, "close"]


def test_outliers_flagged_not_removed(prices):
    d = prices.index[100]
    for col in ("open", "high", "low", "close", "adjusted_close"):
        prices.loc[d, col] = prices.loc[d, col] * 1.5
    clean, report = validate_ohlcv(prices, "TEST.NS", now=NOW)
    assert d in clean.index
    assert report.outliers_flagged[0].date == d.strftime("%Y-%m-%d")
    assert report.outliers_flagged[0].return_pct > 20


def test_stale_data_detected(prices):
    later = datetime(2026, 1, 15, 6, 0, tzinfo=UTC)
    _, report = validate_ohlcv(prices, "TEST.NS", now=later)
    assert report.is_stale and report.business_days_since_last > 3
    assert any("stale" in w for w in report.warnings)


def test_todays_bar_before_close_flagged_incomplete(prices):
    during_session = datetime(2025, 12, 16, 6, 0, tzinfo=UTC)  # 11:30 IST on the last bar's day
    after_close = datetime(2025, 12, 16, 11, 0, tzinfo=UTC)  # 16:30 IST
    assert validate_ohlcv(prices, "T.NS", now=during_session)[1].last_bar_may_be_incomplete is True
    assert validate_ohlcv(prices, "T.NS", now=after_close)[1].last_bar_may_be_incomplete is False


def test_timezone_aware_index_is_converted_to_ist_dates(prices):
    aware = prices.copy()
    aware.index = aware.index.tz_localize("Asia/Kolkata")
    clean, _ = validate_ohlcv(aware, "TEST.NS", now=NOW)
    assert clean.index.tz is None and clean.index[0] == pd.Timestamp("2025-01-01")


def test_missing_columns_raise(prices):
    with pytest.raises(ValueError):
        validate_ohlcv(prices.drop(columns=["adjusted_close"]), "TEST.NS", now=NOW)
