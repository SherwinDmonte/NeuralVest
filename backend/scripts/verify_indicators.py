"""Milestone check 6.3.2: indicators on REAL data vs independent reference implementations.

Fetches real daily prices, computes SMA20, SMA50, RSI14 and MACD with the production code
(app/analysis/technical_indicators.py) and with the plain-loop reference implementations
(tests/reference_indicators.py), and reports the largest difference over the whole series.

Usage (from backend/, venv active):
    python scripts/verify_indicators.py RELIANCE
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis import technical_indicators as ti  # noqa: E402
from app.data.stock_data import get_price_history  # noqa: E402
from tests.reference_indicators import ref_macd, ref_rsi, ref_sma  # noqa: E402

TOLERANCE = 1e-9


def max_diff(production, reference) -> tuple[float, int]:
    worst, compared = 0.0, 0
    for got, want in zip(production, reference, strict=True):
        if want is None:
            if not math.isnan(got):
                return math.inf, compared  # production has a value where the reference has none
            continue
        worst, compared = max(worst, abs(got - want)), compared + 1
    return worst, compared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", nargs="?", default="RELIANCE")
    args = parser.parse_args()

    history = get_price_history(args.symbol, period="2y")
    closes = history.frame["close"].tolist()
    ind = ti.compute_indicators(history.frame)
    line, signal = ref_macd(closes)
    checks = {
        "SMA 20": (ind["sma_20"], ref_sma(closes, 20)),
        "SMA 50": (ind["sma_50"], ref_sma(closes, 50)),
        "RSI 14": (ind["rsi_14"], ref_rsi(closes, 14)),
        "MACD line": (ind["macd"], line),
        "MACD signal": (ind["macd_signal"], signal),
    }
    print(f"{history.symbol}: {len(closes)} real daily closes {history.report.first_date}..{history.report.last_date} "
          f"(source {history.source}, fetched {history.fetched_at:%Y-%m-%d %H:%M} UTC)\n")
    ok = True
    for name, (prod, ref) in checks.items():
        diff, n = max_diff(prod.tolist(), ref)
        passed = diff <= TOLERANCE
        ok &= passed
        latest = prod.iloc[-1]
        print(f"  {'PASS' if passed else 'FAIL'}  {name:12} latest {latest:12.4f}  max |difference| {diff:.2e} over {n} values")
    print("\nAll indicators match the reference implementations." if ok else "\nMISMATCH found.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
