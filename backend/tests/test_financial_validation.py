"""Financial validation on a FIXED REAL dataset (Phase 13, task 13.1.5).

Every production metric is recomputed here by an independent reference written from the textbook
definition: plain Python loops, or NumPy and SciPy where a loop is impractical. The references do
not call pandas rolling/ewm, PyPortfolioOpt, cvxpy or scikit-learn, which the production code uses.

The dataset (two years of daily prices for four NSE stocks and the NIFTY 50, and three companies'
annual statements) is made by scripts/freeze_validation_dataset.py and lives in
data/historical/validation/. It is not committed (Yahoo data is not redistributed), so these tests
are skipped until the script has been run once. The manifest's SHA-256 hashes pin the exact data.
"""

import hashlib
import json
import math
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

from app.analysis import backtesting as bt
from app.analysis import fundamentals as fa
from app.analysis import optimization as opt
from app.analysis import risk_metrics as rm
from app.analysis import technical_indicators as ti
from app.config import PROJECT_ROOT
from app.data.data_validator import validate_ohlcv
from tests.reference_indicators import ref_ema, ref_macd, ref_rsi, ref_sma

DATA = PROJECT_ROOT / "data" / "historical" / "validation"
MANIFEST = DATA / "manifest.json"
pytestmark = pytest.mark.skipif(not MANIFEST.exists(),
                                reason="no validation dataset: run scripts/freeze_validation_dataset.py once")
STOCKS = ("RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS")
BENCH = "^NSEI"
RFR_PCT = 5.4  # any fixed rate works for comparing two implementations


def close_to(got, want, digits):
    """Production rounds to `digits`; the reference is unrounded."""
    assert got is not None and want is not None
    assert abs(got - want) <= 0.5 * 10 ** -digits + 1e-9, (got, want)


# ---------------------------------------------------------------- the dataset
@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def frames(manifest):
    end = pd.Timestamp(manifest["end_date"])
    out = {}
    for name, meta in manifest["files"].items():
        if name.startswith("prices_"):
            raw = pd.read_csv(DATA / name, index_col="date", parse_dates=True)
            # The same validation as the app (it may drop bad rows) before any metric is computed.
            frame, report = validate_ohlcv(raw, meta["symbol"], now=(end + timedelta(days=1)).to_pydatetime(),
                                           min_rows=20)
            out[meta["symbol"]] = frame
    return out


@pytest.fixture(scope="module")
def statements(manifest):
    return {meta["symbol"]: json.loads((DATA / name).read_text(encoding="utf-8"))
            for name, meta in manifest["files"].items() if name.startswith("statements_")}


def test_dataset_is_the_frozen_one(manifest, frames):
    for name, meta in manifest["files"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == meta["sha256"], name
    assert set(frames) == {*STOCKS, BENCH}
    for sym, frame in frames.items():
        assert len(frame) >= 480 and frame.index.is_monotonic_increasing, sym


# ---------------------------------------------------------------- independent references
def ref_returns(p):
    return [p[i] / p[i - 1] - 1 for i in range(1, len(p))]


def ref_mean(xs):
    return sum(xs) / len(xs)


def ref_std(xs):
    m = ref_mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ref_cov(a, b):
    ma, mb = ref_mean(a), ref_mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / (len(a) - 1)


def ref_corr(a, b):
    return ref_cov(a, b) / (ref_std(a) * ref_std(b))


def ref_skew(xs):
    """Adjusted Fisher-Pearson skewness (the sample statistic, not the population one)."""
    n, m = len(xs), ref_mean(xs)
    m2 = sum((x - m) ** 2 for x in xs) / n
    m3 = sum((x - m) ** 3 for x in xs) / n
    return math.sqrt(n * (n - 1)) / (n - 2) * m3 / m2 ** 1.5


def ref_excess_kurtosis(xs):
    """Unbiased sample excess kurtosis (G2)."""
    n, m = len(xs), ref_mean(xs)
    m2 = sum((x - m) ** 2 for x in xs) / n
    m4 = sum((x - m) ** 4 for x in xs) / n
    g2 = m4 / m2 ** 2 - 3
    return (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * g2 + 6)


def ref_drawdown(dates, p):
    peak, peak_i, worst, worst_peak_i, worst_i = p[0], 0, 0.0, None, None
    for i, v in enumerate(p):
        if v > peak:
            peak, peak_i = v, i
        dd = v / peak - 1
        if dd < worst:
            worst, worst_peak_i, worst_i = dd, peak_i, i
    if worst_i is None:
        return {"pct": 0.0}
    recovery = next((i for i in range(worst_i, len(p)) if p[i] >= p[worst_peak_i]), None)
    return {"pct": worst * 100, "peak": dates[worst_peak_i], "trough": dates[worst_i],
            "recovery": dates[recovery] if recovery is not None else None}


def ref_ledoit_wolf(returns: np.ndarray) -> np.ndarray:
    """Ledoit and Wolf (2004) shrinkage towards a constant-variance target, from the paper."""
    t, n = returns.shape
    x = returns - returns.mean(axis=0)
    s = x.T @ x / t
    mu = np.trace(s) / n
    target = mu * np.eye(n)
    d2 = np.sum((s - target) ** 2) / n
    b2_bar = sum(np.sum((np.outer(row, row) - s) ** 2) for row in x) / t ** 2 / n
    shrink = min(b2_bar, d2) / d2
    return shrink * target + (1 - shrink) * s


def ref_min_volatility(cov, lo, hi):
    n = len(cov)
    res = minimize(lambda w: w @ cov @ w, np.full(n, 1 / n), method="SLSQP", bounds=[(lo, hi)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], options={"ftol": 1e-15, "maxiter": 500})
    assert res.success, res.message
    return res.x


def ref_max_sharpe(mu, cov, rf, lo, hi):
    n = len(cov)
    res = minimize(lambda w: -(w @ mu - rf) / math.sqrt(w @ cov @ w), np.full(n, 1 / n), method="SLSQP",
                   bounds=[(lo, hi)] * n, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"ftol": 1e-15, "maxiter": 500})
    assert res.success, res.message
    return res.x


