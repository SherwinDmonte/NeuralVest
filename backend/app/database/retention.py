"""Market-data retention (database_design.md §4.5): keep at most MARKET_DATA_MAX_YEARS of prices."""

from datetime import datetime, timedelta

from pymongo.database import Database

from app.database.models import MARKET_DATA
from app.utils.timing import utc_now

DAYS_PER_YEAR = 365.25


def market_data_cutoff(max_years: int, now: datetime | None = None) -> datetime:
    if max_years < 1:
        raise ValueError("max_years must be at least 1")
    return (now or utc_now()) - timedelta(days=max_years * DAYS_PER_YEAR)


def cleanup_market_data(db: Database, max_years: int, apply: bool = False) -> dict:
    """Count (dry run) or delete market_data rows older than the cutoff.

    Dry run is the default so nothing is deleted by accident.
    """
    cutoff = market_data_cutoff(max_years)
    query = {"date": {"$lt": cutoff}}
    if not apply:
        return {"dry_run": True, "cutoff": cutoff.isoformat(), "would_delete": db[MARKET_DATA].count_documents(query)}
    result = db[MARKET_DATA].delete_many(query)
    return {"dry_run": False, "cutoff": cutoff.isoformat(), "deleted": result.deleted_count}
