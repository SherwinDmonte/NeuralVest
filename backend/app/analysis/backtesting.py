"""Walk-forward backtest of an allocation RULE on historical prices.

How it works:
  1. The first `lookback` trading days are used only for estimation; the test period starts
     after them (out-of-sample).
  2. On each rebalance date t the weights are computed from the `lookback` days UP TO AND
     INCLUDING t, the trade happens at t's close, and returns are earned from t+1 onwards.
  3. Between rebalance dates the weights drift with prices (no daily rebalancing).
  4. Every trade costs `cost_bps` basis points of the traded value (turnover = sum of the
     absolute weight changes; the first purchase counts as 100% turnover).
  5. Comparisons: an equal-weight portfolio rebalanced on the same dates with the same costs,
     and NIFTY 50 bought and held (an index cannot be traded directly, so no costs).

Look-ahead-bias safeguards:
  * The weight function only ever receives a slice that ENDS at the rebalance date
    (`prices.iloc[pos - lookback:pos + 1]`); later prices are not passed to it at all. A test
    changes future prices and checks that earlier weights do not change.
  * Trades use the close of the decision day and earn returns only from the next day.
  * The same estimation rule, method and constraints are used as for today's allocation.

Known limits (reported with every result):
  * Selection bias: the stocks were chosen today, with hindsight.
  * One risk-free rate (today's) is used for the whole period; historical rates are not stored.
  * Adjusted closes include dividends and splits, assuming dividends were reinvested.
  * Taxes, slippage, lot sizes and whole-share rounding are ignored.
"""

import math
from collections.abc import Callable
from typing import Any

import pandas as pd

from app.analysis import risk_metrics as rm

TRADING_DAYS = 252
REBALANCE_FREQUENCIES = ("monthly", "quarterly", "none")
MIN_TEST_DAYS = 20
LIMITATIONS = [
    "The stocks were chosen today, so the test has hindsight (selection bias).",
    "Today's risk-free rate is used for the whole period.",
    "Adjusted closes assume dividends were reinvested.",
    "Taxes, slippage, lot sizes and whole-share rounding are ignored.",
    "Past results do not guarantee future results.",
]

WeightFunction = Callable[[pd.DataFrame], tuple[pd.Series, str | None, str | None]]


class BacktestError(ValueError):
    pass


def _r(value, digits: int = 2):
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


def rebalance_positions(index: pd.DatetimeIndex, start: int, frequency: str) -> list[int]:
    """Row positions of the trades: the start, then the last trading day of every month or
    quarter after it (the final day is excluded because nothing is earned after it)."""
    if frequency not in REBALANCE_FREQUENCIES:
        raise BacktestError(f"unknown rebalancing frequency '{frequency}'")
    positions = [start]
    if frequency == "none":
        return positions
    freq = "M" if frequency == "monthly" else "Q"
    periods = index.to_period(freq)
    for pos in range(start + 1, len(index) - 1):
        if periods[pos] != periods[pos + 1]:
            positions.append(pos)
    return positions


def simulate(prices: pd.DataFrame, targets: dict[int, pd.Series], start: int, cost_bps: float,
             capital: float) -> tuple[pd.Series, list[dict]]:
    """Equity curve from `start` to the end, trading to `targets[pos]` at those positions."""
    weights = pd.Series(0.0, index=prices.columns)
    value, values, trades = capital, [], []
    for pos in range(start, len(prices)):
        if pos > start:
            growth = prices.iloc[pos] / prices.iloc[pos - 1]
            gross = float((weights * growth).sum())
            value *= gross
            weights = weights * growth / gross
        if pos in targets:
            new = targets[pos].reindex(prices.columns).fillna(0)
            turnover = float((new - weights).abs().sum())
            cost = value * turnover * cost_bps / 10_000
            value -= cost
            weights = new
            trades.append({"date": prices.index[pos].strftime("%Y-%m-%d"), "turnover_pct": _r(turnover * 100),
                           "cost_inr": _r(cost)})
        values.append(value)
    return pd.Series(values, index=prices.index[start:]), trades