# ---------------------------------------------------------------- technical indicators
@pytest.mark.parametrize("symbol", [*STOCKS, BENCH])
def test_indicators_match_the_references(frames, symbol):
    frame = frames[symbol]
    closes = frame["close"].tolist()
    ind = ti.compute_indicators(frame)

    def same(series, reference, tol=1e-8):
        for got, want in zip(series.tolist(), reference, strict=True):
            assert (math.isnan(got) if want is None else got == pytest.approx(want, rel=tol, abs=tol))

    for n in (20, 50, 200):
        same(ind[f"sma_{n}"], ref_sma(closes, n))
    same(ind["ema_12"], ref_ema(closes, 12))
    same(ind["ema_26"], ref_ema(closes, 26))
    same(ind["rsi_14"], ref_rsi(closes, 14))
    line, signal = ref_macd(closes)
    same(ind["macd"], line)
    same(ind["macd_signal"], signal)
    # Bollinger bands: SMA20 +/- 2 population standard deviations of the last 20 closes
    for i in range(19, len(closes)):
        win = closes[i - 19:i + 1]
        m = sum(win) / 20
        sd = math.sqrt(sum((c - m) ** 2 for c in win) / 20)
        assert ind["bb_upper"].iloc[i] == pytest.approx(m + 2 * sd, rel=1e-9)
        assert ind["bb_lower"].iloc[i] == pytest.approx(m - 2 * sd, rel=1e-9)


@pytest.mark.parametrize("symbol", STOCKS)
def test_period_return_and_benchmark_comparison(frames, symbol):
    stock, bench = frames[symbol], frames[BENCH]
    p = stock["adjusted_close"].tolist()
    close_to(ti.period_return_pct(stock["adjusted_close"]), (p[-1] / p[0] - 1) * 100, 2)
    common = sorted(set(stock.index) & set(bench.index))
    s0, s1 = stock.loc[common[0], "adjusted_close"], stock.loc[common[-1], "adjusted_close"]
    b0, b1 = bench.loc[common[0], "adjusted_close"], bench.loc[common[-1], "adjusted_close"]
    cmp = ti.benchmark_comparison(stock, bench, BENCH)
    assert cmp["trading_days"] == len(common)
    close_to(cmp["stock_return_pct"], (s1 / s0 - 1) * 100, 2)
    close_to(cmp["benchmark_return_pct"], (b1 / b0 - 1) * 100, 2)
    # relative = difference of the two ROUNDED returns (what the report shows side by side)
    assert cmp["relative_pct"] == round(cmp["stock_return_pct"] - cmp["benchmark_return_pct"], 2)


