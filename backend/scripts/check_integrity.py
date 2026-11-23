"""Read-only database integrity check (database_design.md §5.3). Never modifies data.

Usage (from the backend/ folder, venv active):
    python scripts/check_integrity.py            # main database
    python scripts/check_integrity.py --test-db  # test database
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database.database import close_client, get_client  # noqa: E402
from app.database.integrity import check_integrity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test-db", action="store_true", help="check the test database instead")
    args = parser.parse_args()

    settings = get_settings()
    name = settings.mongodb_test_db_name if args.test_db else settings.mongodb_db_name
    try:
        report = check_integrity(get_client(settings)[name])
    finally:
        close_client()
    print(json.dumps({"database": name, **report}, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
