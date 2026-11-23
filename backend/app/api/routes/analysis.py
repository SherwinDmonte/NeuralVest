"""Analysis endpoints: start a background analysis, poll its status, read its results."""

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field, field_validator

from app.api.errors import AppError
from app.data.errors import InvalidSymbolError
from app.data.symbols import normalize_symbol
from app.database.database import ensure_storage_available
from app.database.models import AGENT_RESULTS, ANALYSIS_REPORTS, FINANCIAL_NEWS
from app.database.repository import serialize_document

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
REQUEST_ID = Path(pattern=r"^[0-9a-f]{32}$", description="request_id returned by POST /api/analysis/start")


class StartAnalysisRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=10, examples=[["RELIANCE.NS"]])
    include_gdelt: bool = Field(default=False, description="Also query GDELT (slower, often rate-limited)")

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


@router.post("/start", status_code=202, summary="Start an analysis in the background")
def start_analysis(body: StartAnalysisRequest, request: Request) -> dict:
    runner = _runner(request)
    ensure_storage_available(runner.settings)  # 507 if the free-tier quota is nearly full
    job = runner.submit(body.symbols, include_gdelt=body.include_gdelt)
    return {**job, "status_url": f"/api/analysis/{job['request_id']}/status"}


@router.get("/{request_id}/status", summary="Progress of an analysis (poll every 2-3 s)")
def analysis_status(request: Request, request_id: str = REQUEST_ID) -> dict:
    status = _runner(request).status(request_id)
    if status is None:
        raise AppError(404, "analysis_not_found", "No analysis with this request_id.")
    return status


@router.post("/{request_id}/rerun", status_code=202, summary="Re-run an interrupted or failed analysis")
def rerun_analysis(request: Request, request_id: str = REQUEST_ID) -> dict:
    return _runner(request).rerun(request_id)


@router.get("/{request_id}", summary="Full results of an analysis")
def analysis_result(request: Request, request_id: str = REQUEST_ID) -> dict:
    runner = _runner(request)
    db = runner.db
    job = db[ANALYSIS_REPORTS].find_one({"request_id": request_id})
    if job is None:
        raise AppError(404, "analysis_not_found", "No analysis with this request_id.")
    agents: dict[str, dict] = {}
    for doc in db[AGENT_RESULTS].find({"request_id": request_id}):
        output = doc["output"]
        if doc["agent_name"] == "financial_news":
            # Articles live in financial_news (authoritative); the result holds references.
            hashes = output.get("article_url_hashes", [])
            articles = {a["url_hash"]: serialize_document(a) for a in db[FINANCIAL_NEWS].find(
                {"symbol": doc["symbol"], "url_hash": {"$in": hashes}})}
            output = {**output, "articles": [articles[h] for h in hashes if h in articles]}
        agents.setdefault(doc["agent_name"], {})[doc["scope_key"]] = output
    return {
        "request_id": request_id,
        "status": job["status"],
        "symbols": job["symbols"],
        "requested_at": job.get("requested_at"),
        "completed_at": job.get("completed_at"),
        "report": job.get("final_summary"),
        "market_research": agents.get("market_research", {}),
        "financial_news": agents.get("financial_news", {}),
        "stock_analysis": agents.get("stock_analysis", {}),
        "errors": job.get("error_summary", []),
        "retry_of": job.get("retry_of"),
    }
