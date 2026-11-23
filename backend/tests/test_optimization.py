"""Portfolio optimisation maths (app/analysis/optimization.py), on synthetic prices."""

import math

import numpy as np
import pandas as pd
import pytest

from app.analysis import optimization as opt
from tests.fixtures.generate_synthetic_prices import generate


def prices(*seeds: int, days: int = 300) -> pd.DataFrame:
    return opt.price_matrix({f"S{seed}.NS": generate(seed=seed, days=days)["adjusted_close"] for seed in seeds})


P3 = prices(1, 2, 3)
RF = 6.0


def vol(weights: pd.Series, p: pd.DataFrame) -> float:
    w = opt.estimation_window(p)
    cov = opt.covariance(w)
    x = weights.reindex(cov.index).to_numpy()
    return math.sqrt(x @ cov.to_numpy() @ x)


@pytest.mark.parametrize("method", ["max_sharpe", "min_volatility", "efficient_risk", "equal_weight",
                                    "inverse_volatility", "hrp"])
def test_weights_sum_to_one_and_respect_bounds(method):
    r = opt.optimize(P3, method, min_weight=0.1, max_weight=0.5, risk_free_rate_pct=RF)
    assert r.weights.sum() == pytest.approx(1, abs=1e-9)
    assert (r.weights >= 0.1 - 1e-6).all() and (r.weights <= 0.5 + 1e-6).all()
    assert set(r.weights.index) == set(P3.columns)
    assert sum(opt.weights_to_percent(r.weights).values()) == pytest.approx(100, abs=1e-9)


def test_min_volatility_has_the_lowest_volatility():
    lowest = vol(opt.optimize(P3, "min_volatility").weights, P3)
    for method in ("equal_weight", "inverse_volatility", "hrp"):
        assert lowest <= vol(opt.optimize(P3, method).weights, P3) + 1e-9


def test_max_sharpe_beats_other_portfolios_on_sharpe():
    best = opt.optimize(P3, "max_sharpe", risk_free_rate_pct=RF)
    assert best.method == "max_sharpe" and best.fallback_reason is None
    for method in ("equal_weight", "min_volatility", "inverse_volatility"):
        other = opt.optimize(P3, method, risk_free_rate_pct=RF)
        assert best.expected["sharpe_ratio"] >= other.expected["sharpe_ratio"] - 1e-3


def test_efficient_risk_stays_within_target_and_efficient_return_reaches_target():
    r = opt.optimize(P3, "efficient_risk", target_volatility_pct=25)
    assert r.expected["annual_volatility_pct"] <= 25.01 and r.parameters["target_source"] == "requested"
    default = opt.optimize(P3, "efficient_risk")
    assert "75% of the way" in default.parameters["target_source"]
    mu = opt.expected_returns(opt.estimation_window(P3))
    target = float(mu.mean() * 100)
    er = opt.optimize(P3, "efficient_return", target_return_pct=target)
    assert er.expected["annual_return_pct"] >= target - 0.01  # constraint: return of AT LEAST the target
    assert er.expected["annual_volatility_pct"] <= opt.optimize(P3, "equal_weight").expected["annual_volatility_pct"]


def test_fallbacks_are_explicit():
    no_rate = opt.optimize(P3, "max_sharpe", risk_free_rate_pct=None)
    assert no_rate.method == "min_volatility" and "not configured" in no_rate.fallback_reason
    high_rate = opt.optimize(P3, "max_sharpe", risk_free_rate_pct=400.0)
    assert high_rate.method == "min_volatility" and "beat the risk-free rate" in high_rate.fallback_reason
    too_low = opt.optimize(P3, "efficient_risk", target_volatility_pct=0.5)
    assert too_low.method == "min_volatility" and "below the lowest achievable" in too_low.fallback_reason
    unreachable = opt.optimize(P3, "efficient_return", target_return_pct=400)
    assert unreachable.method == "equal_weight" and "could not be solved" in unreachable.fallback_reason
    assert unreachable.requested_method == "efficient_return"
    with pytest.raises(opt.OptimizationError, match="target return"):
        opt.optimize(P3, "efficient_return")


def test_hrp_with_two_stocks_equals_inverse_variance():
    p2 = prices(1, 2)
    cov = opt.covariance(opt.estimation_window(p2))
    inv_var = 1 / np.diag(cov)
    expected = inv_var / inv_var.sum()
    assert opt.hrp_weights(cov).to_numpy() == pytest.approx(expected, rel=1e-9)


