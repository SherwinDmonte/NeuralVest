"""Small timing helpers (used for agent execution times and DB latency)."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware current time in UTC (the only timezone stored in the database)."""
    return datetime.now(UTC)


@contextmanager
def stopwatch() -> Iterator[dict]:
    """Usage: `with stopwatch() as t: ...` then read `t["seconds"]`."""
    result: dict = {"seconds": None}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = round(time.perf_counter() - start, 4)
