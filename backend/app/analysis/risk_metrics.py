"""Historical risk metrics (computed in Python, never by the LLM).

Conventions (documented so every number can be reproduced):
  * Returns are SIMPLE daily returns of the ADJUSTED close (dividends/splits included).
    Log returns are also provided for the distribution statistics.
  * Annualisation uses 252 trading days: volatility x sqrt(252), mean return x 252.
  * Standard deviation uses the sample formula (ddof = 1).
  * Beta = covariance(stock, NIFTY 50) / variance(NIFTY 50) on the SAME dates (inner join).
  * Sharpe ratio = (annualised mean return - risk-free rate) / annualised volatility, with the
    manually configured risk-free rate (decision D4). Not computed if the rate is missing.
  * Maximum drawdown: largest fall from a running peak of the adjusted close.
  * Concentration: Herfindahl-Hirschman index (sum of squared weights) and the "effective
    number of stocks" 1 / HHI. Equal weights are assumed until Phase 9 provides weights.
  * Kurtosis is EXCESS kurtosis (normal distribution = 0).
Historical risk describes the past; it is not a forecast.
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252
MIN_OBSERVATIONS = 60  # fewer daily returns than this are too few for stable estimates


def _r(value: float | None, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def log_returns(prices: pd.Series) -> pd.Series:
    return np.log(prices / prices.shift(1)).dropna()


def _label(index_value) -> str:
    return index_value.strftime("%Y-%m-%d") if hasattr(index_value, "strftime") else str(index_value)


def return_distribution(returns: pd.Series) -> dict[str, Any]:
    """Statistics of daily returns, in percent."""
    if len(returns) < 2:
        return {"observations": len(returns)}
    pct = returns * 100
    return {
        "observations": int(len(returns)),
        "mean_daily_pct": _r(pct.mean(), 4),
        "std_daily_pct": _r(pct.std(ddof=1), 4),
        "skewness": _r(stats.skew(returns, bias=False), 3),
        "excess_kurtosis": _r(stats.kurtosis(returns, fisher=True, bias=False), 3),
        "p5_pct": _r(np.percentile(pct, 5), 3),
        "p95_pct": _r(np.percentile(pct, 95), 3),
        "worst_day": {"date": _label(returns.idxmin()), "return_pct": _r(pct.min(), 2)},
        "best_day": {"date": _label(returns.idxmax()), "return_pct": _r(pct.max(), 2)},
        "positive_days_pct": _r((returns > 0).mean() * 100, 1),
    }


def annualized_volatility_pct(returns: pd.Series) -> float | None:
    if len(returns) < 2:
        return None
    return _r(returns.std(ddof=1) * math.sqrt(TRADING_DAYS) * 100)


def annualized_return_pct(returns: pd.Series) -> float | None:
    """Arithmetic mean daily return x 252 (the Sharpe convention, not CAGR)."""
    if len(returns) < 1:
        return None
    return _r(returns.mean() * TRADING_DAYS * 100)


def beta(stock_returns: pd.Series, benchmark_returns: pd.Series) -> dict[str, Any]:
    joined = pd.concat([stock_returns.rename("s"), benchmark_returns.rename("b")], axis=1, join="inner").dropna()
    n = len(joined)
    if n < MIN_OBSERVATIONS:
        return {"value": None, "observations": n,
                "reason": f"only {n} overlapping days with NIFTY 50 (need {MIN_OBSERVATIONS})"}
    var_b = joined["b"].var(ddof=1)
    if var_b == 0:
        return {"value": None, "observations": n, "reason": "benchmark returns have zero variance"}
    b = joined["s"].cov(joined["b"], ddof=1) / var_b
    corr = joined["s"].corr(joined["b"])
    return {"value": _r(b, 3), "observations": n, "correlation_with_benchmark": _r(corr, 3),
            "r_squared": _r(corr ** 2, 3), "reason": None}


def max_drawdown(prices: pd.Series) -> dict[str, Any]:
    """Largest peak-to-trough fall, with dates and whether/when it recovered."""
    if len(prices) < 2:
        return {"max_drawdown_pct": None, "reason": "not enough prices"}
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    trough_date = drawdown.idxmin()
    mdd = drawdown.loc[trough_date]
    if mdd >= 0:
        return {"max_drawdown_pct": 0.0, "peak_date": None, "trough_date": None, "recovery_date": None,
                "duration_trading_days": 0, "recovered": True}
    peak_value = running_peak.loc[trough_date]
    peak_date = prices.loc[:trough_date][prices.loc[:trough_date] == peak_value].index[-1]
    after = prices.loc[trough_date:]
    recovered = after[after >= peak_value]
    recovery_date = recovered.index[0] if not recovered.empty else None
    end = recovery_date if recovery_date is not None else prices.index[-1]
    return {
        "max_drawdown_pct": _r(mdd * 100),
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "recovery_date": recovery_date.strftime("%Y-%m-%d") if recovery_date is not None else None,
        "recovered": recovery_date is not None,
        # trading days from peak to recovery (or to the last date if not recovered yet)
        "duration_trading_days": int(prices.index.get_loc(end) - prices.index.get_loc(peak_date)),
        "current_drawdown_pct": _r(drawdown.iloc[-1] * 100),
    }


def sharpe_ratio(returns: pd.Series, risk_free_rate: dict | None) -> dict[str, Any]:
    if risk_free_rate is None:
        return {"value": None, "reason": "risk-free rate not configured (RISK_FREE_RATE_PCT/_DATE/_SOURCE in .env)"}
    vol = returns.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(returns) > 1 else None
    if not vol:
        return {"value": None, "reason": "volatility is zero or unavailable"}
    excess = returns.mean() * TRADING_DAYS - risk_free_rate["value_pct"] / 100
    return {"value": _r(excess / vol, 3), "reason": None,
            "formula": "(annualised mean daily return - risk-free rate) / annualised volatility"}


def correlation_matrix(returns_by_symbol: dict[str, pd.Series]) -> dict[str, Any]:
    """Pairwise correlations of daily returns on common dates."""
    if len(returns_by_symbol) < 2:
        return {"matrix": {}, "observations": 0, "reason": "needs at least two stocks"}
    frame = pd.DataFrame(returns_by_symbol).dropna()
    if len(frame) < MIN_OBSERVATIONS:
        return {"matrix": {}, "observations": len(frame),
                "reason": f"only {len(frame)} common trading days (need {MIN_OBSERVATIONS})"}
    corr = frame.corr()
    return {"matrix": {a: {b: _r(corr.loc[a, b], 3) for b in corr.columns} for a in corr.index},
            "observations": len(frame), "reason": None}


def concentration(weights: dict[str, float]) -> dict[str, Any]:
    total = sum(weights.values())
    if total <= 0:
        return {"hhi": None, "reason": "weights must be positive"}
    w = {k: v / total for k, v in weights.items()}
    hhi = sum(x * x for x in w.values())
    return {"hhi": _r(hhi, 4), "effective_number_of_stocks": _r(1 / hhi, 2),
            "largest_weight_pct": _r(max(w.values()) * 100), "weights_pct": {k: _r(v * 100) for k, v in w.items()}}


# ---------------------------------------------------------------- rule-based interpretation
RISK_RULES = {
    "volatility": "annualised volatility below 20% low, 20-35% moderate, above 35% high",
    "drawdown": "a maximum drawdown worse than -40% raises the risk class by one level",
    "beta": "beta below 0.8 defensive, 0.8-1.2 market-like, above 1.2 aggressive",
    "diversification": "average pairwise correlation below 0.3 good, 0.3-0.6 moderate, above 0.6 poor",
}


def classify_risk(volatility_pct: float | None, max_drawdown_pct: float | None) -> str:
    if volatility_pct is None:
        return "insufficient_data"
    level = 0 if volatility_pct < 20 else 1 if volatility_pct <= 35 else 2
    if max_drawdown_pct is not None and max_drawdown_pct < -40:
        level = min(level + 1, 2)
    return ["low", "moderate", "high"][level]


def market_sensitivity(beta_value: float | None) -> str | None:
    if beta_value is None:
        return None
    return "defensive" if beta_value < 0.8 else "market-like" if beta_value <= 1.2 else "aggressive"


def diversification(corr: dict[str, Any], conc: dict[str, Any]) -> dict[str, Any]:
    matrix = corr.get("matrix") or {}
    symbols = list(matrix)
    if len(conc.get("weights_pct", {})) < 2:
        return {"assessment": "not_diversified", "reason": "a single stock carries all the risk"}
    if not matrix:
        return {"assessment": "insufficient_data", "reason": corr.get("reason")}
    pairs = [matrix[a][b] for i, a in enumerate(symbols) for b in symbols[i + 1:] if matrix[a][b] is not None]
    avg = sum(pairs) / len(pairs)
    label = "good" if avg < 0.3 else "moderate" if avg <= 0.6 else "poor"
    return {"assessment": label, "average_pairwise_correlation": _r(avg, 3),
            "effective_number_of_stocks": conc.get("effective_number_of_stocks")}
