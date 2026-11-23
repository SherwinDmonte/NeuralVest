"""Test doubles for agent tests: synthetic prices, a fake LLM and a fake news server."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from app.data.data_validator import validate_ohlcv
from app.data.errors import NoDataError
from app.data.stock_data import PriceHistory
from app.llm.ollama_client import LLMResult

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2025, 12, 17, 4, 30, tzinfo=UTC)  # day after the synthetic fixture ends


def synthetic_history(symbol: str, rows: int | None = None, scale: float = 1.0) -> PriceHistory:
    df = pd.read_csv(FIXTURES / "synthetic_prices_1y.csv", index_col="date", parse_dates=True)
    if rows:
        df = df.iloc[-rows:]
    for col in ("open", "high", "low", "close", "adjusted_close"):
        df[col] = df[col] * scale
    frame, report = validate_ohlcv(df, symbol, now=NOW)
    return PriceHistory(symbol=symbol, period="1y", frame=frame, report=report, fetched_at=NOW, from_cache=False)


def patch_market_data(monkeypatch, module, *, rows=None, fail_prices=False, fail_benchmark=False, fail_profile=False):
    """Replace the data functions used by the Market Research agent."""
    def prices(symbol, period="1y", settings=None, now=None, **_):
        if fail_prices:
            raise NoDataError(f"No price data for {symbol}.")
        return synthetic_history(symbol, rows)

    def benchmark(period="1y", settings=None, now=None, **_):
        if fail_benchmark:
            raise NoDataError("No price data for ^NSEI.")
        return synthetic_history("^NSEI", rows, scale=20)

    def profile(symbol, settings=None, **_):
        if fail_profile:
            raise NoDataError("No company profile.")
        return {"symbol": symbol, "company_name": "Reliance Industries Limited", "source": "test",
                "fetched_at": NOW.isoformat(), "sector": "Energy"}

    monkeypatch.setattr(module, "get_price_history", prices)
    monkeypatch.setattr(module, "get_benchmark_history", benchmark)
    monkeypatch.setattr(module, "get_company_profile", profile)


def synthetic_statements(bank: bool = False) -> dict:
    """Hand-built annual statements with round numbers, so every ratio can be checked by hand
    (see tests/test_fundamentals.py). Banks lack operating income and current items."""
    income = {
        "2026-03-31": {"Total Revenue": 1200.0, "Net Income": 120.0, "Operating Income": 180.0, "Diluted EPS": 12.0},
        "2025-03-31": {"Total Revenue": 1000.0, "Net Income": 100.0, "Operating Income": 150.0, "Diluted EPS": 10.0},
        "2024-03-31": {"Total Revenue": 900.0, "Net Income": 90.0, "Operating Income": 130.0, "Diluted EPS": 9.0},
    }
    balance = {
        "2026-03-31": {"Stockholders Equity": 800.0, "Total Assets": 2000.0, "Total Debt": 400.0,
                       "Current Assets": 600.0, "Current Liabilities": 300.0, "Ordinary Shares Number": 10.0},
        "2025-03-31": {"Stockholders Equity": 700.0, "Total Assets": 1800.0, "Total Debt": 350.0,
                       "Current Assets": 500.0, "Current Liabilities": 280.0, "Ordinary Shares Number": 10.0},
    }
    if bank:
        for period in income.values():
            period.pop("Operating Income")
        for period in balance.values():
            period.pop("Current Assets"), period.pop("Current Liabilities")
            period["Total Debt"] *= 5
    return {"income_statement": income, "balance_sheet": balance, "cash_flow": {}}


def patch_fundamentals(monkeypatch, module, *, bank=False, fail=False, financial_currency="INR"):
    """Replace the data functions used by the Stock Analysis agent."""
    from app.data.errors import NoDataError as _NoData
    from app.data.financial_data import FinancialStatements, summarize

    def statements(symbol, settings=None, **_):
        if fail:
            raise _NoData(f"No financial statements available for {symbol}.")
        st = synthetic_statements(bank)
        latest, missing, stale, warnings = summarize(st, today=datetime(2026, 11, 23).date())
        return FinancialStatements(symbol=symbol, statements=st, latest_period=latest, missing_key_items=missing,
                                   is_stale=stale, fetched_at=NOW, from_cache=False, warnings=warnings)

    def profile(symbol, settings=None, **_):
        return {"symbol": symbol, "company_name": "Example Bank Limited" if bank else "Example Industries Limited",
                "sector": "Financial Services" if bank else "Energy",
                "industry": "Banks - Regional" if bank else "Oil & Gas Refining & Marketing",
                "currency": "INR", "financial_currency": financial_currency, "source": "test",
                "fetched_at": NOW.isoformat()}

    monkeypatch.setattr(module, "get_financial_statements", statements)
    monkeypatch.setattr(module, "get_company_profile", profile)


def patch_benchmark(monkeypatch, module):
    """The graph's risk node reads NIFTY 50 from the cache; tests use the synthetic history."""
    monkeypatch.setattr(module, "get_benchmark_history",
                        lambda period="2y", settings=None, **_: synthetic_history("^NSEI", scale=20))


class FakeLLM:
    """Returns fixed, valid answers and records which prompts were used."""

    def __init__(self, relevance: str = "high", sentiment: str = "positive"):
        self.calls: list[str] = []
        self.relevance, self.sentiment = relevance, sentiment

    def generate_structured(self, spec, schema, fallback):
        self.calls.append(spec.name)
        values = {
            "news_analysis": {"summary": "A short neutral summary.", "sentiment": self.sentiment,
                              "category": "company_announcement", "relevance": self.relevance},
            "market_explanation": {"explanation": "The trend is described using the given facts."},
            "news_digest": {"digest": "Recent coverage was mostly about company announcements."},
            "stock_analysis": {"explanation": "The company's finances are described using the given facts."},
            "risk_explanation": {"explanation": "Historical risk is described using the given facts only."},
            "portfolio_explanation": {"explanation": "The illustrative allocation is described using the given facts."},
            "report_summary": {"observations": ["The stock's results are summarised from the given facts.",
                                                "Risk and financial health are described without new numbers."]},
        }[spec.name]
        return LLMResult(value=schema(**values), source="llm", model="fake-model",
                         attempts=[{"model": "fake-model", "ok": True, "seconds": 0.0}])


def news_transport(status: int = 200) -> httpx.MockTransport:
    """Every RSS feed returns the synthetic sample feed (or an error status)."""
    feed = (FIXTURES / "sample_feed.xml").read_bytes()
    return httpx.MockTransport(lambda request: httpx.Response(status, content=feed if status == 200 else b""))
