"""Stock endpoints: stored company info, price history and indicator series for charts.

No dummy data is ever returned. Unknown symbols give an honest 404.
"""

import re
from datetime import timedelta

from fastapi import APIRouter, Path, Query
from pymongo import ASCENDING

from app.analysis import technical_indicators as ti
from app.api.errors import AppError
from app.config import get_settings
from app.data.errors import DataError, InvalidSymbolError, NoDataError
from app.data.stock_data import get_price_history, store_price_history
from app.data.symbols import base_ticker, exchange_of, load_seed_symbols, normalize_symbol
from app.database.database import get_database
from app.database.models import MARKET_DATA, STOCKS, SYMBOL_PATTERN
from app.database.repository import find_one
from app.utils.timing import utc_now

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

SYMBOL = Path(description="Yahoo-style ticker, e.g. RELIANCE.NS (NSE) or 500325.BO (BSE)",
              pattern=SYMBOL_PATTERN, examples=["RELIANCE.NS"])
PERIOD_DAYS = {"1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731}


@router.get("/search", summary="Search stocks by symbol or company name")
def search_stocks(q: str = Query(min_length=1, max_length=50, description="e.g. 'reli', 'TCS' or '500325'"),
                  limit: int = Query(10, ge=1, le=50)) -> dict:
    """Matches stored companies (MongoDB `stocks`, filled when stocks are analysed or seeded) and
    the curated suggestion list. Any valid NSE/BSE symbol can be analysed even if it is not
    listed: when `q` itself is a valid symbol it is returned as `normalized`."""
    text = " ".join(q.split())
    pattern = re.compile(re.escape(text), re.IGNORECASE)  # user text is escaped: no regex injection
    results: dict[str, dict] = {}
    db_error = None
    settings = get_settings()
    if settings.mongodb_configured:
        try:
            cursor = get_database(settings)[STOCKS].find(
                {"$or": [{"symbol": pattern}, {"company_name": pattern}]},
                {"_id": 0, "symbol": 1, "company_name": 1, "exchange": 1, "sector": 1, "industry": 1}).limit(200)
            for d in cursor:
                results[d["symbol"]] = {**d, "source": "stored"}
        except Exception as exc:  # search still works from the curated list
            db_error = exc.__class__.__name__
    for sym in load_seed_symbols()["symbols"]:
        if sym not in results and pattern.search(sym):
            results[sym] = {"symbol": sym, "company_name": None, "exchange": exchange_of(sym), "sector": None,
                            "industry": None, "source": "curated_list"}
    key = text.upper()

    def rank(item: dict) -> tuple:
        base = base_ticker(item["symbol"])
        name = (item.get("company_name") or "").upper()
        return (base != key, not base.startswith(key), not name.startswith(key), item["symbol"])

    items = sorted(results.values(), key=rank)
    try:
        normalized = normalize_symbol(text)
    except InvalidSymbolError:
        normalized = None
    return {"query": text, "items": items[:limit], "total": len(items), "normalized": normalized,
            "note": "Company names appear once a stock has been analysed or seeded."
                    + (f" Stored companies could not be searched ({db_error})." if db_error else "")}


@router.get("/{symbol}/history", summary="Daily prices (from MongoDB, fetched from Yahoo if missing)")
def stock_history(symbol: str = SYMBOL, period: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|2y)$")) -> dict:
    # Validated input first, database afterwards (see errors.py / Phase 2 decision).
    db = get_database()
    since = utc_now() - timedelta(days=PERIOD_DAYS[period])
    docs = list(db[MARKET_DATA].find({"symbol": symbol, "date": {"$gte": since}}, {"_id": 0}).sort("date", ASCENDING))
    source = "mongodb (originally yahoo_finance_via_yfinance)"
    if len(docs) < 5:  # nothing stored yet: fetch, validate, store, then answer
        try:
            history = get_price_history(symbol, period=period)
        except NoDataError as exc:
            raise AppError(404, "stock_not_found", str(exc)) from exc
        except DataError as exc:
            raise AppError(502, "data_source_unavailable", str(exc)) from exc
        store_price_history(db, history)
        docs = list(db[MARKET_DATA].find({"symbol": symbol, "date": {"$gte": since}}, {"_id": 0}).sort("date", ASCENDING))
        source = history.source
    records = [{"date": d["date"].date().isoformat(), **{k: d[k] for k in ("open", "high", "low", "close",
                                                                          "adjusted_close", "volume")}}
               for d in docs]
    return {"symbol": symbol, "period": period, "source": source, "records": records,
            "data_as_of": records[-1]["date"] if records else None,
            "fetched_at": docs[-1]["fetched_at"] if docs else None}


@router.get("/{symbol}/indicators", summary="Indicator series for charts (computed in Python)")
def stock_indicators(symbol: str = SYMBOL, period: str = Query("1y", pattern="^(6mo|1y)$")) -> dict:
    """Computed on 2 years of prices so SMA200 is defined across the whole displayed period."""
    try:
        history = get_price_history(symbol, period="2y", settings=get_settings())
    except NoDataError as exc:
        raise AppError(404, "stock_not_found", str(exc)) from exc
    except DataError as exc:
        raise AppError(502, "data_source_unavailable", str(exc)) from exc
    ind = ti.compute_indicators(history.frame)
    cutoff = ind.index[-1] - timedelta(days=PERIOD_DAYS[period])
    window = ind[ind.index > cutoff]
    columns = ["close", "volume", "sma_20", "sma_50", "sma_200", "ema_12", "ema_26", "rsi_14", "macd",
               "macd_signal", "macd_histogram", "bb_upper", "bb_middle", "bb_lower"]
    series = [{"date": d.strftime("%Y-%m-%d"), **{c: (None if row[c] != row[c] else round(float(row[c]), 4))
                                                   for c in columns}}
              for d, row in window.iterrows()]
    return {
        "symbol": symbol, "period": period, "series": series,
        "latest": ti.latest_snapshot(ind), "trend": ti.classify_trend(ind),
        "rsi_zone": ti.rsi_zone(ti.latest_snapshot(ind)["rsi_14"]),
        "settings": {"sma": [20, 50, 200], "ema": [12, 26], "rsi": 14, "macd": [12, 26, 9], "bollinger": [20, 2]},
        "source": history.source, "fetched_at": history.fetched_at, "data_as_of": history.report.last_date,
        "warnings": history.report.warnings,
    }


@router.get("/{symbol}", summary="Stored company information for one symbol")
def get_stock(symbol: str = SYMBOL) -> dict:
    db = get_database()
    doc = find_one(db, STOCKS, {"symbol": symbol})
    if doc is None:
        raise AppError(404, "stock_not_found",
                       f"No stored company data for {symbol} yet. Run an analysis for it first.")
    return doc
