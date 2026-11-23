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
        }[spec.name]
        return LLMResult(value=schema(**values), source="llm", model="fake-model",
                         attempts=[{"model": "fake-model", "ok": True, "seconds": 0.0}])


def news_transport(status: int = 200) -> httpx.MockTransport:
    """Every RSS feed returns the synthetic sample feed (or an error status)."""
    feed = (FIXTURES / "sample_feed.xml").read_bytes()
    return httpx.MockTransport(lambda request: httpx.Response(status, content=feed if status == 200 else b""))
