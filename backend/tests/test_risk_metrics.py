"""Risk metrics vs hand-computed values and independent loop implementations (task 8.1.8)."""

import math

import numpy as np
import pandas as pd
import pytest

from app.analysis import risk_metrics as rm
from app.config import Settings
from tests.fixtures.generate_synthetic_prices import generate

RFR = {"value_pct": 6.0, "as_of_date": "2026-11-20", "source": "test"}


def series(values, start="2026-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype="float64")


# ---------------------------------------------------------------- independent references
def ref_std(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ref_beta(s, b):
    ms, mb = sum(s) / len(s), sum(b) / len(b)
    cov = sum((x - ms) * (y - mb) for x, y in zip(s, b, strict=True)) / (len(s) - 1)
    var = sum((y - mb) ** 2 for y in b) / (len(b) - 1)
    return cov / var


@pytest.fixture
def stock():
    return generate(seed=42)["adjusted_close"]


@pytest.fixture
def market():
    return generate(seed=7)["adjusted_close"]


# ---------------------------------------------------------------- returns and volatility
def test_returns_and_volatility_match_reference(stock):
    r = rm.daily_returns(stock)
    closes = stock.tolist()
    manual = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    assert r.tolist() == pytest.approx(manual, rel=1e-12)
    assert rm.annualized_volatility_pct(r) == round(ref_std(manual) * math.sqrt(252) * 100, 2)
    assert rm.annualized_return_pct(r) == round(sum(manual) / len(manual) * 252 * 100, 2)
    assert rm.log_returns(stock).iloc[0] == pytest.approx(math.log(closes[1] / closes[0]))


def test_distribution(stock):
    r = rm.daily_returns(stock)
    d = rm.return_distribution(r)
    assert d["observations"] == len(r)
    assert d["std_daily_pct"] == round(ref_std(r.tolist()) * 100, 4)
    assert d["p5_pct"] == round(float(np.percentile(r * 100, 5)), 3)
    assert d["worst_day"]["return_pct"] == round(r.min() * 100, 2)
    normal = pd.Series(np.random.default_rng(0).normal(0, 0.01, 20000))
    assert abs(rm.return_distribution(normal)["excess_kurtosis"]) < 0.15  # excess kurtosis ~0 for normal


# ---------------------------------------------------------------- beta
def test_beta_matches_reference(stock, market):
    s, b = rm.daily_returns(stock), rm.daily_returns(market)
    result = rm.beta(s, b)
    assert result["value"] == round(ref_beta(s.tolist(), b.tolist()), 3)
    assert result["observations"] == len(s)


def test_beta_of_benchmark_against_itself_is_one(market):
    r = rm.daily_returns(market)
    assert rm.beta(r, r)["value"] == 1.0 and rm.beta(r, r)["r_squared"] == 1.0


def test_beta_uses_only_common_dates_and_needs_enough(stock, market):
    s, b = rm.daily_returns(stock), rm.daily_returns(market).iloc[:40]
    result = rm.beta(s, b)
    assert result["value"] is None and "only 40 overlapping days" in result["reason"]


# ---------------------------------------------------------------- drawdown
def test_drawdown_hand_example_not_recovered():
    md = rm.max_drawdown(series([100, 120, 90, 110, 130, 80, 100]))
    assert md["max_drawdown_pct"] == round((80 / 130 - 1) * 100, 2) == -38.46
    assert md["peak_date"] == "2026-01-07" and md["trough_date"] == "2026-01-08"  # 130 -> 80
    assert md["recovered"] is False and md["duration_trading_days"] == 2


def test_drawdown_recovered():
    md = rm.max_drawdown(series([100, 80, 100, 120]))
    assert md["max_drawdown_pct"] == -20.0 and md["recovered"] is True
    assert md["recovery_date"] == "2026-01-05" and md["duration_trading_days"] == 2


def test_no_drawdown_for_rising_prices():
    assert rm.max_drawdown(series([1, 2, 3, 4]))["max_drawdown_pct"] == 0.0


# ---------------------------------------------------------------- Sharpe
def test_sharpe_hand_computed(stock):
    r = rm.daily_returns(stock)
    expected = (r.mean() * 252 - 0.06) / (ref_std(r.tolist()) * math.sqrt(252))
    assert rm.sharpe_ratio(r, RFR)["value"] == round(expected, 3)


def test_sharpe_requires_risk_free_rate(stock):
    s = rm.sharpe_ratio(rm.daily_returns(stock), None)
    assert s["value"] is None and "not configured" in s["reason"]


# ---------------------------------------------------------------- correlation, concentration
def test_correlation_matrix(stock, market):
    s, m = rm.daily_returns(stock), rm.daily_returns(market)
    c = rm.correlation_matrix({"A": s, "B": m, "C": -s})
    assert c["matrix"]["A"]["A"] == 1.0 and c["matrix"]["A"]["C"] == -1.0
    assert c["matrix"]["A"]["B"] == round(float(np.corrcoef(s, m)[0, 1]), 3)
    assert rm.correlation_matrix({"A": s})["reason"] == "needs at least two stocks"


def test_concentration_hand_computed():
    equal = rm.concentration({"A": 1, "B": 1, "C": 1, "D": 1})
    assert equal["hhi"] == 0.25 and equal["effective_number_of_stocks"] == 4.0
    tilted = rm.concentration({"A": 3, "B": 1})  # 0.75^2 + 0.25^2
    assert tilted["hhi"] == 0.625 and tilted["effective_number_of_stocks"] == 1.6 and tilted["largest_weight_pct"] == 75.0


# ---------------------------------------------------------------- rules
@pytest.mark.parametrize("vol, mdd, expected", [(15, -10, "low"), (25, -20, "moderate"), (40, -20, "high"),
                                                (15, -45, "moderate"), (25, -50, "high"), (None, None, "insufficient_data")])
def test_classify_risk(vol, mdd, expected):
    assert rm.classify_risk(vol, mdd) == expected


def test_market_sensitivity():
    assert [rm.market_sensitivity(b) for b in (0.5, 1.0, 1.5, None)] == ["defensive", "market-like", "aggressive", None]


def test_diversification():
    one = rm.diversification({"matrix": {}}, rm.concentration({"A": 1}))
    assert one["assessment"] == "not_diversified"
    corr = {"matrix": {"A": {"A": 1, "B": 0.2}, "B": {"A": 0.2, "B": 1}}}
    assert rm.diversification(corr, rm.concentration({"A": 1, "B": 1}))["assessment"] == "good"


# ---------------------------------------------------------------- risk-free rate settings (D4)
def test_risk_free_rate_settings():
    placeholders = Settings(_env_file=None, risk_free_rate_pct="<value>", risk_free_rate_date="<YYYY-MM-DD>",
                            risk_free_rate_source="<description>")
    assert placeholders.risk_free_rate is None
    partial = Settings(_env_file=None, risk_free_rate_pct="6.5")
    assert partial.risk_free_rate is None  # all three are required
    full = Settings(_env_file=None, risk_free_rate_pct="6.5", risk_free_rate_date="2026-11-20",
                    risk_free_rate_source="RBI 91-day T-bill")
    assert full.risk_free_rate == {"value_pct": 6.5, "as_of_date": "2026-11-20", "source": "RBI 91-day T-bill"}
