"""Portfolio optimisation (computed in Python, never by the LLM).

Conventions (documented so every allocation can be reproduced):
  * Inputs are ADJUSTED close prices of the selected stocks on their COMMON trading dates.
  * Estimation window: the last 252 trading days (about one year). The backtest uses exactly
    the same rule at every rebalance date, so it tests the rule that produced today's weights.
  * Expected returns: arithmetic mean of simple daily returns x 252 (same convention as the
    Risk Assessment Agent and its Sharpe ratio). Optional: exponentially weighted mean
    (span 126 days), which gives recent months more influence. Past averages are a weak
    estimate of future returns; this is the main limitation of mean-variance optimisation.
  * Covariance: Ledoit-Wolf shrinkage of the sample covariance (default; more stable with
    few observations) or the plain sample covariance, annualised x 252.
  * No short selling: every weight is between `min_weight` and `max_weight` (0..1).
  * Methods: max_sharpe, min_volatility, efficient_risk, efficient_return (PyPortfolioOpt
    with cvxpy), equal_weight, inverse_volatility and HRP (implemented here, see `hrp_weights`).
  * Risk preference -> default method and cap: conservative = min_volatility, max 25% per
    stock; moderate = max_sharpe, max 35%; aggressive = efficient_risk, max 50%, target
    volatility three quarters of the way from the minimum-volatility portfolio to the most
    volatile single stock.
  * Fallbacks are explicit and reported: max Sharpe without a risk-free rate, or with no stock
    whose past average return beat it, uses min volatility; a target volatility below the
    minimum achievable uses min volatility; any other solver failure uses equal weights.
  * Discrete allocation: whole shares at the last (unadjusted) close, greedy rounding, the
    rest is reported as leftover cash.
Optimised weights describe the past. They are not forecasts or investment advice.
"""

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252
LOOKBACK_DAYS = 252  # trading days of history used to estimate returns and covariance
MIN_OBSERVATIONS = 120  # fewer common daily returns than this are too few to optimise on
EMA_SPAN = 126
CLEAN_CUTOFF = 1e-4  # weights below 0.01% are set to zero (solver noise)

METHODS = ("max_sharpe", "min_volatility", "efficient_risk", "efficient_return", "equal_weight",
           "inverse_volatility", "hrp")
METHOD_LABELS = {
    "max_sharpe": "maximum Sharpe ratio (best past return per unit of risk)",
    "min_volatility": "minimum volatility (smallest past price swings)",
    "efficient_risk": "highest past return for a chosen level of volatility",
    "efficient_return": "lowest volatility for a chosen target return",
    "equal_weight": "equal weights (the same amount in every stock)",
    "inverse_volatility": "inverse volatility (less money in more volatile stocks)",
    "hrp": "hierarchical risk parity (risk spread across groups of similar stocks)",
}
PREFERENCE_DEFAULTS = {
    "conservative": {"method": "min_volatility", "max_weight": 0.25},
    "moderate": {"method": "max_sharpe", "max_weight": 0.35},
    "aggressive": {"method": "efficient_risk", "max_weight": 0.50},
}
AGGRESSIVE_TARGET_POSITION = 0.75
OPTIMISATION_RULES = {
    "estimation": f"last {LOOKBACK_DAYS} trading days of adjusted closes; expected return = mean daily "
                  "return x 252; covariance = Ledoit-Wolf shrinkage x 252",
    "preference": "conservative: min volatility, max 25% per stock; moderate: max Sharpe, max 35%; "
                  "aggressive: efficient risk, max 50%",
    "short_selling": "not allowed (all weights 0% or more)",
    "fallback": "max Sharpe without a usable risk-free rate, or a too-low target volatility, uses min "
                "volatility; any other solver failure uses equal weights",
}


class OptimizationError(ValueError):
    """Invalid inputs or constraints that no method can satisfy (reported to the caller)."""


class _Fallback(Exception):
    def __init__(self, method: str, reason: str):
        super().__init__(reason)
        self.method, self.reason = method, reason


