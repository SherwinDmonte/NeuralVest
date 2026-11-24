"""Risk endpoint: historical risk metrics on demand (no LLM, nothing stored).

Used for quick comparisons (e.g. the Risk Analysis page in Phase 12). Full analyses with
explanations and persistence go through POST /api/analysis/start.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

import numpy as np

from app.agents.market_research import analysis_window
from app.agents.risk_assessment import frame_from_records, run_risk_assessment
from app.analysis import risk_metrics as rm
from app.api.deps import AnalysisUser
from app.api.errors import AppError
from app.api.rate_limit import rate_limit
from app.config import get_settings
from app.data.errors import DataError, InvalidSymbolError, NoDataError
from app.data.stock_data import get_benchmark_history, get_price_history
from app.data.symbols import normalize_symbol
from app.schemas.agents import RISK_DISCLAIMER

router = APIRouter(prefix="/api/risk", tags=["risk"])
# Phase 12: login like the other computations; shares the "portfolio" rate limit (RATE_LIMIT_PORTFOLIO).


class RiskRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=10, examples=[["RELIANCE.NS", "TCS.NS"]])
    period: Literal["6mo", "1y", "2y"] = "1y"
    weights: dict[str, float] | None = Field(default=None, description="Optional weights per symbol (any positive scale)")

    @field_validator("symbols")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        try:
            return list(dict.fromkeys(normalize_symbol(v) for v in values))
        except InvalidSymbolError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("weights")
    @classmethod
    def _positive(cls, weights):
        if weights is not None and any(w < 0 for w in weights.values()):
            raise ValueError("weights must not be negative (no short positions)")
        return {normalize_symbol(k): v for k, v in weights.items()} if weights else None


@router.post("/analyze", summary="Historical risk metrics for one or more stocks",
             dependencies=[Depends(rate_limit("portfolio"))])
def analyze_risk(body: RiskRequest, user: AnalysisUser) -> dict:
    settings = get_settings()
    lookback = "2y" if body.period in ("6mo", "1y") else "5y"
    records, missing = {}, []
    for symbol in body.symbols:
        try:
            history = get_price_history(symbol, period=lookback, settings=settings)
            records[symbol] = history.to_records()
        except NoDataError:
            missing.append(symbol)
        except DataError as exc:
            raise AppError(502, "data_source_unavailable", str(exc)) from exc
    if not records:
        raise AppError(404, "stock_not_found", f"No price data for: {', '.join(missing)}")
    try:
        bench = get_benchmark_history(period=lookback, settings=settings).frame
    except DataError:
        bench = None
    results, portfolio = run_risk_assessment(records, benchmark_frame=bench, period=body.period,
                                             weights=body.weights, settings=settings)
    return {
        "period": body.period,
        "symbols": {s: o.model_dump(mode="json", exclude={"explanation", "llm"}) for s, o in results.items()},
        "distribution": {s: return_histogram(records[s], body.period) for s in results},
        "portfolio": portfolio.model_dump(mode="json") if portfolio else None,
        "not_found": missing,
        "risk_free_rate": settings.risk_free_rate,
        "disclaimer": RISK_DISCLAIMER,
    }


HISTOGRAM_BINS = 21


def return_histogram(records: list[dict], period: str) -> dict:
    """Phase 12B: how often each size of daily move happened, from the SAME daily returns and
    window the Risk Assessment agent uses (simple returns of the adjusted close)."""
    window = analysis_window(frame_from_records(records), period)
    returns = rm.daily_returns(window["adjusted_close"]).dropna() * 100
    if len(returns) < 2:
        return {"bins": [], "observations": int(len(returns))}
    edge = float(np.ceil(max(abs(returns.min()), abs(returns.max()))))
    counts, edges = np.histogram(returns, bins=HISTOGRAM_BINS, range=(-edge, edge))
    return {
        "observations": int(len(returns)),
        "unit": "daily return, %",
        "bins": [{"from": round(float(a), 2), "to": round(float(b), 2), "count": int(c)}
                 for a, b, c in zip(edges[:-1], edges[1:], counts)],
    }
