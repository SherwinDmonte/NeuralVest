"""Stock endpoints.

PLACEHOLDER (Phase 2): only `GET /api/stocks/{symbol}` exists, and it returns what is
already stored in the `stocks` collection. Data collection (yfinance) arrives in Phase 3,
and search/history/indicators in later phases. No dummy data is ever returned: an
unknown symbol gives an honest 404.
"""

from fastapi import APIRouter, Path

from app.api.errors import AppError
from app.database.database import get_database
from app.database.models import STOCKS, SYMBOL_PATTERN
from app.database.repository import find_one

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/{symbol}", summary="Stored company information for one symbol")
def get_stock(
    symbol: str = Path(
        description="Yahoo-style ticker, e.g. RELIANCE.NS (NSE) or 500325.BO (BSE)",
        pattern=SYMBOL_PATTERN,
        examples=["RELIANCE.NS"],
    ),
) -> dict:
    # The database is obtained inside the handler, AFTER FastAPI has validated `symbol`.
    # (Dependencies run before parameter validation, so a DB dependency would turn
    # invalid input into a misleading 503 when the database is down.)
    db = get_database()
    doc = find_one(db, STOCKS, {"symbol": symbol})
    if doc is None:
        raise AppError(
            404,
            "stock_not_found",
            f"No stored data for {symbol} yet. Market data collection is added in Phase 3.",
        )
    return doc
