"""Freeze a fixed historical dataset for the financial validation tests (Phase 13, task 13.1.5).

Downloads two years of real daily prices (Yahoo Finance via yfinance) for a few NSE stocks and
the NIFTY 50, cuts them at a fixed end date, and saves the latest annual statements. The files go
to data/historical/validation/, which is NOT committed (Yahoo data is third-party and is not
redistributed; see .gitignore). A manifest records the end date, row counts and SHA-256 hashes,
so tests/test_financial_validation.py can confirm it is checking the same data every time.

Nothing is written to MongoDB. Run it once (from backend/, venv active):
    python scripts/freeze_validation_dataset.py
    python scripts/freeze_validation_dataset.py --end 2026-11-20 --force
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import PROJECT_ROOT  # noqa: E402
from app.data.financial_data import get_financial_statements  # noqa: E402
from app.data.stock_data import SOURCE, _download  # noqa: E402

OUT_DIR = PROJECT_ROOT / "data" / "historical" / "validation"
PRICE_SYMBOLS = ("RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "^NSEI")
STATEMENT_SYMBOLS = ("RELIANCE.NS", "TCS.NS", "HDFCBANK.NS")  # HDFCBANK.NS: the bank rules
DEFAULT_END = "2026-11-20"


def file_name(kind: str, symbol: str) -> str:
    return f"{kind}_{symbol.replace('^', '_')}.{'csv' if kind == 'prices' else 'json'}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--end", default=DEFAULT_END, help="last trading date to keep (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="replace an existing dataset")
    args = parser.parse_args()
    end = date.fromisoformat(args.end)
    manifest_path = OUT_DIR / "manifest.json"
    if manifest_path.exists() and not args.force:
        print(f"A dataset already exists ({manifest_path}). Use --force to replace it.")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict] = {}
    for symbol in PRICE_SYMBOLS:
        raw = _download(symbol, "2y")
        raw.index = raw.index.tz_localize(None) if raw.index.tz is not None else raw.index
        raw = raw[raw.index.date <= end]
        path = OUT_DIR / file_name("prices", symbol)
        raw.to_csv(path, index_label="date", date_format="%Y-%m-%d", float_format="%.6f", lineterminator="\n")
        files[path.name] = {"symbol": symbol, "rows": len(raw), "first": raw.index[0].strftime("%Y-%m-%d"),
                            "last": raw.index[-1].strftime("%Y-%m-%d"), "sha256": sha256(path)}
        print(f"{symbol:12} {len(raw)} rows, {files[path.name]['first']} to {files[path.name]['last']}")

    for symbol in STATEMENT_SYMBOLS:
        fs = get_financial_statements(symbol)
        path = OUT_DIR / file_name("statements", symbol)
        path.write_text(json.dumps(fs.statements, indent=1), encoding="utf-8", newline="\n")
        files[path.name] = {"symbol": symbol, "latest_period": fs.latest_period,
                            "fetched_at": fs.fetched_at.isoformat(), "sha256": sha256(path)}
        print(f"{symbol:12} statements, latest period {fs.latest_period}")

    manifest = {"created_at": datetime.now(UTC).isoformat(timespec="seconds"), "end_date": args.end,
                "price_source": SOURCE, "statement_source": SOURCE, "files": files}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    print(f"Saved to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
