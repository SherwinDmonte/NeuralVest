"""Financial statement handling with synthetic yfinance-shaped tables (no network)."""

from datetime import date

import numpy as np
import pandas as pd

from app.data.financial_data import KEY_LINE_ITEMS, statement_to_periods, summarize


def yf_table(items: dict[str, list], periods: list[str]) -> pd.DataFrame:
    """yfinance layout: rows = line items, columns = period end dates."""
    return pd.DataFrame(items, index=pd.to_datetime(periods)).T


def test_statement_to_periods_drops_empty_years_and_nans():
    df = yf_table(
        {"Total Revenue": [200.0, 180.0, np.nan], "Net Income": [20.0, np.nan, np.nan]},
        ["2026-03-31", "2025-03-31", "2022-03-31"],
    )
    periods = statement_to_periods(df)
    assert list(periods) == ["2026-03-31", "2025-03-31"]  # all-NaN 2022 dropped, newest first
    assert periods["2025-03-31"]["Net Income"] is None  # missing stays missing, never filled
    assert periods["2026-03-31"]["Total Revenue"] == 200.0


def test_empty_statement():
    assert statement_to_periods(pd.DataFrame()) == {} and statement_to_periods(None) == {}


def test_summarize_reports_missing_items_like_a_bank():
    income = {"2026-03-31": {"Total Revenue": 1.0, "Net Income": 1.0, "Diluted EPS": 1.0, "Basic EPS": 1.0}}
    statements = {"income_statement": income, "balance_sheet": {}, "cash_flow": {}}
    latest, missing, stale, warnings = summarize(statements, today=date(2026, 11, 23))
    assert latest["income_statement"] == "2026-03-31" and latest["balance_sheet"] is None
    assert missing["income_statement"] == ["Operating Income"]  # banks report no operating income
    assert missing["balance_sheet"] == KEY_LINE_ITEMS["balance_sheet"]
    assert not stale
    assert any("No balance sheet data" in w for w in warnings)


def test_summarize_flags_stale_statements():
    old = {"2024-03-31": {item: 1.0 for item in KEY_LINE_ITEMS["income_statement"]}}
    _, _, stale, warnings = summarize({"income_statement": old, "balance_sheet": {}, "cash_flow": {}},
                                      today=date(2026, 11, 23))
    assert stale and any("18 months" in w for w in warnings)