# ---------------------------------------------------------------- risk metrics
@pytest.mark.parametrize("symbol", STOCKS)
def test_return_statistics_volatility_and_sharpe(frames, symbol):
    prices = frames[symbol]["adjusted_close"]
    r = ref_returns(prices.tolist())
    returns = rm.daily_returns(prices)
    assert returns.tolist() == pytest.approx(r, rel=1e-12)
    close_to(rm.annualized_volatility_pct(returns), ref_std(r) * math.sqrt(252) * 100, 2)
    close_to(rm.annualized_return_pct(returns), ref_mean(r) * 252 * 100, 2)
    dist = rm.return_distribution(returns)
    close_to(dist["mean_daily_pct"], ref_mean(r) * 100, 4)
    close_to(dist["std_daily_pct"], ref_std(r) * 100, 4)
    close_to(dist["skewness"], ref_skew(r), 3)
    close_to(dist["excess_kurtosis"], ref_excess_kurtosis(r), 3)
    close_to(dist["positive_days_pct"], sum(x > 0 for x in r) / len(r) * 100, 1)
    sharpe = rm.sharpe_ratio(returns, {"value_pct": RFR_PCT})
    close_to(sharpe["value"], (ref_mean(r) * 252 - RFR_PCT / 100) / (ref_std(r) * math.sqrt(252)), 3)


@pytest.mark.parametrize("symbol", STOCKS)
def test_beta_against_the_nifty_50(frames, symbol):
    s, b = frames[symbol]["adjusted_close"], frames[BENCH]["adjusted_close"]
    rs, rb = rm.daily_returns(s), rm.daily_returns(b)
    common = sorted(set(rs.index) & set(rb.index))
    xs, ys = [rs[d] for d in common], [rb[d] for d in common]
    result = rm.beta(rs, rb)
    assert result["observations"] == len(common)
    close_to(result["value"], ref_cov(xs, ys) / ref_cov(ys, ys), 3)
    close_to(result["correlation_with_benchmark"], ref_corr(xs, ys), 3)


@pytest.mark.parametrize("symbol", [*STOCKS, BENCH])
def test_max_drawdown(frames, symbol):
    prices = frames[symbol]["adjusted_close"]
    want = ref_drawdown([d.strftime("%Y-%m-%d") for d in prices.index], prices.tolist())
    got = rm.max_drawdown(prices)
    close_to(got["max_drawdown_pct"], want["pct"], 2)
    if want["pct"] < 0:
        assert (got["peak_date"], got["trough_date"], got["recovery_date"]) == \
            (want["peak"], want["trough"], want["recovery"])


def test_correlation_matrix_and_concentration(frames):
    returns = {s: rm.daily_returns(frames[s]["adjusted_close"]) for s in STOCKS}
    common = sorted(set.intersection(*(set(r.index) for r in returns.values())))
    got = rm.correlation_matrix(returns)
    assert got["observations"] == len(common)
    for a in STOCKS:
        for b in STOCKS:
            close_to(got["matrix"][a][b], ref_corr([returns[a][d] for d in common], [returns[b][d] for d in common]), 3)
    weights = {"RELIANCE.NS": 40, "TCS.NS": 30, "INFY.NS": 20, "HDFCBANK.NS": 10}
    conc = rm.concentration(weights)
    hhi = sum((w / 100) ** 2 for w in weights.values())
    close_to(conc["hhi"], hhi, 4)
    close_to(conc["effective_number_of_stocks"], 1 / hhi, 2)


# ---------------------------------------------------------------- portfolio optimisation
@pytest.fixture(scope="module")
def prices(frames):
    return opt.price_matrix({s: frames[s]["adjusted_close"] for s in STOCKS})


@pytest.fixture(scope="module")
def window(prices):
    """The latest year, as used for today's allocation."""
    return opt.estimation_window(prices)


@pytest.fixture(scope="module", params=["first_year", "latest_year"])
def any_window(request, prices):
    return prices.iloc[:253] if request.param == "first_year" else opt.estimation_window(prices)


@pytest.fixture(scope="module")
def first_year(prices):
    """The first year of the dataset. Max Sharpe needs a stock whose past mean return beats the
    risk-free rate; in the latest year of the frozen data (Nov 2025 - Nov 2026) none did."""
    return prices.iloc[:253]


def window_returns(window):
    cols = [window[c].tolist() for c in window.columns]
    return np.array([ref_returns(c) for c in cols]).T


