"""Technical indicators, computed in Python (never by the LLM). Decision D3: no pandas-ta.

Conventions (documented because different charting sites use slightly different ones):
  * SMA: simple rolling mean; NaN until a full window is available.
  * EMA: pandas `ewm(span, adjust=False)`, seeded with the first price; values are shown
    only after `span` observations. After a few spans this matches common charting tools.
  * RSI: Wilder's smoothing (the original definition). The first average is the simple
    mean of the first `period` gains/losses, then avg = (prev * (n - 1) + current) / n.
  * MACD: EMA(12) - EMA(26); signal = EMA(9) of MACD; histogram = MACD - signal.
  * Bollinger Bands: SMA(20) +/- 2 x POPULATION standard deviation (ddof=0), as most
    charting tools use.
  * Indicators use the unadjusted `close` (what price charts show). Returns and benchmark
    comparison use `adjusted_close` (dividends/splits accounted for).
"""

import math
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- basic building blocks
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI. Flat prices (no gains and no losses) give 50."""
    delta = close.diff().to_numpy()
    gains, losses = np.clip(delta, 0, None), np.clip(-delta, 0, None)
    out = np.full(len(close), np.nan)
    if len(close) <= period:
        return pd.Series(out, index=close.index)
    avg_gain, avg_loss = gains[1:period + 1].mean(), losses[1:period + 1].mean()
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out[i] = 50.0 if avg_gain == 0 else 100.0
        else:
            out[i] = 100 - 100 / (1 + avg_gain / avg_loss)
    return pd.Series(out, index=close.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": signal_line, "macd_histogram": line - signal_line})


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    middle = sma(close, window)
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    return pd.DataFrame({"bb_upper": middle + num_std * std, "bb_middle": middle, "bb_lower": middle - num_std * std})


# ---------------------------------------------------------------- full indicator table
def compute_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Input: validated OHLCV frame (Phase 3). Output: the same rows plus indicator columns."""
    close = frame["close"]
    out = frame.copy()
    for window in (20, 50, 200):
        out[f"sma_{window}"] = sma(close, window)
    out["ema_12"] = ema(close, 12)
    out["ema_26"] = ema(close, 26)
    out["rsi_14"] = rsi(close, 14)
    out = out.join(macd(close)).join(bollinger(close))
    out["volume_avg_20"] = sma(frame["volume"].astype("float64"), 20)
    return out


def _clean(value: Any, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return None
    return round(float(value), digits)


def latest_snapshot(ind: pd.DataFrame) -> dict[str, Any]:
    """Most recent value of every indicator (None when there is not enough history)."""
    last = ind.iloc[-1]
    return {
        "sma_20": _clean(last["sma_20"]), "sma_50": _clean(last["sma_50"]), "sma_200": _clean(last["sma_200"]),
        "ema_12": _clean(last["ema_12"]), "ema_26": _clean(last["ema_26"]),
        "rsi_14": _clean(last["rsi_14"]),
        "macd": {"macd": _clean(last["macd"], 3), "signal": _clean(last["macd_signal"], 3),
                 "histogram": _clean(last["macd_histogram"], 3)},
        "bollinger": {"upper": _clean(last["bb_upper"]), "middle": _clean(last["bb_middle"]),
                      "lower": _clean(last["bb_lower"])},
    }


# ---------------------------------------------------------------- interpretation rules
def classify_trend(ind: pd.DataFrame) -> dict[str, Any]:
    """Deterministic trend rule based on moving-average alignment.

    With >= 200 rows:  bullish if close > SMA50 > SMA200; bearish if close < SMA50 < SMA200.
    With 50-199 rows:  same idea with SMA20/SMA50 (short-history rule, reported as such).
    Otherwise sideways; fewer than 50 rows -> insufficient_data.
    """
    last = ind.iloc[-1]
    close = float(last["close"])
    if not pd.isna(last["sma_200"]):
        fast, slow, names, basis = float(last["sma_50"]), float(last["sma_200"]), ("SMA50", "SMA200"), "long_term"
    elif not pd.isna(last["sma_50"]):
        fast, slow, names, basis = float(last["sma_20"]), float(last["sma_50"]), ("SMA20", "SMA50"), "short_history"
    else:
        return {"classification": "insufficient_data", "basis": None,
                "rules_triggered": ["fewer than 50 trading days of data"]}

    values = f"close {close:.2f}, {names[0]} {fast:.2f}, {names[1]} {slow:.2f}"
    if close > fast > slow:
        label, rule = "bullish", f"close > {names[0]} > {names[1]} ({values})"
    elif close < fast < slow:
        label, rule = "bearish", f"close < {names[0]} < {names[1]} ({values})"
    else:
        label, rule = "sideways", f"moving averages not aligned ({values})"
    return {"classification": label, "basis": basis, "rules_triggered": [rule]}


def rsi_zone(value: float | None) -> str | None:
    if value is None:
        return None
    return "overbought" if value >= 70 else "oversold" if value <= 30 else "neutral"


def volume_analysis(frame: pd.DataFrame, window: int = 20, spike_factor: float = 2.0) -> dict[str, Any]:
    volume = frame["volume"].astype("float64")
    avg = sma(volume, window)
    recent = frame.iloc[-window:]
    spikes = recent.index[(volume.iloc[-window:] > spike_factor * avg.iloc[-window:]).to_numpy()]
    last_avg = avg.iloc[-1]
    return {
        "last": int(volume.iloc[-1]),
        "avg_20d": None if pd.isna(last_avg) else int(round(last_avg)),
        "last_vs_avg_ratio": None if pd.isna(last_avg) or last_avg == 0 else round(float(volume.iloc[-1] / last_avg), 2),
        "spike_days_last_20": [d.strftime("%Y-%m-%d") for d in spikes],
    }


def period_return_pct(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return None
    return round(float((clean.iloc[-1] / clean.iloc[0] - 1) * 100), 2)


def benchmark_comparison(stock: pd.DataFrame, benchmark: pd.DataFrame, benchmark_symbol: str) -> dict[str, Any]:
    """Return over the dates BOTH series have (adjusted close), and the difference."""
    joined = pd.concat([stock["adjusted_close"].rename("stock"), benchmark["adjusted_close"].rename("bench")],
                       axis=1, join="inner").dropna()
    if len(joined) < 2:
        return {"benchmark": benchmark_symbol, "available": False, "reason": "no overlapping dates"}
    s, b = period_return_pct(joined["stock"]), period_return_pct(joined["bench"])
    return {
        "benchmark": benchmark_symbol, "available": True,
        "from": joined.index[0].strftime("%Y-%m-%d"), "to": joined.index[-1].strftime("%Y-%m-%d"),
        "trading_days": len(joined), "stock_return_pct": s, "benchmark_return_pct": b,
        "relative_pct": None if s is None or b is None else round(s - b, 2),
        "outperformed": None if s is None or b is None else s > b,
    }


def corporate_action_warning(frame: pd.DataFrame, tolerance: float = 0.05) -> str | None:
    """Unadjusted indicators can jump around splits/bonus issues. Detect them from the
    close / adjusted_close ratio changing inside the window."""
    ratio = (frame["close"] / frame["adjusted_close"]).replace([np.inf, -np.inf], np.nan).dropna()
    if len(ratio) > 1 and (ratio.max() / ratio.min() - 1) > tolerance:
        return ("A split, bonus issue or large dividend occurred in this period; indicators based on the "
                "unadjusted close may show an artificial jump.")
    return None
