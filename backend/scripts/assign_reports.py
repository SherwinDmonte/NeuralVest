"""Give reports and portfolios that have no owner to one account (Phase 11).

Analyses started before Phase 11, or without logging in, have `user_id = null`. They do not
appear in GET /api/reports (your list), and with AUTH_REQUIRED=true nobody can open them.
This script assigns them to the account with the given e-mail. It only touches documents
whose user_id is null; reports that belong to someone are never changed.

Usage (from the backend/ folder, venv active):
    python scripts/assign_reports.py --email you@example.com            # dry run: only counts
    python scripts/assign_reports.py --email you@example.com --apply    # writes
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database.database import close_client, get_client  # noqa: E402
from app.database.models import ANALYSIS_REPORTS, PORTFOLIOS, USERS  # noqa: E402

UNOWNED = {"$or": [{"user_id": None}, {"user_id": {"$exists": False}}]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="e-mail of a registered account")
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument("--test-db", action="store_true", help="use the test database")
    args = parser.parse_args()

    settings = get_settings()
    name = settings.mongodb_test_db_name if args.test_db else settings.mongodb_db_name
    try:
        db = get_client(settings)[name]
        user = db[USERS].find_one({"email": args.email.strip().lower()}, {"user_id": 1})
        if user is None:
            print(f"No account with e-mail {args.email}. Register first (POST /api/auth/register).")
            return 1
        counts = {c: db[c].count_documents(UNOWNED) for c in (ANALYSIS_REPORTS, PORTFOLIOS)}
        print(f"Database '{name}': unowned reports={counts[ANALYSIS_REPORTS]}, portfolios={counts[PORTFOLIOS]}")
        if not args.apply:
            print("Dry run: nothing changed. Add --apply to assign them to this account.")
            return 0
        for c in (ANALYSIS_REPORTS, PORTFOLIOS):
            res = db[c].update_many(UNOWNED, {"$set": {"user_id": user["user_id"]}})
            print(f"{c}: {res.modified_count} assigned")
    finally:
        close_client()
    return 0


if __name__ == "__main__":
    sys.exit(main())