def test_expected_returns_and_covariances(any_window):
    window = any_window
    r = window_returns(window)
    mu = opt.expected_returns(window)
    assert mu.to_numpy() == pytest.approx(r.mean(axis=0) * 252, rel=1e-10)
    sample = opt.covariance(window, "sample")
    assert sample.to_numpy() == pytest.approx(np.cov(r, rowvar=False, ddof=1) * 252, rel=1e-10)
    lw = opt.covariance(window, "ledoit_wolf")
    assert lw.to_numpy() == pytest.approx(ref_ledoit_wolf(r) * 252, rel=1e-8)


@pytest.mark.parametrize("cov_model", ["sample", "ledoit_wolf"])
@pytest.mark.parametrize("hi", [1.0, 0.35])
def test_min_volatility_matches_an_independent_solver(any_window, cov_model, hi):
    window = any_window
    cov = opt.covariance(window, cov_model).to_numpy()
    got = opt.optimize(window, "min_volatility", max_weight=hi, covariance_model=cov_model)
    want = ref_min_volatility(cov, 0.0, hi)
    w = got.weights.reindex(window.columns).to_numpy()
    assert w.sum() == pytest.approx(1) and (w <= hi + 1e-6).all() and (w >= 0).all()
    # The same minimum (to 1e-6 of variance) and the same weights (to 0.5 percentage points)
    assert math.sqrt(w @ cov @ w) == pytest.approx(math.sqrt(want @ cov @ want), abs=1e-6)
    assert w == pytest.approx(want, abs=5e-3)


@pytest.mark.parametrize("hi", [1.0, 0.5])
def test_max_sharpe_matches_an_independent_solver(first_year, hi):
    window = first_year
    mu = opt.expected_returns(window)
    assert (mu > RFR_PCT / 100).sum() >= 2  # max Sharpe is defined and not a single stock
    cov = opt.covariance(window).to_numpy()
    got = opt.optimize(window, "max_sharpe", max_weight=hi, risk_free_rate_pct=RFR_PCT)
    assert got.method == "max_sharpe"
    want = ref_max_sharpe(mu.to_numpy(), cov, RFR_PCT / 100, 0.0, hi)
    w = got.weights.reindex(window.columns).to_numpy()

    def sharpe(x):
        return (x @ mu.to_numpy() - RFR_PCT / 100) / math.sqrt(x @ cov @ x)

    assert sharpe(w) == pytest.approx(sharpe(want), abs=1e-4)
    assert w == pytest.approx(want, abs=1e-2)
    close_to(got.expected["sharpe_ratio"], sharpe(w), 3)


def test_discrete_allocation_spends_within_the_capital(frames, window):
    weights = pd.Series(0.25, index=window.columns)
    last = window.iloc[-1]
    alloc = opt.discrete_allocation(weights, last, 100_000)
    spent = sum(n * float(last[s]) for s, n in alloc["shares"].items())
    assert spent <= 100_000 + 1e-6 and alloc["leftover_cash_inr"] == pytest.approx(100_000 - spent, abs=0.01)


# ---------------------------------------------------------------- backtest
def ref_simulate(prices, rebalance_rows, weights, cost_bps, capital):
    """Hold whole fractions of shares; at each rebalance row, sell everything at that close,
    pay costs on the turnover, and buy the target weights."""
    cols = list(prices.columns)
    holdings = dict.fromkeys(cols, 0.0)
    values = []
    for i in range(rebalance_rows[0], len(prices)):
        row = prices.iloc[i]
        value = sum(holdings[c] * row[c] for c in cols) if i > rebalance_rows[0] else capital
        if i in rebalance_rows:
            current = {c: (holdings[c] * row[c] / value if i > rebalance_rows[0] else 0.0) for c in cols}
            turnover = sum(abs(weights[c] - current[c]) for c in cols)
            value -= value * turnover * cost_bps / 10_000
            holdings = {c: value * weights[c] / row[c] for c in cols}
        values.append(value)
    return values