def _r(value: float | None, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


# ---------------------------------------------------------------- inputs
def price_matrix(prices_by_symbol: dict[str, pd.Series]) -> pd.DataFrame:
    """Adjusted closes side by side, only on dates where every stock traded."""
    frame = pd.DataFrame(prices_by_symbol).sort_index().dropna()
    if (frame <= 0).any().any():
        raise OptimizationError("prices must be positive")
    return frame


def estimation_window(prices: pd.DataFrame, lookback: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """The last `lookback` daily returns need `lookback + 1` prices."""
    return prices.iloc[-(lookback + 1):]


def expected_returns(prices: pd.DataFrame, model: str = "mean") -> pd.Series:
    from pypfopt import expected_returns as er

    if model == "mean":
        return er.mean_historical_return(prices, compounding=False, frequency=TRADING_DAYS)
    if model == "ema":
        return er.ema_historical_return(prices, compounding=False, span=EMA_SPAN, frequency=TRADING_DAYS)
    raise OptimizationError(f"unknown expected-return model '{model}'")


def covariance(prices: pd.DataFrame, model: str = "ledoit_wolf") -> pd.DataFrame:
    from pypfopt import risk_models

    if model == "ledoit_wolf":
        return risk_models.CovarianceShrinkage(prices, frequency=TRADING_DAYS).ledoit_wolf()
    if model == "sample":
        return risk_models.sample_cov(prices, frequency=TRADING_DAYS)
    raise OptimizationError(f"unknown covariance model '{model}'")


# ---------------------------------------------------------------- constraints
def check_bounds(n: int, min_weight: float, max_weight: float) -> None:
    if n < 2:
        raise OptimizationError("a portfolio needs at least 2 stocks")
    if min_weight < 0:
        raise OptimizationError("short positions are not allowed (minimum weight must be 0% or more)")
    if not 0 < max_weight <= 1 or min_weight > max_weight:
        raise OptimizationError("weights must satisfy 0% <= minimum <= maximum <= 100%")
    if n * max_weight < 1 - 1e-9:
        raise OptimizationError(f"a maximum of {max_weight:.0%} per stock cannot be met with {n} stocks "
                                f"(the weights could add up to only {n * max_weight:.0%}); raise the maximum "
                                f"to at least {math.ceil(10000 / n) / 100}% or add stocks")
    if n * min_weight > 1 + 1e-9:
        raise OptimizationError(f"a minimum of {min_weight:.0%} per stock cannot be met with {n} stocks "
                                f"(the weights would add up to {n * min_weight:.0%})")


def resolve_settings(risk_preference: str, n: int, method: str | None = None, min_weight: float | None = None,
                     max_weight: float | None = None) -> dict[str, Any]:
    """Risk preference -> method and bounds. Explicit choices override the defaults. A DEFAULT
    cap that cannot work with this few stocks is raised to 1/n (with a note); an EXPLICIT cap
    that cannot work is an error, because silently changing a user's constraint is wrong."""
    if risk_preference not in PREFERENCE_DEFAULTS:
        raise OptimizationError(f"unknown risk preference '{risk_preference}'")
    if method is not None and method not in METHODS:
        raise OptimizationError(f"unknown method '{method}'")
    defaults = PREFERENCE_DEFAULTS[risk_preference]
    notes = []
    lo = 0.0 if min_weight is None else min_weight
    if max_weight is None:
        hi = defaults["max_weight"]
        if n * hi < 1 - 1e-9:
            new_hi = math.ceil(10000 / n) / 10000
            notes.append(f"With {n} stocks the default {hi:.0%} maximum per stock cannot add up to 100%, so it was "
                         f"raised to {new_hi:.2%}" + (" (this forces equal weights)." if abs(new_hi * n - 1) < 1e-3
                                                     else "."))
            hi = new_hi
    else:
        hi = max_weight
    check_bounds(n, lo, hi)
    if not notes and (abs(n * hi - 1) < 1e-6 or abs(n * lo - 1) < 1e-6):
        notes.append(f"With {n} stocks and these limits the only possible allocation is equal weights.")
    return {"method": method or defaults["method"], "method_source": "requested" if method else "risk_preference",
            "min_weight": lo, "max_weight": hi, "notes": notes}


def apply_bounds(raw: pd.Series, lo: float, hi: float) -> pd.Series:
    """Scale non-negative raw scores to weights summing to 1 within [lo, hi] (water-filling:
    weights that break a bound are fixed at it and the rest is shared in proportion)."""
    raw = raw.clip(lower=0).astype(float)
    if raw.sum() <= 0:
        raw[:] = 1.0
    fixed = pd.Series(np.nan, index=raw.index)
    for _ in range(len(raw) + 1):
        free = fixed.isna()
        remaining = 1 - fixed[~free].sum()
        scores = raw[free]
        cand = scores / scores.sum() * remaining if scores.sum() > 0 else pd.Series(remaining / free.sum(), scores.index)
        over, under = cand[cand > hi + 1e-12], cand[cand < lo - 1e-12]
        if over.empty and under.empty:
            fixed[free] = cand
            break
        if not over.empty:
            fixed[over.index] = hi
        else:
            fixed[under.index] = lo
    return fixed / fixed.sum()


# ---------------------------------------------------------------- HRP
def hrp_weights(cov: pd.DataFrame) -> pd.Series:
    """Hierarchical risk parity (Lopez de Prado, 2016), written here because PyPortfolioOpt
    1.6's HRPOpt relies on a private SciPy attribute that SciPy 1.18 removed.

    1. Distance between stocks from their correlation: d = sqrt((1 - corr) / 2).
    2. Single-linkage clustering orders the stocks so similar ones sit next to each other.
    3. Recursive bisection: split the ordered list in halves and give each half money in
       inverse proportion to its variance (inverse-variance weights inside the half).
    With two stocks this equals inverse-variance weighting."""
    from scipy.cluster import hierarchy as sch
    from scipy.spatial.distance import squareform

    std = np.sqrt(np.diag(cov))
    corr = cov / np.outer(std, std)
    dist = np.sqrt(np.clip((1 - corr.to_numpy()) / 2, 0, 1))
    np.fill_diagonal(dist, 0)
    order = list(cov.index[sch.leaves_list(sch.linkage(squareform(dist, checks=False), "single"))])

    def cluster_variance(items: list[str]) -> float:
        sub = cov.loc[items, items].to_numpy()
        ivp = 1 / np.diag(sub)
        ivp /= ivp.sum()
        return float(ivp @ sub @ ivp)

    weights = pd.Series(1.0, index=order)
    clusters = [order]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) < 2:
                continue
            half = len(c) // 2
            left, right = c[:half], c[half:]
            v_left, v_right = cluster_variance(left), cluster_variance(right)
            alpha = 1 - v_left / (v_left + v_right)
            weights[left] *= alpha
            weights[right] *= 1 - alpha
            nxt += [left, right]
        clusters = nxt
    return weights.reindex(cov.index)


# ---------------------------------------------------------------- results
def performance(weights: pd.Series, mu: pd.Series, cov: pd.DataFrame, risk_free_rate_pct: float | None) -> dict:
    w = weights.reindex(mu.index).fillna(0).to_numpy()
    ret = float(w @ mu.to_numpy())
    vol = float(math.sqrt(max(w @ cov.to_numpy() @ w, 0)))
    sharpe = (ret - risk_free_rate_pct / 100) / vol if risk_free_rate_pct is not None and vol > 0 else None
    return {"annual_return_pct": _r(ret * 100), "annual_volatility_pct": _r(vol * 100),
            "sharpe_ratio": _r(sharpe, 3),
            "sharpe_reason": None if sharpe is not None else (
                "risk-free rate not configured" if risk_free_rate_pct is None else "volatility is zero")}


@dataclass
class OptimizationResult:
    weights: pd.Series
    method: str
    requested_method: str
    fallback_reason: str | None
    parameters: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    expected_returns_pct: dict[str, float | None] = field(default_factory=dict)
    volatility_pct: dict[str, float | None] = field(default_factory=dict)
    window: dict[str, Any] = field(default_factory=dict)

    def weights_pct(self) -> dict[str, float]:
        return {s: round(float(w) * 100, 2) for s, w in self.weights.items()}


def _solve(method: str, mu: pd.Series, cov: pd.DataFrame, lo: float, hi: float, rf_pct: float | None,
           target_volatility_pct: float | None, target_return_pct: float | None) -> tuple[pd.Series, dict]:
    n = len(mu)
    if method == "equal_weight":
        return pd.Series(1 / n, index=mu.index), {}
    if method == "inverse_volatility":
        return apply_bounds(1 / np.sqrt(pd.Series(np.diag(cov), index=cov.index)), lo, hi), {}
    if method == "hrp":
        return apply_bounds(hrp_weights(cov), lo, hi), {"linkage": "single", "bounds_applied_after_hrp": True}

    from pypfopt import EfficientFrontier

    def frontier():
        return EfficientFrontier(mu, cov, weight_bounds=(lo, hi))

    if method == "min_volatility":
        return pd.Series(frontier().min_volatility()), {}
    if method == "max_sharpe":
        if rf_pct is None:
            raise _Fallback("min_volatility", "the risk-free rate is not configured, so the maximum Sharpe ratio "
                                              "cannot be computed; the minimum-volatility portfolio was used instead")
        if (mu <= rf_pct / 100).all():
            raise _Fallback("min_volatility",
                            f"no stock's past average return beat the risk-free rate of {rf_pct}%, so a maximum "
                            "Sharpe portfolio is not defined; the minimum-volatility portfolio was used instead")
        return pd.Series(frontier().max_sharpe(risk_free_rate=rf_pct / 100)), {"risk_free_rate_pct": rf_pct}
    if method == "efficient_risk":
        w_min = pd.Series(frontier().min_volatility()).reindex(cov.index).to_numpy()
        min_vol = float(math.sqrt(max(w_min @ cov.to_numpy() @ w_min, 0)))
        if target_volatility_pct is None:
            max_asset = float(np.sqrt(np.diag(cov)).max())
            target = min_vol + AGGRESSIVE_TARGET_POSITION * (max_asset - min_vol)
            source = "default: 75% of the way from the minimum-volatility portfolio to the most volatile stock"
        else:
            target, source = target_volatility_pct / 100, "requested"
        if target < min_vol - 1e-6:
            raise _Fallback("min_volatility", f"the target volatility {target * 100:.2f}% is below the lowest "
                                              f"achievable {min_vol * 100:.2f}%; the minimum-volatility portfolio "
                                              "was used instead")
        weights = pd.Series(frontier().efficient_risk(target_volatility=max(target, min_vol + 1e-6)))
        return weights, {"target_volatility_pct": _r(target * 100), "target_source": source}
    if method == "efficient_return":
        if target_return_pct is None:
            raise OptimizationError("efficient_return needs a target return (target_return_pct)")
        weights = pd.Series(frontier().efficient_return(target_return=target_return_pct / 100))
        return weights, {"target_return_pct": target_return_pct}
    raise OptimizationError(f"unknown method '{method}'")


def _clean(weights: pd.Series, lo: float) -> pd.Series:
    w = weights.astype(float).clip(lower=0)
    if lo == 0:
        w[w < CLEAN_CUTOFF] = 0.0
    return w / w.sum()


def optimize(prices: pd.DataFrame, method: str, *, min_weight: float = 0.0, max_weight: float = 1.0,
             risk_free_rate_pct: float | None = None, target_volatility_pct: float | None = None,
             target_return_pct: float | None = None, returns_model: str = "mean",
             covariance_model: str = "ledoit_wolf", lookback: int = LOOKBACK_DAYS) -> OptimizationResult:
    """Weights for `prices` (adjusted closes, common dates). Only the last `lookback` returns
    are used, so the backtest can call this with history up to a past date."""
    if method not in METHODS:
        raise OptimizationError(f"unknown method '{method}'")
    window = estimation_window(prices, lookback)
    if len(window) - 1 < MIN_OBSERVATIONS:
        raise OptimizationError(f"only {len(window) - 1} common daily returns (need {MIN_OBSERVATIONS})")
    check_bounds(len(window.columns), min_weight, max_weight)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mu = expected_returns(window, returns_model)
        cov = covariance(window, covariance_model)
        used, reason, params = method, None, {}
        try:
            raw, params = _solve(method, mu, cov, min_weight, max_weight, risk_free_rate_pct,
                                 target_volatility_pct, target_return_pct)
        except _Fallback as fb:
            used, reason = fb.method, fb.reason
            raw, params = _solve(used, mu, cov, min_weight, max_weight, risk_free_rate_pct, None, None)
        except OptimizationError:
            raise
        except Exception as exc:  # solver failure (cvxpy / PyPortfolioOpt): reported, never hidden
            used, reason = "equal_weight", (f"the {method} optimisation could not be solved "
                                            f"({exc.__class__.__name__}); equal weights were used instead")
            raw, params = _solve(used, mu, cov, min_weight, max_weight, None, None, None)
    weights = _clean(raw.reindex(window.columns).fillna(0), min_weight)
    return OptimizationResult(
        weights=weights, method=used, requested_method=method, fallback_reason=reason, parameters=params,
        expected=performance(weights, mu, cov, risk_free_rate_pct),
        expected_returns_pct={s: _r(v * 100) for s, v in mu.items()},
        volatility_pct={s: _r(math.sqrt(cov.loc[s, s]) * 100) for s in cov.index},
        window={"from": window.index[0].strftime("%Y-%m-%d"), "to": window.index[-1].strftime("%Y-%m-%d"),
                "observations": len(window) - 1, "returns_model": returns_model,
                "covariance_model": covariance_model},
    )


# ---------------------------------------------------------------- discrete allocation
def discrete_allocation(weights: pd.Series, prices: pd.Series, capital: float) -> dict[str, Any]:
    """Whole shares at `prices` (last close). Step 1: floor of each target amount. Step 2:
    repeatedly buy one share of the stock furthest BELOW its target that the remaining cash
    can still pay for. The rest is leftover cash."""
    if capital <= 0:
        raise OptimizationError("investment amount must be positive")
    prices = prices.reindex(weights.index)
    if prices.isna().any() or (prices <= 0).any():
        raise OptimizationError("a last price is missing for at least one stock")
    target = weights * capital
    shares = np.floor(target / prices).astype(int)
    cash = capital - float((shares * prices).sum())
    while True:
        deficit = target - shares * prices
        affordable = deficit[(prices <= cash + 1e-9) & (deficit > 0) & (weights > 0)]
        if affordable.empty:
            break
        pick = affordable.idxmax()
        shares[pick] += 1
        cash -= float(prices[pick])
    amounts = shares * prices
    invested = float(amounts.sum())
    return {
        "shares": {s: int(v) for s, v in shares.items()},
        "amount_inr": {s: round(float(v), 2) for s, v in amounts.items()},
        "actual_weight_pct": {s: (round(float(v) / capital * 100, 2)) for s, v in amounts.items()},
        "invested_inr": round(invested, 2),
        "leftover_cash_inr": round(capital - invested, 2),
        "leftover_pct": round((capital - invested) / capital * 100, 2),
    }


def weights_to_percent(weights: pd.Series) -> dict[str, float]:
    """Percent weights rounded to 2 decimals that add up to EXACTLY 100 (the rounding
    difference goes to the largest weight), as the `portfolios` schema requires."""
    pct = (weights * 100).round(2)
    pct[pct.idxmax()] = round(pct[pct.idxmax()] + round(100 - pct.sum(), 2), 2)
    return {s: float(v) for s, v in pct.items()}