def metrics(equity: pd.Series, risk_free_rate_pct: float | None) -> dict[str, Any]:
    daily = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    growth = equity.iloc[-1] / equity.iloc[0]
    vol = daily.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(daily) > 1 else None
    sharpe = None
    if risk_free_rate_pct is not None and vol:
        sharpe = (daily.mean() * TRADING_DAYS - risk_free_rate_pct / 100) / vol
    mdd = rm.max_drawdown(equity)
    return {
        "start_value": _r(equity.iloc[0]), "end_value": _r(equity.iloc[-1]),
        "total_return_pct": _r((growth - 1) * 100),
        "cagr_pct": _r((growth ** (1 / years) - 1) * 100) if years > 0 else None,
        "volatility_pct": _r(vol * 100) if vol is not None else None,
        "sharpe": _r(sharpe, 3),
        "sharpe_reason": None if sharpe is not None else "risk-free rate not configured",
        "max_drawdown_pct": mdd.get("max_drawdown_pct"),
        "max_drawdown": {k: mdd.get(k) for k in ("peak_date", "trough_date", "recovered")},
    }


def run_backtest(prices: pd.DataFrame, weight_fn: WeightFunction, *, lookback: int = 252,
                 rebalance: str = "quarterly", cost_bps: float = 10.0, capital: float = 100_000.0,
                 risk_free_rate_pct: float | None = None, benchmark: pd.Series | None = None) -> dict[str, Any]:
    """`weight_fn(history)` -> (weights, method_used, fallback_reason). `history` ends at the
    rebalance date and holds `lookback + 1` prices."""
    if cost_bps < 0:
        raise BacktestError("transaction cost must not be negative")
    if len(prices) - 1 - lookback < MIN_TEST_DAYS:
        raise BacktestError(f"not enough history for a backtest: {len(prices)} common trading days, need at "
                            f"least {lookback + 1 + MIN_TEST_DAYS} ({lookback} for estimation + "
                            f"{MIN_TEST_DAYS} to test)")
    start = lookback
    positions = rebalance_positions(prices.index, start, rebalance)
    targets, decisions = {}, []
    for pos in positions:
        history = prices.iloc[pos - lookback:pos + 1]  # nothing after the decision date
        weights, method_used, fallback = weight_fn(history)
        targets[pos] = weights
        decisions.append({"date": prices.index[pos].strftime("%Y-%m-%d"), "method": method_used,
                          "fallback_reason": fallback,
                          "weights_pct": {s: _r(w * 100) for s, w in weights.items()}})
    strategy, trades = simulate(prices, targets, start, cost_bps, capital)
    for d, t in zip(decisions, trades):
        d.update(turnover_pct=t["turnover_pct"], cost_inr=t["cost_inr"])

    n = len(prices.columns)
    equal = {pos: pd.Series(1 / n, index=prices.columns) for pos in positions}
    equal_curve, _ = simulate(prices, equal, start, cost_bps, capital)

    bench_curve = None
    if benchmark is not None and len(benchmark):
        aligned = benchmark.sort_index().reindex(strategy.index, method="ffill")
        if aligned.notna().all():
            bench_curve = capital * aligned / aligned.iloc[0]

    curve = [{"date": d.strftime("%Y-%m-%d"), "strategy": _r(strategy[d]), "equal_weight": _r(equal_curve[d]),
              "nifty50": _r(bench_curve[d]) if bench_curve is not None else None} for d in strategy.index]
    result = metrics(strategy, risk_free_rate_pct)
    eq_metrics = metrics(equal_curve, risk_free_rate_pct)
    bench_metrics = metrics(bench_curve, risk_free_rate_pct) if bench_curve is not None else None
    return {
        "period": {"from": strategy.index[0].strftime("%Y-%m-%d"), "to": strategy.index[-1].strftime("%Y-%m-%d"),
                   "trading_days": len(strategy) - 1,
                   "estimation_from": prices.index[0].strftime("%Y-%m-%d")},
        "settings": {"lookback_days": lookback, "rebalancing": rebalance, "transaction_cost_bps": cost_bps,
                     "initial_capital_inr": capital, "risk_free_rate_pct": risk_free_rate_pct},
        **result,
        "rebalances": decisions,
        "fallbacks_used": sum(1 for d in decisions if d["fallback_reason"]),
        "total_costs_inr": _r(sum(t["cost_inr"] or 0 for t in trades)),
        "vs_benchmark": {
            "equal_weight": eq_metrics,
            "nifty50": bench_metrics,
            "nifty50_reason": None if bench_metrics else "NIFTY 50 prices unavailable for the test period",
        },
        "equity_curve": curve,
        "look_ahead_safeguards": [
            "weights on each rebalance date use only prices up to that date",
            "trades are made at that day's close and earn returns from the next day",
            "the same estimation rule and constraints as today's allocation",
        ],
        "limitations": LIMITATIONS,
    }
