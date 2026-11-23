"""Fundamental ratios checked against HAND-COMPUTED values (task 7.1.8).

Synthetic statements (tests/agent_fakes.synthetic_statements), price = 180:
  revenue 900 -> 1000 -> 1200, net income 90 -> 100 -> 120, operating income 180 (latest)
  equity 700 -> 800, assets 1800 -> 2000, debt 400, current assets/liabilities 600/300,
  shares 10, diluted EPS 12.
"""

import pytest

from app.analysis import fundamentals as fa
from tests.agent_fakes import synthetic_statements

PRICE = 180.0


def compute(statements=None, price=PRICE, **kw):
    return fa.compute_fundamentals(statements or synthetic_statements(), price, **kw)


def test_hand_computed_values():
    m = compute()
    expected = {
        "revenue_growth_yoy_pct": 20.0,  # 1200 / 1000 - 1
        "revenue_cagr_pct": 15.47,  # (1200 / 900) ** (1/2) - 1 = 0.15470
        "net_profit_growth_yoy_pct": 20.0,  # 120 / 100 - 1
        "net_profit_cagr_pct": 15.47,  # (120 / 90) ** (1/2) - 1
        "eps": 12.0,  # reported diluted EPS
        "pe": 15.0,  # 180 / 12
        "pb": 2.25,  # 180 / (800 / 10)
        "roe_pct": 16.0,  # 120 / ((800 + 700) / 2)
        "roa_pct": 6.32,  # 120 / ((2000 + 1800) / 2) = 0.063158
        "debt_to_equity": 0.5,  # 400 / 800
        "current_ratio": 2.0,  # 600 / 300
        "operating_margin_pct": 15.0,  # 180 / 1200
        "net_margin_pct": 10.0,  # 120 / 1200
    }
    assert {k: m[k].value for k in expected} == expected


def test_every_metric_has_period_formula_and_unit():
    for name, metric in compute().items():
        assert metric.formula and metric.unit in {"%", "x", "INR"}, name
        assert metric.period, name
    assert compute()["roe_pct"].period == "FY2026 (year ended 2026-03-31)"
    assert "average of opening and closing" in compute()["roe_pct"].formula


def test_assessments_and_overall():
    m = compute()
    a = fa.assess(m, is_bank=False)
    assert a == {"profitability": "strong", "growth": "strong", "leverage": "low", "liquidity": "strong"}
    assert fa.overall(a) == "solid"
    strengths, weaknesses = fa.strengths_and_weaknesses(m, a)
    assert "High return on equity (16.0%)." in strengths and weaknesses == []


# ---------------------------------------------------------------- edge cases (task 7.1.6)
def test_negative_eps_makes_pe_not_meaningful():
    st = synthetic_statements()
    st["income_statement"]["2026-03-31"]["Diluted EPS"] = -3.0
    pe = compute(st)["pe"]
    assert pe.value is None and "loss-making" in pe.reason


def test_zero_denominators():
    st = synthetic_statements()
    st["balance_sheet"]["2026-03-31"]["Current Liabilities"] = 0.0
    st["income_statement"]["2026-03-31"]["Total Revenue"] = 0.0
    m = compute(st)
    assert m["current_ratio"].value is None and m["current_ratio"].reason == "denominator is zero"
    assert m["net_margin_pct"].value is None and m["operating_margin_pct"].value is None


def test_loss_in_previous_year_makes_growth_not_meaningful():
    st = synthetic_statements()
    st["income_statement"]["2025-03-31"]["Net Income"] = -50.0
    g = compute(st)["net_profit_growth_yoy_pct"]
    assert g.value is None and "not meaningful" in g.reason


def test_negative_equity():
    st = synthetic_statements()
    for period in ("2026-03-31", "2025-03-31"):
        st["balance_sheet"][period]["Stockholders Equity"] = -100.0
    m = compute(st)
    assert m["roe_pct"].value is None and "negative" in m["roe_pct"].reason
    assert m["pb"].value is None and m["debt_to_equity"].value is None


