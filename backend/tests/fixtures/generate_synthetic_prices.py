"""Generate the SYNTHETIC price fixture used by the tests.

Why synthetic: real Yahoo Finance data may not be redistributed in a public repository
(personal-use terms), and tests must be reproducible offline. This deterministic random walk
has realistic structure (OHLC ordering, volume, ~1 year of weekdays) but is NOT market data.

    python tests/fixtures/generate_synthetic_prices.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).with_name("synthetic_prices_1y.csv")


def generate(seed: int = 42, days: int = 250, start_price: float = 1000.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=days)
    returns = rng.normal(0.0004, 0.015, days)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]]) * (1 + rng.normal(0, 0.003, days))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, days)))
    volume = rng.integers(2_000_000, 12_000_000, days)
    return pd.DataFrame(
        {"open": open_.round(2), "high": high.round(2), "low": low.round(2), "close": close.round(2),
         "adjusted_close": close.round(2), "volume": volume},
        index=pd.Index(dates, name="date"),
    )


if __name__ == "__main__":
    df = generate()
    df.to_csv(OUT)
    print(f"wrote {OUT.name}: {len(df)} rows, {df.index[0].date()} .. {df.index[-1].date()}")
