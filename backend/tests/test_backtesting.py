"""Walk-forward backtest (app/analysis/backtesting.py)."""

import pandas as pd
import pytest

from app.analysis import backtesting as bt
from app.analysis import optimization as opt
from tests.fixtures.generate_synthetic_prices import generate

LOOKBACK = 252


def prices(days: int = 500) -> pd.DataFrame:
    return opt.price_matrix({f"S{s}.NS": generate(seed=s, days=days)["adjusted_close"] for s in (1, 2, 3)})


def equal_fn(history):
    return pd.Series(1 / len(history.columns), index=history.columns), "equal_weight", None


def minvol_fn(history):
    r = opt.optimize(history, "min_volatility")
    return r.weights, r.method, r.fallback_reason


def test_no_look_ahead():
    """Weights on a rebalance date must not change when LATER prices change, and the weight
    function must never see a date after the rebalance date."""
    p = prices()
    seen = []

    def spy(history):
        seen.append(history.index[-1])
        return minvol_fn(history)

    base = bt.run_backtest(p, spy, lookback=LOOKBACK, rebalance="quarterly")
    decision_dates = [pd.Timestamp(d["date"]) for d in base["rebalances"]]
    assert seen == decision_dates  # each call ends exactly on its decision date

    cut = decision_dates[2]
    changed = p.copy()
    changed.loc[changed.index > cut] *= 1.5 + 0.2 * (changed.loc[changed.index > cut].index.day_of_week.to_numpy()[:, None])
    other = bt.run_backtest(changed, minvol_fn, lookback=LOOKBACK, rebalance="quarterly")
    for a, b in zip(base["rebalances"], other["rebalances"]):
        if pd.Timestamp(a["date"]) <= cut:
            assert a["weights_pct"] == b["weights_pct"]
    assert base["equity_curve"][0]["strategy"] == other["equity_curve"][0]["strategy"]


def test_buy_and_hold_by_hand():
    idx = pd.bdate_range("2025-01-01", periods=LOOKBACK + 31)
    a = pd.Series(100.0, index=idx)
    b = pd.Series(100.0, index=idx)
    a.iloc[LOOKBACK + 1:] = 200.0  # A doubles the day after the purchase
    p = pd.DataFrame({"A": a, "B": b})
    r = bt.run_backtest(p, equal_fn, lookback=LOOKBACK, rebalance="none", cost_bps=0, capital=1000)
    assert r["end_value"] == pytest.approx(1500)  # 500 in A doubles, 500 in B unchanged
    assert r["total_return_pct"] == 50.0 and len(r["rebalances"]) == 1
    assert r["rebalances"][0]["turnover_pct"] == 100.0  # the first purchase


def test_transaction_costs_reduce_the_result():
    p = prices()
    free = bt.run_backtest(p, equal_fn, lookback=LOOKBACK, rebalance="monthly", cost_bps=0)
    costly = bt.run_backtest(p, equal_fn, lookback=LOOKBACK, rebalance="monthly", cost_bps=50)
    assert costly["end_value"] < free["end_value"] and costly["total_costs_inr"] > 0 and free["total_costs_inr"] == 0
    # first trade: 100% turnover x 50 bps of 100,000 = 500
    assert costly["rebalances"][0]["cost_inr"] == pytest.approx(500)


def test_equal_weight_strategy_matches_equal_weight_comparison():
    r = bt.run_backtest(prices(), equal_fn, lookback=LOOKBACK, rebalance="quarterly")
    assert all(row["strategy"] == row["equal_weight"] for row in r["equity_curve"])
    assert r["cagr_pct"] == r["vs_benchmark"]["equal_weight"]["cagr_pct"]


def test_rebalance_schedule():
    idx = pd.bdate_range("2025-01-01", "2025-12-31")
    start = 10
    monthly = bt.rebalance_positions(idx, start, "monthly")
    assert monthly[0] == start and len(monthly) == 12  # start (Jan) + last day of Jan..Nov
    assert all(idx[p].month != idx[p + 1].month for p in monthly[1:])
    assert bt.rebalance_positions(idx, start, "quarterly") == [start] + [
        p for p in monthly[1:] if idx[p].month in (3, 6, 9)]
    assert bt.rebalance_positions(idx, start, "none") == [start]
    with pytest.raises(bt.BacktestError):
        bt.rebalance_positions(idx, start, "weekly")


def test_benchmark_and_metrics():
    p = prices()
    bench = generate(seed=7, days=500)["adjusted_close"]
    r = bt.run_backtest(p, minvol_fn, lookback=LOOKBACK, benchmark=bench, risk_free_rate_pct=6.0)
    assert r["equity_curve"][0]["nifty50"] == 100_000 and r["vs_benchmark"]["nifty50"]["cagr_pct"] is not None
    assert r["sharpe"] is not None and r["max_drawdown_pct"] <= 0 and r["volatility_pct"] > 0
    assert r["period"]["trading_days"] == len(p) - 1 - LOOKBACK
    assert r["look_ahead_safeguards"] and any("hindsight" in x for x in r["limitations"])
    no_bench = bt.run_backtest(p, equal_fn, lookback=LOOKBACK)
    assert no_bench["vs_benchmark"]["nifty50"] is None and no_bench["sharpe"] is None


def test_not_enough_history():
    with pytest.raises(bt.BacktestError, match="not enough history"):
        bt.run_backtest(prices(260), equal_fn, lookback=LOOKBACK)
    with pytest.raises(bt.BacktestError, match="negative"):
        bt.run_backtest(prices(), equal_fn, cost_bps=-1)
