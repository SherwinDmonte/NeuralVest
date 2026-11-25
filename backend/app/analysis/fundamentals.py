"""Fundamental ratios from annual financial statements (computed in Python, never by the LLM).

Every metric is returned as a `Metric`: value, unit, the statement period it uses, the
formula, the data source, and when it cannot be computed, `value=None` with a reason.
Missing values are never estimated (spec §5, Agent 3).

Conventions (documented so results are reproducible):
  * Statements are annual (Indian companies mostly report for the year ending 31 March).
  * EPS is the company-reported diluted EPS (basic EPS if diluted is missing).
  * P/E and P/B use the latest available close price and the latest annual statements
    (a "trailing annual" ratio, not trailing-twelve-months).
  * ROE and ROA use the AVERAGE of opening and closing equity/assets when the previous
    year is available, otherwise the closing value (stated in the formula).
  * Growth: year-over-year for the latest year, plus CAGR over all available years.
  * Banks: current ratio and operating margin are not applicable (banks do not report
    current assets/liabilities or operating income), and debt-to-equity is not comparable
    with non-financial companies (deposits/borrowings are their raw material).
"""

from dataclasses import asdict, dataclass, field
from typing import Any

INCOME, BALANCE = "income_statement", "balance_sheet"
STRUCTURAL_CHANGE = 0.5  # a one-year change above 50% is flagged (merger/acquisition)


@dataclass
class Metric:
    value: float | None
    unit: str  # "%", "x", "INR"
    period: str | None
    formula: str
    reason: str | None = None  # why value is None (or a caveat)
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get(statements: dict, statement: str, period: str | None, *items: str) -> tuple[float | None, str | None]:
    """First available line item (in the given order) for one period: (value, item name)."""
    if period is None:
        return None, None
    values = statements.get(statement, {}).get(period, {})
    for item in items:
        if values.get(item) is not None:
            return float(values[item]), item
    return None, None


def _periods(statements: dict, statement: str) -> list[str]:
    """Period end dates (YYYY-MM-DD), newest first. Sorted here rather than trusting the dict
    order, which a JSON round trip with sorted keys reverses (found in Phase 13)."""
    return sorted(statements.get(statement, {}), reverse=True)


def _fy(period: str | None) -> str | None:
    return f"FY{period[:4]} (year ended {period})" if period else None


def _ratio(numerator: float | None, denominator: float | None, scale: float = 1.0) -> tuple[float | None, str | None]:
    if numerator is None or denominator is None:
        return None, "required statement items are not available"
    if denominator == 0:
        return None, "denominator is zero"
    return round(numerator / denominator * scale, 4), None


def _average(statements: dict, statement: str, period: str, item: str) -> tuple[float | None, str]:
    periods = _periods(statements, statement)
    current, _ = _get(statements, statement, period, item)
    idx = periods.index(period) if period in periods else -1
    previous, _ = _get(statements, statement, periods[idx + 1], item) if 0 <= idx < len(periods) - 1 else (None, None)
    if current is not None and previous is not None:
        return (current + previous) / 2, f"average of opening and closing {item}"
    return current, f"closing {item} (previous year unavailable)"


# ---------------------------------------------------------------- growth
def growth_metrics(statements: dict, item: str, label: str) -> dict[str, Metric]:
    periods = [p for p in _periods(statements, INCOME) if _get(statements, INCOME, p, item)[0] is not None]
    yoy = Metric(None, "%", _fy(periods[0]) if periods else None, f"({label} this year / last year - 1) x 100")
    cagr = Metric(None, "%", None, f"((latest {label} / earliest {label}) ^ (1 / years) - 1) x 100")
    if len(periods) < 2:
        yoy.reason = cagr.reason = f"need at least two years of {label}"
        return {"yoy": yoy, "cagr": cagr}

    latest, prev = (_get(statements, INCOME, p, item)[0] for p in periods[:2])
    yoy.inputs = {"latest": latest, "previous": prev, "previous_period": periods[1]}
    if prev <= 0:
        yoy.reason = f"previous year's {label} is zero or negative; growth is not meaningful"
    else:
        yoy.value = round((latest / prev - 1) * 100, 2)

    earliest = _get(statements, INCOME, periods[-1], item)[0]
    years = len(periods) - 1
    cagr.period = f"FY{periods[-1][:4]}-FY{periods[0][:4]}"
    cagr.inputs = {"latest": latest, "earliest": earliest, "years": years}
    if earliest <= 0 or latest <= 0:
        cagr.reason = f"{label} is zero or negative in the first or last year; CAGR is not meaningful"
    elif years < 2:
        cagr.reason = "need at least three years for a multi-year growth rate"
    else:
        cagr.value = round(((latest / earliest) ** (1 / years) - 1) * 100, 2)
        # A one-year jump above 50% usually means a merger, demerger or acquisition
        # (e.g. HDFC Bank + HDFC Ltd, July 2023): the value is kept but flagged.
        values = [_get(statements, INCOME, p, item)[0] for p in periods]
        jumps = [periods[i] for i in range(len(values) - 1)
                 if values[i + 1] > 0 and abs(values[i] / values[i + 1] - 1) > STRUCTURAL_CHANGE]
        if jumps:
            cagr.reason = (f"{label} changed by more than {int(STRUCTURAL_CHANGE * 100)}% in one year "
                           f"({', '.join('FY' + p[:4] for p in jumps)}), possibly a merger, demerger or "
                           "acquisition; multi-year growth may not be comparable")
    return {"yoy": yoy, "cagr": cagr}