def test_highly_correlated_stocks():
    base = generate(seed=5, days=300)["adjusted_close"]
    noise = np.random.default_rng(0).normal(0, 0.0005, len(base))
    twin = opt.price_matrix({"A.NS": base, "B.NS": base * np.exp(np.cumsum(noise)), "C.NS": generate(seed=9, days=300)
                             ["adjusted_close"]})
    assert twin.pct_change().corr().loc["A.NS", "B.NS"] > 0.95
    for method in ("min_volatility", "max_sharpe", "hrp", "inverse_volatility"):
        r = opt.optimize(twin, method, max_weight=0.6, risk_free_rate_pct=RF)
        assert r.weights.sum() == pytest.approx(1) and (r.weights >= 0).all()


def test_two_stocks_and_infeasible_bounds():
    p2 = prices(1, 2)
    assert opt.optimize(p2, "min_volatility", max_weight=0.5).weights.to_numpy() == pytest.approx([0.5, 0.5])
    with pytest.raises(opt.OptimizationError, match="cannot be met with 2 stocks"):
        opt.optimize(p2, "min_volatility", max_weight=0.4)
    with pytest.raises(opt.OptimizationError, match="minimum of 60%"):
        opt.optimize(p2, "min_volatility", min_weight=0.6)
    with pytest.raises(opt.OptimizationError, match="short positions"):
        opt.check_bounds(2, -0.1, 1)
    with pytest.raises(opt.OptimizationError, match="at least 2 stocks"):
        opt.check_bounds(1, 0, 1)


def test_too_little_history():
    with pytest.raises(opt.OptimizationError, match="need 120"):
        opt.optimize(prices(1, 2, days=100), "equal_weight")


def test_only_the_lookback_window_is_used():
    longer = prices(1, 2, 3, days=600)
    a = opt.optimize(longer, "min_volatility")
    b = opt.optimize(longer.iloc[-(opt.LOOKBACK_DAYS + 1):], "min_volatility")
    assert a.weights.to_numpy() == pytest.approx(b.weights.to_numpy())
    assert a.window["observations"] == opt.LOOKBACK_DAYS


def test_resolve_settings_from_risk_preference():
    s = opt.resolve_settings("moderate", 5)
    assert s["method"] == "max_sharpe" and s["max_weight"] == 0.35 and s["method_source"] == "risk_preference"
    raised = opt.resolve_settings("conservative", 2)
    assert raised["max_weight"] == 0.5 and "raised to 50.00%" in raised["notes"][0]
    assert "forces equal weights" in raised["notes"][0]
    forced = opt.resolve_settings("conservative", 4)
    assert "only possible allocation is equal weights" in forced["notes"][0]
    explicit = opt.resolve_settings("aggressive", 3, method="hrp", max_weight=0.4)
    assert explicit["method"] == "hrp" and explicit["method_source"] == "requested"
    with pytest.raises(opt.OptimizationError):
        opt.resolve_settings("moderate", 2, max_weight=0.3)  # an explicit cap is never changed silently
    with pytest.raises(opt.OptimizationError, match="unknown risk preference"):
        opt.resolve_settings("reckless", 3)


def test_apply_bounds_water_filling():
    w = opt.apply_bounds(pd.Series({"A": 10.0, "B": 1.0, "C": 1.0}), 0.0, 0.5)
    assert w.to_dict() == pytest.approx({"A": 0.5, "B": 0.25, "C": 0.25})
    w = opt.apply_bounds(pd.Series({"A": 10.0, "B": 1.0, "C": 0.0}), 0.1, 1.0)
    assert w["C"] == pytest.approx(0.1) and w.sum() == pytest.approx(1)


def test_discrete_allocation_by_hand():
    # targets 5000 / 5000; floors 16 x 300 = 4800 and 7 x 700 = 4900; cash 300;
    # A is 200 below target and affordable -> one more A share; cash 0.
    alloc = opt.discrete_allocation(pd.Series({"A": 0.5, "B": 0.5}), pd.Series({"A": 300.0, "B": 700.0}), 10_000)
    assert alloc["shares"] == {"A": 17, "B": 7}
    assert alloc["invested_inr"] == 10_000 and alloc["leftover_cash_inr"] == 0
    small = opt.discrete_allocation(pd.Series({"A": 0.5, "B": 0.5}), pd.Series({"A": 300.0, "B": 7000.0}), 1000)
    assert small["shares"]["B"] == 0 and small["leftover_cash_inr"] >= 0
    with pytest.raises(opt.OptimizationError, match="positive"):
        opt.discrete_allocation(pd.Series({"A": 1.0}), pd.Series({"A": 1.0}), 0)


def test_percentages_add_up_to_exactly_100():
    pct = opt.weights_to_percent(pd.Series({"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}))
    assert sum(pct.values()) == 100 and sorted(pct.values()) == [33.33, 33.33, 33.34]


def test_price_matrix_uses_common_dates_only():
    a = generate(seed=1, days=50)["adjusted_close"]
    b = a.iloc[10:]
    assert len(opt.price_matrix({"A": a, "B": b})) == 40
