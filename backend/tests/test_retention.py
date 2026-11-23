from datetime import UTC, datetime

import pytest

from app.database.retention import market_data_cutoff


def test_cutoff_is_max_years_before_now():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    cutoff = market_data_cutoff(5, now)
    assert cutoff.year == 2021 and cutoff.month == 11


def test_cutoff_rejects_zero_years():
    with pytest.raises(ValueError):
        market_data_cutoff(0)