# ---------------------------------------------------------------- all metrics
def compute_fundamentals(statements: dict, price: float | None, is_bank: bool = False,
                         currencies_match: bool | None = True) -> dict[str, Metric]:
    """All Phase 7 metrics for the latest annual period."""
    inc_period = next(iter(_periods(statements, INCOME)), None)
    bal_period = next(iter(_periods(statements, BALANCE)), None)
    m: dict[str, Metric] = {}

    rev_growth = growth_metrics(statements, "Total Revenue", "revenue")
    np_growth = growth_metrics(statements, "Net Income", "net profit")
    m["revenue_growth_yoy_pct"], m["revenue_cagr_pct"] = rev_growth["yoy"], rev_growth["cagr"]
    m["net_profit_growth_yoy_pct"], m["net_profit_cagr_pct"] = np_growth["yoy"], np_growth["cagr"]

    revenue, _ = _get(statements, INCOME, inc_period, "Total Revenue")
    net_income, _ = _get(statements, INCOME, inc_period, "Net Income")
    op_income, _ = _get(statements, INCOME, inc_period, "Operating Income")
    eps, eps_item = _get(statements, INCOME, inc_period, "Diluted EPS", "Basic EPS")
    equity, _ = _get(statements, BALANCE, bal_period, "Stockholders Equity", "Common Stock Equity")
    shares, shares_item = _get(statements, BALANCE, bal_period, "Ordinary Shares Number", "Share Issued")
    debt, _ = _get(statements, BALANCE, bal_period, "Total Debt")
    cur_assets, _ = _get(statements, BALANCE, bal_period, "Current Assets")
    cur_liab, _ = _get(statements, BALANCE, bal_period, "Current Liabilities")
    inc_fy, bal_fy = _fy(inc_period), _fy(bal_period)

    # --- per-share and valuation
    m["eps"] = Metric(eps, "INR", inc_fy, f"reported {eps_item or 'diluted EPS'}",
                      None if eps is not None else "EPS not reported", {"source_item": eps_item})
    pe = Metric(None, "x", inc_fy, "latest close price / EPS", inputs={"price": price, "eps": eps})
    if currencies_match is False:
        pe.reason = "price and financial statements use different currencies"
    elif price is None or eps is None:
        pe.reason = "price or EPS not available"
    elif eps <= 0:
        pe.reason = "EPS is zero or negative (loss-making); P/E is not meaningful"
    else:
        pe.value = round(price / eps, 2)
    m["pe"] = pe

    pb = Metric(None, "x", bal_fy, "latest close price / (shareholders' equity / shares outstanding)",
                inputs={"price": price, "equity": equity, "shares": shares, "shares_item": shares_item})
    if currencies_match is False:
        pb.reason = "price and financial statements use different currencies"
    elif price is None or equity is None or not shares:
        pb.reason = "price, equity or share count not available"
    elif equity <= 0:
        pb.reason = "shareholders' equity is zero or negative; P/B is not meaningful"
    else:
        pb.value = round(price / (equity / shares), 2)
    m["pb"] = pb

    # --- returns (average equity/assets)
    avg_equity, eq_note = _average(statements, BALANCE, bal_period, "Stockholders Equity") if bal_period else (None, "")
    avg_assets, as_note = _average(statements, BALANCE, bal_period, "Total Assets") if bal_period else (None, "")
    roe_value, roe_reason = _ratio(net_income, avg_equity, 100)
    if avg_equity is not None and avg_equity < 0:
        roe_value, roe_reason = None, "shareholders' equity is negative; ROE is not meaningful"
    m["roe_pct"] = Metric(roe_value, "%", inc_fy, f"net income / {eq_note} x 100", roe_reason,
                          {"net_income": net_income, "equity": avg_equity})
    roa_value, roa_reason = _ratio(net_income, avg_assets, 100)
    m["roa_pct"] = Metric(roa_value, "%", inc_fy, f"net income / {as_note} x 100", roa_reason,
                          {"net_income": net_income, "assets": avg_assets})

    # --- balance-sheet strength
    de_value, de_reason = _ratio(debt, equity)
    if equity is not None and equity < 0:
        de_value, de_reason = None, "shareholders' equity is negative; debt-to-equity is not meaningful"
    elif is_bank and de_value is not None:
        de_reason = "for banks, borrowings are part of normal business; not comparable with other companies"
    m["debt_to_equity"] = Metric(de_value, "x", bal_fy, "total debt / shareholders' equity", de_reason,
                                 {"total_debt": debt, "equity": equity})
    cr_value, cr_reason = _ratio(cur_assets, cur_liab)
    if is_bank and cr_value is None:
        cr_reason = "not applicable: banks do not report current assets and liabilities"
    m["current_ratio"] = Metric(cr_value, "x", bal_fy, "current assets / current liabilities", cr_reason,
                                {"current_assets": cur_assets, "current_liabilities": cur_liab})

    # --- margins
    om_value, om_reason = _ratio(op_income, revenue, 100)
    if is_bank and om_value is None:
        om_reason = "not applicable: banks do not report operating income"
    m["operating_margin_pct"] = Metric(om_value, "%", inc_fy, "operating income / total revenue x 100", om_reason,
                                       {"operating_income": op_income, "revenue": revenue})
    nm_value, nm_reason = _ratio(net_income, revenue, 100)
    m["net_margin_pct"] = Metric(nm_value, "%", inc_fy, "net income / total revenue x 100", nm_reason,
                                 {"net_income": net_income, "revenue": revenue})
    for metric in m.values():
        if metric.value is not None:
            metric.value = round(metric.value, 2)
    return m


