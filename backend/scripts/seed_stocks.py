"""Seed the `stocks` collection with the curated suggestion list (app/data/seed_symbols.json).

Each symbol's company name, sector and industry are fetched from Yahoo Finance; symbols
that cannot be verified are skipped and reported (never stored with made-up details).

Usage (from backend/, venv active):
    python scripts/seed_stocks.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.data.errors import DataError  # noqa: E402
from app.data.stock_data import get_company_profile  # noqa: E402
from app.data.symbols import load_seed_symbols  # noqa: E402
from app.database.database import close_client, get_database, initialize_database  # noqa: E402
from app.database.models import StockDocument  # noqa: E402
from app.database.repository import upsert_document  # noqa: E402


def main() -> int:
    seed = load_seed_symbols()
    settings = get_settings()
    db = get_database(settings)
    initialize_database(db)
    stored, skipped = 0, []
    try:
        for symbol in seed["symbols"]:
            try:
                profile = get_company_profile(symbol, settings=settings)
            except DataError as exc:
                skipped.append(f"{symbol}: {exc}")
                continue
            doc = StockDocument(
                symbol=symbol,
                company_name=profile["company_name"],
                exchange=profile["exchange"],
                sector=profile.get("sector"),
                industry=profile.get("industry"),
                company_information={
                    "short_name": profile.get("short_name"),
                    "currency": profile.get("currency"),
                    "source": profile["source"],
                    "profile_fetched_at": profile["fetched_at"],
                    "listed_in": "NeuralVest curated suggestion list " + seed["curated_on"],
                },
            )
            upsert_document(db, doc, ["symbol"])
            stored += 1
            print(f"  ok  {symbol:16} {profile['company_name']}  [{profile.get('sector')}]")
            if not profile.get("from_cache"):
                time.sleep(1)  # be gentle with Yahoo
    finally:
        close_client()
    print(f"\nStored {stored}/{len(seed['symbols'])} symbols in '{db.name}.stocks'.")
    for line in skipped:
        print("  skipped", line)
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
