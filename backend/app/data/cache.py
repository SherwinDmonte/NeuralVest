"""Small JSON file cache in data/cache/ (git-ignored).

Purpose: avoid repeating slow or rate-limited calls (Yahoo, GDELT, RSS). Each entry stores
when it was fetched, so freshness can be checked and shown to the user.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.utils.timing import utc_now

_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]")


class FileCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, namespace: str, key: str) -> Path:
        # '^NSEI' -> '_NSEI', 'M&M.NS' -> 'M_M.NS': safe file names, no path traversal.
        return self.root / _SAFE_KEY.sub("_", namespace) / f"{_SAFE_KEY.sub('_', key)}.json"

    def read(self, namespace: str, key: str, max_age: timedelta) -> tuple[Any, datetime] | None:
        """Return (data, fetched_at) if a fresh entry exists, else None."""
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (ValueError, KeyError, OSError):
            return None  # corrupt entry: behave as a cache miss
        if utc_now() - fetched_at > max_age:
            return None
        return entry["data"], fetched_at

    def write(self, namespace: str, key: str, data: Any, fetched_at: datetime | None = None) -> datetime:
        fetched_at = fetched_at or utc_now()
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at.isoformat(), "data": data}), encoding="utf-8")
        os.replace(tmp, path)  # atomic: readers never see a half-written file
        return fetched_at
