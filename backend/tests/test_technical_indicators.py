"""Indicators checked against INDEPENDENT reference implementations written here with plain
Python loops (task 5.1.9), plus hand-computed textbook values."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analysis import technical_indicators as ti
from tests.reference_indicators import ref_ema, ref_macd, ref_rsi, ref_sma

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_prices_1y.csv"


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, index_col="date", parse_dates=True)


def assert_close(series: pd.Series, reference: list, tol=1e-9):
    for got, want in zip(series.tolist(), reference, strict=True):
        if want is None:
            assert np.isnan(got)
        else:
            assert got == pytest.approx(want, rel=tol, abs=tol)


# ---------------------------------------------------------------- tests
def test_sma_matches_reference(frame):
    closes = frame["close"].tolist()
    for n in (20, 50, 200):
        assert_close(ti.sma(frame["close"], n), ref_sma(closes, n))


def test_ema_matches_reference(frame):
    for span in (12, 26):
        assert_close(ti.ema(frame["close"], span), ref_ema(frame["close"].tolist(), span))


def test_rsi_matches_reference(frame):
    assert_close(ti.rsi(frame["close"], 14), ref_rsi(frame["close"].tolist(), 14), tol=1e-9)


def test_rsi_hand_computed_example():
    # The 14 price changes below contain gains summing to 3.34 and losses summing to 1.40, so
    # the first RSI = 100 - 100 / (1 + 3.34 / 1.40) = 70.464 (computed by hand, no rounding).
    # Textbooks that round the averages first (0.24 / 0.10) print about 70.5.
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61,
              46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    values = ti.rsi(pd.Series(closes), 14)
    assert values.iloc[14] == pytest.approx(100 - 100 / (1 + 3.34 / 1.40), abs=1e-9)
    assert values.iloc[14] == pytest.approx(70.464, abs=0.001)
    assert values.iloc[:14].isna().all()


def test_rsi_edge_cases():
    assert ti.rsi(pd.Series([10.0] * 20)).iloc[-1] == 50.0  # flat
    assert ti.rsi(pd.Series(np.arange(1.0, 21.0))).iloc[-1] == 100.0  # only gains
    assert ti.rsi(pd.Series([1.0, 2.0])).isna().all()  # too short


def test_macd_matches_reference(frame):
    line, signal = ref_macd(frame["close"].tolist())
    m = ti.macd(frame["close"])
    assert_close(m["macd"], line)
    assert_close(m["macd_signal"], signal)


def test_macd_relationships(frame):
    m = ti.macd(frame["close"])
    ema12 = pd.Series(ref_ema(frame["close"].tolist(), 12), dtype="float64")
    ema26 = pd.Series(ref_ema(frame["close"].tolist(), 26), dtype="float64")
    assert m["macd"].iloc[-1] == pytest.approx((ema12 - ema26).iloc[-1], rel=1e-9)
    assert (m["macd_histogram"] - (m["macd"] - m["macd_signal"])).dropna().abs().max() < 1e-12


def test_bollinger_uses_population_std(frame):
    bb = ti.bollinger(frame["close"])
    window = frame["close"].iloc[-20:].to_numpy()
    assert bb["bb_middle"].iloc[-1] == pytest.approx(window.mean())
    assert bb["bb_upper"].iloc[-1] == pytest.approx(window.mean() + 2 * window.std(ddof=0))


def test_snapshot_has_none_for_missing_history(frame):
    snap = ti.latest_snapshot(ti.compute_indicators(frame.iloc[:60]))
    assert snap["sma_200"] is None and snap["sma_50"] is not None and snap["rsi_14"] is not None


def _trend_frame(close, fast, slow):
    return pd.DataFrame({"close": [close], "sma_20": [fast], "sma_50": [fast], "sma_200": [slow]})


@pytest.mark.parametrize(
    "close, sma50, sma200, expected",
    [(110, 105, 100, "bullish"), (90, 95, 100, "bearish"), (100, 105, 95, "sideways")],
)
def test_trend_rules(close, sma50, sma200, expected):
    result = ti.classify_trend(_trend_frame(close, sma50, sma200))
    assert result["classification"] == expected and result["basis"] == "long_term"


def test_trend_short_history_and_insufficient(frame):
    ind = ti.compute_indicators(frame.iloc[:120])
    assert ti.classify_trend(ind)["basis"] == "short_history"
    assert ti.classify_trend(ti.compute_indicators(frame.iloc[:30]))["classification"] == "insufficient_data"


def test_rsi_zone():
    assert [ti.rsi_zone(v) for v in (75, 50, 25, None)] == ["overbought", "neutral", "oversold", None]


def test_volume_analysis_detects_spike(frame):
    frame.loc[frame.index[-1], "volume"] = int(frame["volume"].iloc[-21:-1].mean() * 5)
    va = ti.volume_analysis(frame)
    assert frame.index[-1].strftime("%Y-%m-%d") in va["spike_days_last_20"] and va["last_vs_avg_ratio"] > 2


def test_benchmark_comparison_uses_common_dates():
    idx = pd.bdate_range("2026-01-01", periods=5)
    stock = pd.DataFrame({"adjusted_close": [100, 101, 102, 103, 110.0]}, index=idx)
    bench = pd.DataFrame({"adjusted_close": [200, 202, 204, 206.0]}, index=idx[:4])  # missing last day
    result = ti.benchmark_comparison(stock, bench, "^NSEI")
    assert result["trading_days"] == 4 and result["stock_return_pct"] == 3.0
    assert result["benchmark_return_pct"] == 3.0 and result["relative_pct"] == 0.0


def test_corporate_action_detection(frame):
    assert ti.corporate_action_warning(frame) is None
    split = frame.copy()
    split.loc[split.index[100:], "adjusted_close"] = split.loc[split.index[100:], "close"] / 2
    assert "split" in ti.corporate_action_warning(split)
