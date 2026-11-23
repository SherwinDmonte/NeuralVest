"""Price history pipeline with the Yahoo download replaced by the synthetic fixture."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.config import Settings
from app.data import stock_data as sd
from app.data.errors import NoDataError
from app.database import models as m

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_prices_1y.csv"
NOW = datetime(2025, 12, 17, 4, 30, tzinfo=UTC)


@pytest.fixture
def fake_download(monkeypatch):
    calls = []

    def _download(symbol, period):
        calls.append(symbol)
        df = pd.read_csv(FIXTURE, index_col="date", parse_dates=True)
        df.index = df.index.tz_localize("Asia/Kolkata")  # like yfinance
        return df

    monkeypatch.setattr(sd, "_download", _download)
    return calls


def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_cache_dir=tmp_path)


def test_history_is_validated_then_cached(tmp_path, fake_download):
    first = sd.get_price_history("reliance", settings=settings(tmp_path), now=NOW)
    assert first.symbol == "RELIANCE.NS" and not first.from_cache
    assert first.report.rows_valid == 250 and first.report.last_date == "2025-12-16"
    assert first.provenance()["source"] == "yahoo_finance_via_yfinance"

    second = sd.get_price_history("RELIANCE.NS", settings=settings(tmp_path), now=NOW)
    assert second.from_cache and fake_download == ["RELIANCE.NS"]  # no second download
    pd.testing.assert_frame_equal(first.frame, second.frame)


def test_invalid_period_rejected(tmp_path, fake_download):
    with pytest.raises(ValueError):
        sd.get_price_history("TCS", period="7y", settings=settings(tmp_path))


def test_empty_download_raises(tmp_path, monkeypatch):
    def _empty(symbol, period):
        raise NoDataError("No price data")
    monkeypatch.setattr(sd, "_download", _empty)
    with pytest.raises(NoDataError):
        sd.get_price_history("NOTREAL", settings=settings(tmp_path))


@pytest.mark.integration
def test_store_price_history_upserts(tmp_path, fake_download, clean_db):
    history = sd.get_price_history("TCS", settings=settings(tmp_path), now=NOW)
    first = sd.store_price_history(clean_db, history)
    second = sd.store_price_history(clean_db, history)
    assert first["upserted"] == 250 and second["upserted"] == 0
    doc = clean_db[m.MARKET_DATA].find_one({"symbol": "TCS.NS"}, sort=[("date", 1)])
    assert doc["date"] == datetime(2025, 1, 1, tzinfo=UTC) and doc["source"] == "yahoo_finance_via_yfinance"