def test_missing_items_are_never_estimated():
    st = synthetic_statements()
    st["balance_sheet"]["2026-03-31"].pop("Total Debt")
    st["income_statement"]["2026-03-31"].pop("Diluted EPS")
    m = compute(st)
    assert m["debt_to_equity"].value is None and "not available" in m["debt_to_equity"].reason
    assert m["eps"].value is None and m["pe"].value is None


def test_basic_eps_used_when_diluted_missing():
    st = synthetic_statements()
    st["income_statement"]["2026-03-31"].pop("Diluted EPS")
    st["income_statement"]["2026-03-31"]["Basic EPS"] = 12.5
    m = compute(st)
    assert m["eps"].value == 12.5 and m["eps"].inputs["source_item"] == "Basic EPS" and m["pe"].value == 14.4


def test_single_year_and_no_price():
    st = synthetic_statements()
    st["income_statement"] = {"2026-03-31": st["income_statement"]["2026-03-31"]}
    m = compute(st, price=None)
    assert m["revenue_growth_yoy_pct"].value is None and "two years" in m["revenue_growth_yoy_pct"].reason
    assert m["pe"].value is None and m["pb"].value is None


def test_two_years_gives_yoy_but_no_cagr():
    st = synthetic_statements()
    st["income_statement"].pop("2024-03-31")
    m = compute(st)
    assert m["revenue_growth_yoy_pct"].value == 20.0 and m["revenue_cagr_pct"].value is None


def test_closing_values_when_previous_year_missing():
    st = synthetic_statements()
    st["balance_sheet"].pop("2025-03-31")
    roe = compute(st)["roe_pct"]
    assert roe.value == 15.0 and "previous year unavailable" in roe.formula  # 120 / 800


def test_currency_mismatch_blocks_valuation_ratios():
    m = compute(currencies_match=False)
    assert m["pe"].value is None and "currencies" in m["pe"].reason
    assert m["pb"].value is None and m["roe_pct"].value == 16.0  # ratios within statements still fine


def test_bank_handling():
    m = compute(synthetic_statements(bank=True), is_bank=True)
    assert m["current_ratio"].value is None and "banks do not report" in m["current_ratio"].reason
    assert m["operating_margin_pct"].value is None and "not applicable" in m["operating_margin_pct"].reason
    assert m["debt_to_equity"].value == 2.5 and "not comparable" in m["debt_to_equity"].reason
    a = fa.assess(m, is_bank=True)
    assert a["leverage"] == "not_applicable" and a["liquidity"] == "not_applicable"
    assert a["profitability"] == "strong" and fa.overall(a) == "solid"


@pytest.mark.parametrize(
    "assessments, expected",
    [({"profitability": "weak", "growth": "declining", "leverage": "high", "liquidity": "weak"}, "weak"),
     ({"profitability": "strong", "growth": "declining", "leverage": "moderate", "liquidity": "adequate"}, "mixed"),
     ({"profitability": "insufficient_data", "growth": "strong", "leverage": "not_applicable",
       "liquidity": "not_applicable"}, "insufficient_data")],
)
def test_overall_rule(assessments, expected):
    assert fa.overall(assessments) == expected


def test_merger_like_jump_flags_cagr():
    # HDFC Bank case: revenue more than doubles in one year after a merger.
    st = synthetic_statements()
    st["income_statement"]["2025-03-31"]["Total Revenue"] = 1100.0
    st["income_statement"]["2024-03-31"]["Total Revenue"] = 400.0  # 400 -> 1100 is +175%
    cagr = compute(st)["revenue_cagr_pct"]
    assert cagr.value is not None and "possibly a merger" in cagr.reason and "FY2025" in cagr.reason
    assert compute()["revenue_cagr_pct"].reason is None  # normal growth is not flagged
