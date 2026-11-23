"""Delete market_data rows older than MARKET_DATA_MAX_YEARS (database_design.md §4.5).

Dry run by default: it only counts. Add --apply to actually delete.

Usage (from the backend/ folder, venv active):
    python scripts/cleanup_market_data.py              # dry run
    python scripts/cleanup_market_data.py --apply      # delete
    python scripts/cleanup_market_data.py --years 3    # override the configured retention
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database.database import close_client, get_client  # noqa: E402
from app.database.retention import cleanup_market_data  # noqa: E402


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, default=settings.market_data_max_years,
                        help=f"years of history to keep (default from .env: {settings.market_data_max_years})")
    parser.add_argument("--apply", action="store_true", help="actually delete (otherwise dry run)")
    args = parser.parse_args()

    try:
        result = cleanup_market_data(get_client(settings)[settings.mongodb_db_name], args.years, apply=args.apply)
    finally:
        close_client()
    print(json.dumps({"database": settings.mongodb_db_name, "years": args.years, **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
