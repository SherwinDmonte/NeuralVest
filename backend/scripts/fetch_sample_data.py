"""Phase 3 manual verification (task 3.6.3): run the real data pipeline for sample symbols.

For each symbol: company profile, 1 year of prices (validated, stored in market_data),
annual financial statements, and recent news (RSS + GDELT). Prints a summary; raw data
stays in the git-ignored cache and in MongoDB. Nothing here is committed to the repository.

Usage (from backend/, venv active):
    python scripts/fetch_sample_data.py                       # the 5 milestone symbols
    python scripts/fetch_sample_data.py RELIANCE TCS --no-gdelt
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Windows consoles default to cp1252, which cannot print characters such as the rupee sign.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


from app.config import get_settings  # noqa: E402
from app.data.errors import DataError  # noqa: E402
from app.data.financial_data import get_financial_statements  # noqa: E402
from app.data.news_data import collect_news  # noqa: E402
from app.data.stock_data import get_benchmark_history, get_company_profile, get_price_history, store_price_history  # noqa: E402
from app.data.symbols import normalize_symbol  # noqa: E402
from app.database.database import close_client, get_database, initialize_database  # noqa: E402
from app.utils.timing import stopwatch  # noqa: E402

DEFAULT_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--no-gdelt", action="store_true", help="RSS only (GDELT is slow: ~25 s per request)")
    parser.add_argument("--no-store", action="store_true", help="do not write prices to MongoDB")
    args = parser.parse_args()

    settings = get_settings()
    db = None if args.no_store else get_database(settings)
    if db is not None:
        initialize_database(db)
    failures = 0
    try:
        bench = get_benchmark_history(settings=settings)
        print(f"Benchmark ^NSEI: {bench.report.rows_valid} rows, last {bench.report.last_date}, "
              f"cache={bench.from_cache}, warnings={bench.report.warnings}")
        if db is not None:
            store_price_history(db, bench)

        for raw_symbol in args.symbols:
            try:
                symbol = normalize_symbol(raw_symbol)
                print(f"\n=== {symbol} ===")
                with stopwatch() as t:
                    profile = get_company_profile(symbol, settings=settings)
                    prices = get_price_history(symbol, settings=settings)
                    stored = store_price_history(db, prices) if db is not None else None
                    fin = get_financial_statements(symbol, settings=settings)
                    news = collect_news(symbol, profile["company_name"], include_gdelt=not args.no_gdelt,
                                        settings=settings)
                r = prices.report
                last = prices.frame.iloc[-1]
                print(f"Company   : {profile['company_name']} | {profile.get('sector')} / {profile.get('industry')}")
                print(f"Prices    : {r.rows_valid}/{r.rows_received} valid rows {r.first_date}..{r.last_date}, "
                      f"last close {last['close']:.2f} (as of {r.last_date}), stale={r.is_stale}, "
                      f"incomplete_last_bar={r.last_bar_may_be_incomplete}, outliers={len(r.outliers_flagged)}, "
                      f"removed={len(r.missing_price_dates_removed) + len(r.invalid_price_dates_removed)}, "
                      f"dups={r.duplicates_removed}, cache={prices.from_cache}")
                if stored is not None:
                    print(f"MongoDB   : market_data upserted={stored['upserted']} matched={stored['matched']}")
                print(f"Financials: latest periods {fin.latest_period}, stale={fin.is_stale}")
                print(f"            missing key items {({k: v for k, v in fin.missing_key_items.items() if v}) or 'none'}")
                print(f"News      : {len(news.articles)} articles (dups removed {news.duplicates_removed}), "
                      f"cache={news.from_cache}")
                print(f"            sources {news.source_status}")
                for a in news.articles[:3]:
                    print(f"            - {a.published_at:%Y-%m-%d} {a.publisher[:30]}: {a.headline[:90]}"
                          if a.published_at else f"            - (no date) {a.headline[:90]}")
                for w in prices.warnings + fin.warnings + news.warnings:
                    print(f"  warning : {w}")
                print(f"Time      : {t['seconds']:.1f} s")
            except DataError as exc:
                failures += 1
                print(f"FAILED    : {exc.__class__.__name__}: {exc}")
    finally:
        close_client()
    print(f"\nDone: {len(args.symbols) - failures}/{len(args.symbols)} symbols succeeded.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
