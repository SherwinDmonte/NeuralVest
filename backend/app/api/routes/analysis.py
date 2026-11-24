"""Analysis endpoints: start a background analysis, poll its status, read its results."""

from typing import Literal

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import AnalysisUser, get_app_settings, require_access, user_id_of
from app.api.errors import AppError
from app.api.rate_limit import rate_limit
from app.data.errors import InvalidSymbolError
from app.data.symbols import normalize_symbol
from app.database.database import ensure_storage_available
from app.database.models import AGENT_RESULTS, ANALYSIS_REPORTS, FINANCIAL_NEWS
from app.database.repository import serialize_document
from app.utils.urls import safe_http_url
from app.schemas.agents import MAX_INVESTMENT_INR, PortfolioConstraints, PortfolioMethod, RiskPreferenceLiteral

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
REQUEST_ID = Path(pattern=r"^[0-9a-f]{32}$", description="request_id returned by POST /api/analysis/start")


class PortfolioOptions(BaseModel):
    """Optional Portfolio Optimization settings; the defaults follow the risk preference."""
    method: PortfolioMethod | None = None
    constraints: PortfolioConstraints = Field(default_factory=PortfolioConstraints)
    target_volatility_pct: float | None = Field(default=None, gt=0, le=200)
    target_return_pct: float | None = Field(default=None, ge=-100, le=500)
    rebalance: Literal["monthly", "quarterly", "none"] = "quarterly"
    transaction_cost_bps: float = Field(default=10.0, ge=0, le=200)


class StartAnalysisRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=10, examples=[["RELIANCE.NS"]])
    include_gdelt: bool = Field(default=False, description="Also query GDELT (slower, often rate-limited)")
    investment_amount: float | None = Field(default=None, gt=0, le=MAX_INVESTMENT_INR,
                                            description="INR; with 2+ stocks this adds Portfolio Optimization")
    risk_preference: RiskPreferenceLiteral = "moderate"
    portfolio: PortfolioOptions | None = None

    @model_validator(mode="after")
    def _portfolio_needs_two_stocks(self) -> "StartAnalysisRequest":
        if self.investment_amount is not None and len(self.symbols) < 2:
            raise ValueError("a portfolio (investment_amount) needs at least 2 different stocks")
        return self

    @field_validator("symbols")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        out = []
        for v in values:
            try:
                out.append(normalize_symbol(v))
            except InvalidSymbolError as exc:
                raise ValueError(str(exc)) from exc
        return list(dict.fromkeys(out))


def _runner(request: Request):
    runner = getattr(request.app.state, "runner", None)
    if runner is None:
        raise AppError(503, "database_not_configured",
                       "Analyses need MongoDB. Configure MONGODB_URI in backend/.env and restart the API.")
    return runner


NOT_FOUND = "No analysis with this request_id."


def _job(request: Request, request_id: str, user: dict | None, projection: dict | None = None) -> dict:
    """The job record if this user may see it (404 otherwise, also for other users' jobs)."""
    job = _runner(request).db[ANALYSIS_REPORTS].find_one({"request_id": request_id}, projection)
    return require_access(job, user, get_app_settings(request), "analysis_not_found", NOT_FOUND)


@router.post("/start", status_code=202, summary="Start an analysis in the background",
             dependencies=[Depends(rate_limit("analysis"))])
def start_analysis(body: StartAnalysisRequest, request: Request, user: AnalysisUser) -> dict:
    runner = _runner(request)
    ensure_storage_available(runner.settings)  # 507 if the free-tier quota is nearly full
    job = runner.submit(body.symbols, include_gdelt=body.include_gdelt, user_id=user_id_of(user),
                        investment_amount=body.investment_amount,
                        risk_preference=body.risk_preference,
                        portfolio_options=body.portfolio.model_dump(mode="json", exclude_none=True)
                        if body.portfolio else None)
    return {**job, "status_url": f"/api/analysis/{job['request_id']}/status"}


@router.get("/{request_id}/status", summary="Progress of an analysis (poll every 2-3 s)")
def analysis_status(request: Request, user: AnalysisUser, request_id: str = REQUEST_ID) -> dict:
    _job(request, request_id, user, {"user_id": 1})  # access check; the job record is written on submit
    status = _runner(request).status(request_id)
    if status is None:
        raise AppError(404, "analysis_not_found", NOT_FOUND)
    return status


@router.post("/{request_id}/rerun", status_code=202, summary="Re-run an interrupted or failed analysis",
             dependencies=[Depends(rate_limit("analysis"))])
def rerun_analysis(request: Request, user: AnalysisUser, request_id: str = REQUEST_ID) -> dict:
    _job(request, request_id, user, {"user_id": 1})
    return _runner(request).rerun(request_id)


@router.get("/{request_id}/report", summary="The unified report of a finished analysis")
def analysis_report(request: Request, user: AnalysisUser, request_id: str = REQUEST_ID) -> dict:
    job = _job(request, request_id, user, {"status": 1, "final_summary": 1, "agent_runs": 1, "completed_at": 1,
                                           "user_id": 1, "report_id": 1})
    if not job.get("final_summary"):
        raise AppError(409, "report_not_ready", f"The analysis is {job['status']}; the report is not available yet.")
    return {"request_id": request_id, "report_id": job.get("report_id"), "status": job["status"],
            "completed_at": job.get("completed_at"), "pdf_url": f"/api/reports/{job.get('report_id')}/pdf",
            "agent_runs": job.get("agent_runs"), "report": job["final_summary"]}


@router.get("/{request_id}", summary="Full results of an analysis")
def analysis_result(request: Request, user: AnalysisUser, request_id: str = REQUEST_ID) -> dict:
    db = _runner(request).db
    job = _job(request, request_id, user)
    return assemble_result(db, job)


def assemble_result(db, job: dict) -> dict:
    """The job record plus every agent result of the request (also used by GET /api/reports/{id})."""
    request_id = job["request_id"]
    agents: dict[str, dict] = {}
    for doc in db[AGENT_RESULTS].find({"request_id": request_id}):
        output = doc["output"]
        if doc["agent_name"] == "financial_news":
            # Articles live in financial_news (authoritative); the result holds references.
            hashes = output.get("article_url_hashes", [])
            articles = {a["url_hash"]: serialize_document(a) for a in db[FINANCIAL_NEWS].find(
                {"symbol": doc["symbol"], "url_hash": {"$in": hashes}})}
            # URLs are validated again before they are returned (task 11.3.3)
            output = {**output, "articles": [{**articles[h], "article_url": safe_http_url(articles[h].get("article_url"))}
                                             for h in hashes if h in articles]}
        agents.setdefault(doc["agent_name"], {})[doc["scope_key"]] = output
    return {
        "request_id": request_id,
        "report_id": job.get("report_id"),
        "status": job["status"],
        "symbols": job["symbols"],
        "requested_at": job.get("requested_at"),
        "completed_at": job.get("completed_at"),
        "report": job.get("final_summary"),
        "market_research": agents.get("market_research", {}),
        "financial_news": agents.get("financial_news", {}),
        "stock_analysis": agents.get("stock_analysis", {}),
        "risk_assessment": agents.get("risk_assessment", {}),  # per symbol + "__request__" (correlation)
        "portfolio_optimization": agents.get("portfolio_optimization", {}).get("__request__"),
        "errors": job.get("error_summary", []),
        "retry_of": job.get("retry_of"),
        # Phase 12 (Agent Monitoring page): per-node timings, status and retries, plus the
        # output-validation summary (both null until the workflow has finished)
        "agent_runs": job.get("agent_runs"),
        "validation_summary": job.get("validation_summary"),
    }
