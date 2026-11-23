"""Portfolio endpoints (Phase 9).

* POST /api/portfolio/optimize  - illustrative allocation + backtest, computed immediately
  (a few seconds, no LLM: the explanation is the rule-based template). If MongoDB is
  configured the result is saved (job record, agent result, `portfolios` projection) so it
  can be read again with GET /api/portfolio/{portfolio_id}.
* POST /api/portfolio/backtest  - walk-forward backtest only, over 2 or 5 years; nothing stored.
* GET  /api/portfolio/{portfolio_id} - a saved allocation with its full result.
Full analyses with AI explanations go through POST /api/analysis/start with an investment_amount.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field, field_validator

from app.agents.portfolio_optimizer import backtest_rule, optimisation_kwargs, portfolio_document, \
    run_portfolio_optimization
from app.agents.risk_assessment import frame_from_records
from app.analysis import backtesting as bt
from app.analysis import optimization as opt
from app.api.errors import AppError
from app.config import get_settings
from app.data.errors import DataError, InvalidSymbolError, NoDataError
from app.data.stock_data import get_benchmark_history, get_price_history
from app.data.symbols import normalize_symbol
from app.database.database import ensure_storage_available
from app.database.models import AGENT_RESULTS, ANALYSIS_REPORTS, PORTFOLIOS, AnalysisReportDocument, StatusEvent
from app.database.repository import insert_document, serialize_document, upsert_document
from app.schemas.agents import PORTFOLIO_DISCLAIMER, PortfolioConstraints, PortfolioMethod, \
    PortfolioOptimizationInput, RiskPreferenceLiteral
from app.utils.timing import utc_now

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
PORTFOLIO_ID = Path(pattern=r"^[0-9a-f]{32}$", description="portfolio_id returned by POST /api/portfolio/optimize")


def _normalize(values: list[str]) -> list[str]:
    try:
        return list(dict.fromkeys(normalize_symbol(v) for v in values))
    except InvalidSymbolError as exc:
        raise ValueError(str(exc)) from exc


class OptimizeRequest(PortfolioOptimizationInput):
    symbols: list[str] = Field(min_length=2, max_length=10, examples=[["RELIANCE.NS", "TCS.NS", "INFY.NS"]])

    @field_validator("symbols")
    @classmethod
    def _symbols(cls, values: list[str]) -> list[str]:
        out = _normalize(values)
        if len(out) < 2:
            raise ValueError("a portfolio needs at least 2 different stocks")
        return out


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=10, examples=[["RELIANCE.NS", "TCS.NS"]])
    risk_preference: RiskPreferenceLiteral = "moderate"
    method: PortfolioMethod | None = None
    constraints: PortfolioConstraints = Field(default_factory=PortfolioConstraints)
    target_volatility_pct: float | None = Field(default=None, gt=0, le=200)
    target_return_pct: float | None = Field(default=None, ge=-100, le=500)
    returns_model: Literal["mean", "ema"] = "mean"
    covariance_model: Literal["ledoit_wolf", "sample"] = "ledoit_wolf"
    period: Literal["2y", "5y"] = Field(default="2y", description="Total history; the first year is used "
                                                                  "only for estimation")
    rebalance: Literal["monthly", "quarterly", "none"] = "quarterly"
    transaction_cost_bps: float = Field(default=10.0, ge=0, le=200)
    initial_capital: float = Field(default=100_000.0, gt=0, le=1_000_000_000)

    @field_validator("symbols")
    @classmethod
    def _symbols(cls, values: list[str]) -> list[str]:
        out = _normalize(values)
        if len(out) < 2:
            raise ValueError("a backtest needs at least 2 different stocks")
        return out


def _db(request: Request):
    runner = getattr(request.app.state, "runner", None)
    return runner.db if runner is not None else None


def _records(symbols: list[str], period: str, settings) -> tuple[dict, list[str]]:
    records, missing = {}, []
    for symbol in symbols:
        try:
            records[symbol] = get_price_history(symbol, period=period, settings=settings).to_records()
        except NoDataError:
            missing.append(symbol)
        except DataError as exc:
            raise AppError(502, "data_source_unavailable", str(exc)) from exc
    return records, missing


def _benchmark(period: str, settings):
    try:
        return get_benchmark_history(period=period, settings=settings).frame
    except DataError:
        return None


@router.post("/optimize", summary="Illustrative allocation (weights, rupees, whole shares) + backtest")
def optimize_portfolio(body: OptimizeRequest, request: Request) -> dict:
    settings = get_settings()
    records, missing = _records(body.symbols, "2y", settings)
    if len(records) < 2:
        raise AppError(404, "stock_not_found", f"Not enough stocks with price data (missing: {', '.join(missing)})")
    db = _db(request)
    request_id = uuid.uuid4().hex if db is not None else None
    if db is not None:
        ensure_storage_available(settings)
        insert_document(db, AnalysisReportDocument(
            report_id=uuid.uuid4().hex, request_id=request_id, symbols=body.symbols, status="running",
            request_params={"source": "api/portfolio/optimize", "request_type": "portfolio",
                            **body.model_dump(mode="json")},
            status_history=[StatusEvent(status="queued"), StatusEvent(status="running")]))
    out = run_portfolio_optimization(records, body, benchmark_frame=_benchmark("2y", settings), db=db,
                                     request_id=request_id, settings=settings)
    for symbol in missing:
        out.warnings.append(f"{symbol} was left out: no price data.")
    result = out.model_dump(mode="json")
    stored = False
    if db is not None:
        db[ANALYSIS_REPORTS].update_one(
            {"request_id": request_id},
            {"$set": {"status": out.status, "completed_at": utc_now(), "generated_at": utc_now(),
                      "error_summary": [{"agent": "portfolio_optimization", "message": e} for e in out.errors]},
             "$push": {"status_history": StatusEvent(status=out.status).model_dump()}})
        if out.status != "failed" and out.allocations:
            ids = [d["_id"] for d in db[AGENT_RESULTS].find({"request_id": request_id}, {"_id": 1})]
            upsert_document(db, portfolio_document(result, request_id, ids), ["request_id"])
            stored = True
    if out.status == "failed":
        raise AppError(422, "portfolio_infeasible", out.errors[0] if out.errors else "Portfolio could not be optimised.")
    return {**result, "request_id": request_id, "stored": stored, "not_found": missing}


@router.post("/backtest", summary="Walk-forward backtest of an allocation rule (nothing stored)")
def backtest_portfolio(body: BacktestRequest) -> dict:
    settings = get_settings()
    records, missing = _records(body.symbols, body.period, settings)
    if len(records) < 2:
        raise AppError(404, "stock_not_found", f"Not enough stocks with price data (missing: {', '.join(missing)})")
    rfr = settings.risk_free_rate
    try:
        frames = {s: frame_from_records(r)["adjusted_close"] for s, r in records.items()}
        prices = opt.price_matrix(frames)
        c = body.constraints
        chosen = opt.resolve_settings(body.risk_preference, len(frames), body.method, c.min_weight_pct / 100,
                                      None if c.max_weight_pct is None else c.max_weight_pct / 100)
        result = backtest_rule(prices, chosen["method"], optimisation_kwargs(body, chosen, rfr),
                               rebalance=body.rebalance, cost_bps=body.transaction_cost_bps,
                               capital=body.initial_capital, benchmark=_benchmark_close(body.period, settings))
    except (opt.OptimizationError, bt.BacktestError) as exc:
        raise AppError(422, "backtest_not_possible", str(exc)) from exc
    return {"symbols": list(frames), "not_found": missing, "method": chosen["method"],
            "method_label": opt.METHOD_LABELS[chosen["method"]], "constraints": {
                "min_weight_pct": round(chosen["min_weight"] * 100, 2),
                "max_weight_pct": round(chosen["max_weight"] * 100, 2), "notes": chosen["notes"]},
            "risk_free_rate": rfr, "backtest": result, "disclaimer": PORTFOLIO_DISCLAIMER}


def _benchmark_close(period: str, settings):
    frame = _benchmark(period, settings)
    return frame["adjusted_close"] if frame is not None and len(frame) else None


@router.get("/{portfolio_id}", summary="A saved allocation with its full result")
def get_portfolio(request: Request, portfolio_id: str = PORTFOLIO_ID) -> dict:
    db = _db(request)
    if db is None:
        raise AppError(503, "database_not_configured",
                       "Saved portfolios need MongoDB. Configure MONGODB_URI in backend/.env and restart the API.")
    doc = db[PORTFOLIOS].find_one({"portfolio_id": portfolio_id})
    if doc is None:
        raise AppError(404, "portfolio_not_found", "No portfolio with this portfolio_id.")
    full = db[AGENT_RESULTS].find_one({"request_id": doc["request_id"], "agent_name": "portfolio_optimization"})
    return {"portfolio": serialize_document(doc), "result": full["output"] if full else None}
