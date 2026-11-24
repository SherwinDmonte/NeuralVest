"""Market overview endpoints (Phase 12B).

* GET /api/market/indices  - NIFTY 50 and SENSEX: last close, the change from the previous
  close and a short series for sparklines.
* GET /api/market/breadth  - gainers, losers, advancers and decliners ACROSS NEURALVEST'S
  CURATED LIST OF 30 LARGE NSE STOCKS (seed_symbols.json). This is not whole-market breadth:
  there is no free market-wide source, and scraping NSE is against its terms. Every response
  says so in `universe`.

All figures are end of day from Yahoo Finance (via yfinance), use the file cache (12 h by
default) and are computed here in Python: change % = (last close / previous close - 1) x 100
on adjusted closes. Nothing is real time.
"""

import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Query

from app.api.errors import AppError
from app.config import get_settings
from app.data.errors import DataError
from app.data.stock_data import get_price_history
from app.data.errors import InvalidSymbolError
from app.data.symbols import load_seed_symbols, normalize_symbol

router = APIRouter(prefix="/api/market", tags=["market"])
logger = logging.getLogger("neuralvest.market")

INDICES = {"^NSEI": "NIFTY 50", "^BSESN": "SENSEX"}
UNIVERSE = ("NeuralVest's curated list of 30 large NSE stocks (not an index and not the whole market); "
            "end of day prices from Yahoo Finance")
RULE = "change = (last adjusted close / previous adjusted close - 1) x 100"
SPARK_POINTS = 60
TOP_N = 5
WORKERS = 4  # polite to Yahoo; the price cache makes later calls instant
_lock = threading.Lock()  # one breadth computation at a time


def _day_change(symbol: str, period: str = "3mo") -> dict[str, Any]:
    history = get_price_history(symbol, period=period, settings=get_settings())
    frame = history.frame.dropna(subset=["adjusted_close"])
    if len(frame) < 2:
        raise DataError(f"not enough prices for {symbol}")
    last, prev = frame.iloc[-1], frame.iloc[-2]
    change = (float(last["adjusted_close"]) / float(prev["adjusted_close"]) - 1) * 100
    return {
        "symbol": symbol,
        "last_close": round(float(last["close"]), 2),
        "previous_close": round(float(prev["close"]), 2),
        "change_pct": round(change, 2),
        "date": frame.index[-1].strftime("%Y-%m-%d"),
        "previous_date": frame.index[-2].strftime("%Y-%m-%d"),
        "fetched_at": history.fetched_at,
        "series": [{"date": d.strftime("%Y-%m-%d"), "close": round(float(c), 2)}
                   for d, c in frame["close"].tail(SPARK_POINTS).items()],
    }


@router.get("/indices", summary="NIFTY 50 and SENSEX: last close, day change and a short series")
def market_indices() -> dict:
    items, errors = [], {}
    for symbol, name in INDICES.items():
        try:
            items.append({"name": name, **_day_change(symbol)})
        except DataError as exc:
            errors[symbol] = str(exc)
    if not items:
        raise AppError(502, "data_source_unavailable", "Index prices are unavailable right now.", errors)
    return {"items": items, "unavailable": errors, "rule": RULE,
            "note": "End of day data from Yahoo Finance via yfinance; not real time."}


@router.get("/breadth", summary="Gainers, losers, advancers and decliners across the 30 curated stocks")
def market_breadth(top: int = Query(TOP_N, ge=1, le=10)) -> dict:
    symbols = load_seed_symbols()["symbols"]
    started = time.perf_counter()
    rows, errors = [], {}
    with _lock, ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {s: pool.submit(_day_change, s, "1mo") for s in symbols}
        for s, f in futures.items():
            try:
                row = f.result()
                row.pop("series", None)
                rows.append(row)
            except DataError as exc:
                errors[s] = str(exc)
            except Exception as exc:  # one bad symbol must not break the overview
                logger.warning("breadth: %s failed: %s", s, exc.__class__.__name__)
                errors[s] = exc.__class__.__name__
    if not rows:
        raise AppError(502, "data_source_unavailable", "Prices for the curated stocks are unavailable right now.")
    # Compare like with like: only stocks whose last bar is the most common (latest) trading day.
    as_of = Counter(r["date"] for r in rows).most_common(1)[0][0]
    current = [r for r in rows if r["date"] == as_of]
    stale = sorted(r["symbol"] for r in rows if r["date"] != as_of)
    ranked = sorted(current, key=lambda r: r["change_pct"], reverse=True)
    return {
        "universe": UNIVERSE,
        "rule": RULE,
        "as_of": as_of,
        "counted": len(current),
        "advancers": sum(1 for r in current if r["change_pct"] > 0),
        "decliners": sum(1 for r in current if r["change_pct"] < 0),
        "unchanged": sum(1 for r in current if r["change_pct"] == 0),
        "gainers": [r for r in ranked if r["change_pct"] > 0][:top],
        "losers": [r for r in reversed(ranked) if r["change_pct"] < 0][:top],
        "rows": ranked,
        "left_out": {"different_last_date": stale, "unavailable": errors},
        "seconds": round(time.perf_counter() - started, 1),
    }


MAX_QUOTES = 20


@router.get("/quotes", summary="Last close, day change and a short series for up to 20 symbols (watchlist)")
def market_quotes(symbols: str = Query(..., min_length=1, max_length=600,
                                       description="Comma separated, e.g. RELIANCE.NS,TCS.NS")) -> dict:
    try:
        wanted = list(dict.fromkeys(normalize_symbol(s) for s in symbols.split(",") if s.strip()))
    except InvalidSymbolError as exc:
        raise AppError(422, "validation_error", str(exc)) from exc
    if not wanted or len(wanted) > MAX_QUOTES:
        raise AppError(422, "validation_error", f"Give 1 to {MAX_QUOTES} symbols.")
    items, errors = [], {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {s: pool.submit(_day_change, s, "3mo") for s in wanted}
        for s, f in futures.items():
            try:
                items.append(f.result())
            except DataError as exc:
                errors[s] = str(exc)
    return {"items": items, "unavailable": errors, "rule": RULE,
            "note": "End of day data from Yahoo Finance via yfinance; not real time."}
