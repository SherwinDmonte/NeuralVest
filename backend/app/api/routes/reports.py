"""Reports endpoints (Phase 11): the logged-in user's reports, one report, and its PDF.

* GET /api/reports               - your reports, newest first, paginated (login required)
* GET /api/reports/{report_id}    - one report with all its agent results
* GET /api/reports/{report_id}/pdf - the report as a PDF (generated on request, not stored)
Access follows api/deps.can_access: your own reports only; reports started without logging
in are readable by id while AUTH_REQUIRED=false.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response
from pymongo import ASCENDING, DESCENDING

from app.api.deps import AnalysisUser, CurrentUser, get_app_settings, get_db, require_access
from app.api.errors import AppError
from app.api.rate_limit import rate_limit
from app.api.routes.analysis import assemble_result
from app.database.models import AGENT_RESULTS, ANALYSIS_REPORTS, MARKET_DATA
from app.database.repository import find_page
from app.services.pdf_export import build_pdf, price_points

router = APIRouter(prefix="/api/reports", tags=["reports"])
REPORT_ID = Path(pattern=r"^[0-9a-f]{32}$", description="report_id from GET /api/reports or the analysis result")
NOT_FOUND = "No report with this report_id."
LIST_FIELDS = {"report_id": 1, "request_id": 1, "symbols": 1, "status": 1, "requested_at": 1, "completed_at": 1,
               "retry_of": 1, "request_params.request_type": 1, "request_params.investment_amount": 1,
               "final_summary.key_observations.items": 1, "final_summary.traceability.ok": 1}
PRICE_CHART_DAYS = 366


def _report(request: Request, report_id: str, user: dict | None, projection: dict | None = None) -> dict:
    doc = get_db(request)[ANALYSIS_REPORTS].find_one({"report_id": report_id}, projection)
    return require_access(doc, user, get_app_settings(request), "report_not_found", NOT_FOUND)


@router.get("", summary="Your reports (newest first, paginated)")
def list_reports(
    request: Request,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Literal["queued", "running", "completed", "partial", "failed", "interrupted"] | None = None,
    symbol: str | None = Query(None, pattern=r"^\^?[A-Z0-9&\-]{1,20}(\.(NS|BO))?$"),
) -> dict:
    query = {"user_id": user["user_id"]} | ({"status": status} if status else {}) | (
        {"symbols": symbol} if symbol else {})
    page_data = find_page(get_db(request), ANALYSIS_REPORTS, query, sort=[("requested_at", DESCENDING)],
                          page=page, page_size=page_size, projection=LIST_FIELDS)
    page_data["items"] = [_summary(d) for d in page_data["items"]]
    return page_data


def _summary(doc: dict) -> dict:
    summary = doc.get("final_summary") or {}
    params = doc.get("request_params") or {}
    return {
        "report_id": doc.get("report_id"), "request_id": doc.get("request_id"), "symbols": doc.get("symbols"),
        "status": doc.get("status"), "requested_at": doc.get("requested_at"),
        "completed_at": doc.get("completed_at"), "retry_of": doc.get("retry_of"),
        "request_type": params.get("request_type"), "investment_amount": params.get("investment_amount"),
        "report_ready": bool(summary),
        "key_observations": (summary.get("key_observations") or {}).get("items", [])[:2],
        "traceability_ok": (summary.get("traceability") or {}).get("ok"),
        "pdf_url": f"/api/reports/{doc.get('report_id')}/pdf" if summary else None,
    }


@router.get("/{report_id}", summary="One report with all its agent results")
def get_report(request: Request, user: AnalysisUser, report_id: str = REPORT_ID) -> dict:
    job = _report(request, report_id, user)
    return {**assemble_result(get_db(request), job), "pdf_url": f"/api/reports/{report_id}/pdf"
            if job.get("final_summary") else None}


@router.get("/{report_id}/pdf", summary="Download the report as a PDF",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}},
            dependencies=[Depends(rate_limit("pdf"))])
def report_pdf(request: Request, user: AnalysisUser, report_id: str = REPORT_ID) -> Response:
    job = _report(request, report_id, user)
    report = job.get("final_summary")
    if not report:
        raise AppError(409, "report_not_ready", f"The analysis is {job.get('status')}; the report is not available yet.")
    db = get_db(request)
    pdf = build_pdf(report, prices=_prices(db, report), equity_curve=_equity_curve(db, job["request_id"]))
    stamp = (report.get("generated_at") or "")[:10] or "report"
    name = f"neuralvest_{'_'.join(s.split('.')[0] for s in job.get('symbols', [])[:3])}_{stamp}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


def _prices(db, report: dict) -> dict:
    """Stored closing prices over the analysis window (only for the chart; values unchanged)."""
    out = {}
    overview = (report.get("sections") or {}).get("company_overview") or {}
    for sym in (report.get("request") or {}).get("symbols") or []:
        last = (overview.get(sym) or {}).get("last_close_date")
        try:
            end = datetime.combine(datetime.fromisoformat(last).date(), time.max, tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        docs = db[MARKET_DATA].find({"symbol": sym, "date": {"$gte": end - timedelta(days=PRICE_CHART_DAYS),
                                                             "$lte": end}},
                                    {"_id": 0, "date": 1, "close": 1}).sort("date", ASCENDING)
        out[sym] = price_points(list(docs))
    return out


def _equity_curve(db, request_id: str) -> list[dict]:
    doc = db[AGENT_RESULTS].find_one({"request_id": request_id, "agent_name": "portfolio_optimization"},
                                     {"output.backtest.equity_curve": 1})
    return (((doc or {}).get("output") or {}).get("backtest") or {}).get("equity_curve") or []