# ---------------------------------------------------------------- rule-based assessments
# Thresholds are deliberately simple, general rules of thumb (documented, not sector-specific).
THRESHOLDS = {
    "profitability": "ROE >= 15% strong, 8-15% moderate, below 8% weak",
    "growth": "revenue growth >= 10% strong, 0-10% moderate, below 0% declining",
    "leverage": "debt-to-equity <= 0.5 low, 0.5-1.5 moderate, above 1.5 high",
    "liquidity": "current ratio >= 1.5 strong, 1.0-1.5 adequate, below 1.0 weak",
}


def assess(metrics: dict[str, Metric], is_bank: bool) -> dict[str, str]:
    def val(key):
        return metrics[key].value

    out: dict[str, str] = {}
    roe = val("roe_pct")
    out["profitability"] = ("insufficient_data" if roe is None else
                            "strong" if roe >= 15 else "moderate" if roe >= 8 else "weak")
    growth = val("revenue_growth_yoy_pct")
    out["growth"] = ("insufficient_data" if growth is None else
                     "strong" if growth >= 10 else "moderate" if growth >= 0 else "declining")
    de = val("debt_to_equity")
    out["leverage"] = ("not_applicable" if is_bank else "insufficient_data" if de is None else
                       "low" if de <= 0.5 else "moderate" if de <= 1.5 else "high")
    cr = val("current_ratio")
    out["liquidity"] = ("not_applicable" if is_bank else "insufficient_data" if cr is None else
                        "strong" if cr >= 1.5 else "adequate" if cr >= 1.0 else "weak")
    return out


NEGATIVE = {"weak", "declining", "high"}


def overall(assessments: dict[str, str]) -> str:
    """+1 per strong/low-debt dimension, -1 per weak/declining/high-debt one."""
    rated = [v for v in assessments.values() if v not in ("insufficient_data", "not_applicable")]
    if len(rated) < 2:
        return "insufficient_data"
    score = sum(v in {"strong", "low"} for v in rated) - sum(v in NEGATIVE for v in rated)
    return "solid" if score >= 2 else "weak" if score <= -1 else "mixed"


def strengths_and_weaknesses(metrics: dict[str, Metric], assessments: dict[str, str]) -> tuple[list[str], list[str]]:
    """Plain sentences built from computed values only."""
    def f(key):
        return metrics[key].value

    strengths, weaknesses = [], []
    a = assessments
    if a["profitability"] == "strong":
        strengths.append(f"High return on equity ({f('roe_pct')}%).")
    elif a["profitability"] == "weak":
        weaknesses.append(f"Low return on equity ({f('roe_pct')}%).")
    if a["growth"] == "strong":
        strengths.append(f"Revenue grew {f('revenue_growth_yoy_pct')}% in the latest year.")
    elif a["growth"] == "declining":
        weaknesses.append(f"Revenue fell {abs(f('revenue_growth_yoy_pct'))}% in the latest year.")
    if a["leverage"] == "low":
        strengths.append(f"Low debt relative to equity (debt-to-equity {f('debt_to_equity')}).")
    elif a["leverage"] == "high":
        weaknesses.append(f"High debt relative to equity (debt-to-equity {f('debt_to_equity')}).")
    if a["liquidity"] == "strong":
        strengths.append(f"Comfortable short-term liquidity (current ratio {f('current_ratio')}).")
    elif a["liquidity"] == "weak":
        weaknesses.append(f"Current liabilities exceed current assets (current ratio {f('current_ratio')}).")
    npg = f("net_profit_growth_yoy_pct")
    if npg is not None and npg < 0:
        weaknesses.append(f"Net profit fell {abs(npg)}% in the latest year.")
    elif npg is not None and npg >= 10:
        strengths.append(f"Net profit grew {npg}% in the latest year.")
    return strengths, weaknesses