def ref_quarter_ends(index, start):
    rows = [start]
    for i in range(start + 1, len(index) - 1):
        if (index[i].year, (index[i].month - 1) // 3) != (index[i + 1].year, (index[i + 1].month - 1) // 3):
            rows.append(i)
    return rows


def test_backtest_equity_curve_matches_a_share_based_simulation(frames, prices):
    weights = {"RELIANCE.NS": 0.4, "TCS.NS": 0.3, "INFY.NS": 0.2, "HDFCBANK.NS": 0.1}
    start = 252
    rows = bt.rebalance_positions(prices.index, start, "quarterly")
    assert rows == ref_quarter_ends(prices.index, start)
    targets = {r: pd.Series(weights) for r in rows}
    curve, _ = bt.simulate(prices, targets, start, 10, 100_000)
    want = ref_simulate(prices, rows, weights, 10, 100_000)
    assert curve.tolist() == pytest.approx(want, rel=1e-10)

    result = bt.run_backtest(prices, lambda h: (pd.Series(weights), "fixed", None), lookback=start,
                             rebalance="quarterly", cost_bps=10, risk_free_rate_pct=RFR_PCT,
                             benchmark=frames[BENCH]["adjusted_close"])
    close_to(result["end_value"], want[-1], 2)
    close_to(result["total_return_pct"], (want[-1] / 100_000 - 1) * 100, 2)
    years = (prices.index[-1] - prices.index[start]).days / 365.25
    close_to(result["cagr_pct"], ((want[-1] / 100_000) ** (1 / years) - 1) * 100, 2)
    daily = ref_returns(want)
    close_to(result["volatility_pct"], ref_std(daily) * math.sqrt(252) * 100, 2)


# ---------------------------------------------------------------- fundamentals
def item(st, statement, period, *names):
    values = st[statement].get(period, {})
    return next((float(values[n]) for n in names if values.get(n) is not None), None)


@pytest.mark.parametrize("symbol", ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"])
def test_fundamental_ratios_from_the_annual_statements(frames, statements, symbol):
    st = statements[symbol]
    inc = sorted(st["income_statement"], reverse=True)
    bal = sorted(st["balance_sheet"], reverse=True)
    price = float(frames[symbol]["close"].iloc[-1])
    m = fa.compute_fundamentals(st, price, is_bank=symbol == "HDFCBANK.NS")
    p0, b0, b1 = inc[0], bal[0], bal[1] if len(bal) > 1 else None

    def check(key, want, digits=2):
        if want is None:
            assert m[key].value is None, key
        else:
            close_to(m[key].value, want, digits)

    revenue, net = item(st, "income_statement", p0, "Total Revenue"), item(st, "income_statement", p0, "Net Income")
    eq0 = item(st, "balance_sheet", b0, "Stockholders Equity")
    eq1 = item(st, "balance_sheet", b1, "Stockholders Equity") if b1 else None
    as0, as1 = item(st, "balance_sheet", b0, "Total Assets"), item(st, "balance_sheet", b1, "Total Assets") if b1 else None
    avg_eq = (eq0 + eq1) / 2 if eq1 is not None else eq0
    avg_as = (as0 + as1) / 2 if as1 is not None else as0
    check("roe_pct", net / avg_eq * 100)
    check("roa_pct", net / avg_as * 100)
    check("net_margin_pct", net / revenue * 100)
    op = item(st, "income_statement", p0, "Operating Income")
    check("operating_margin_pct", op / revenue * 100 if op is not None else None)
    debt = item(st, "balance_sheet", b0, "Total Debt")
    equity = item(st, "balance_sheet", b0, "Stockholders Equity", "Common Stock Equity")
    check("debt_to_equity", debt / equity if debt is not None else None)
    ca, cl = item(st, "balance_sheet", b0, "Current Assets"), item(st, "balance_sheet", b0, "Current Liabilities")
    check("current_ratio", ca / cl if ca is not None and cl else None)
    eps = item(st, "income_statement", p0, "Diluted EPS", "Basic EPS")
    check("pe", price / eps if eps and eps > 0 else None)
    shares = item(st, "balance_sheet", b0, "Ordinary Shares Number", "Share Issued")
    check("pb", price / (equity / shares) if shares and equity > 0 else None)

    years = [p for p in inc if item(st, "income_statement", p, "Total Revenue") is not None]
    revs = [item(st, "income_statement", p, "Total Revenue") for p in years]
    check("revenue_growth_yoy_pct", (revs[0] / revs[1] - 1) * 100)
    if len(revs) >= 3:
        check("revenue_cagr_pct", ((revs[0] / revs[-1]) ** (1 / (len(revs) - 1)) - 1) * 100)


def test_max_sharpe_falls_back_to_min_volatility_in_the_latest_year(window):
    """Real case from the frozen data: no stock's mean return beat the rate, so the documented
    fallback is used and reported (never a silent change of method)."""
    got = opt.optimize(window, "max_sharpe", risk_free_rate_pct=RFR_PCT)
    assert got.method == "min_volatility" and "risk-free rate" in got.fallback_reason
    want = ref_min_volatility(opt.covariance(window).to_numpy(), 0.0, 1.0)
    assert got.weights.reindex(window.columns).to_numpy() == pytest.approx(want, abs=5e-3)
