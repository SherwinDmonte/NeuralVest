"""Background analysis runner (architecture §7, database_design §6).

* One worker thread (ThreadPoolExecutor(max_workers=1)): analyses run one at a time to
  protect RAM. API requests never wait for an analysis; they get a request_id and poll.
* The job record in `analysis_reports` is created BEFORE the job is queued, with the full
  request parameters, so nothing is lost if the server stops.
* Progress: LangGraph `stream(..., stream_mode="updates")` reports each finished node, so
  the status endpoint can show which agent is running right now.
* Every status change is appended to `status_history`; nothing is overwritten silently.
* Startup recovery: `queued` jobs are re-queued; `running` jobs become `interrupted`
  (completed agent results are kept, unfinished ones are marked interrupted).
"""

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pymongo import ASCENDING
from pymongo.database import Database

from app.api.errors import AppError
from app.config import Settings, get_settings
from app.data.symbols import normalize_symbol
from app.database.models import (
    AGENT_RESULTS,
    ANALYSIS_REPORTS,
    AnalysisReportDocument,
    RiskReportDocument,
    SectionRef,
    StatusEvent,
)
from app.agents.portfolio_optimizer import portfolio_document
from app.agents.risk_assessment import risk_report_fields
from app.database.repository import insert_document, upsert_document
from app.orchestration.graph import build_graph, initial_state
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.runner")

# Agents in execution order. Portfolio Optimization runs only for portfolio requests.
AGENT_ORDER = ["market_research", "financial_news", "stock_analysis", "risk_assessment", "portfolio_optimization"]
PORTFOLIO_AGENT = "portfolio_optimization"
TERMINAL = ("completed", "partial", "failed", "interrupted")
MAX_PENDING_JOBS = 5


def _event(status: str, reason: str | None = None) -> dict:
    return StatusEvent(status=status, reason=reason).model_dump()


class AnalysisRunner:
    def __init__(
        self,
        db: Database,
        settings: Settings | None = None,
        llm=None,
        workflow_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.llm = llm
        # Tests inject a factory that builds the graph with fakes.
        self.workflow_factory = workflow_factory or (
            lambda include_gdelt: build_graph(llm=self.llm, db=self.db, settings=self.settings,
                                              include_gdelt=include_gdelt))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
        self._lock = threading.Lock()
        self._progress: dict[str, dict[str, str]] = {}  # request_id -> {agent: status}
        self._pending: list[str] = []  # queue order, for queue positions

    # ---------------------------------------------------------------- submit
    def submit(self, symbols: list[str], include_gdelt: bool = False, user_id: str | None = None,
               investment_amount: float | None = None, risk_preference: str = "moderate",
               portfolio_options: dict | None = None) -> dict:
        normalized = list(dict.fromkeys(normalize_symbol(s) for s in symbols))
        with self._lock:
            if len(self._pending) >= MAX_PENDING_JOBS:
                raise AppError(429, "queue_full", "Too many analyses are waiting. Try again in a few minutes.")
        request_id = uuid.uuid4().hex
        if investment_amount and len(normalized) >= 2:
            request_type = "portfolio"
        else:
            request_type = "single_stock" if len(normalized) == 1 else "multi_stock"
        params = {"symbols": normalized, "include_gdelt": include_gdelt, "request_type": request_type}
        if request_type == "portfolio":
            params |= {"investment_amount": investment_amount, "risk_preference": risk_preference,
                       "portfolio_options": portfolio_options or {}}
        doc = AnalysisReportDocument(report_id=uuid.uuid4().hex, request_id=request_id, user_id=user_id,
                                     symbols=normalized, request_params=params, status="queued",
                                     status_history=[StatusEvent(status="queued")])
        insert_document(self.db, doc)  # persisted BEFORE queuing
        self._enqueue(request_id, params)
        return {"request_id": request_id, "report_id": doc.report_id, "status": "queued", "symbols": normalized}

    def _enqueue(self, request_id: str, params: dict) -> None:
        with self._lock:
            self._pending.append(request_id)
            self._progress[request_id] = {a: "pending" for a in AGENT_ORDER}
            if params.get("request_type") != "portfolio":
                self._progress[request_id][PORTFOLIO_AGENT] = "skipped"
        self._executor.submit(self._run, request_id, params)

    # ---------------------------------------------------------------- worker
    def _set_status(self, request_id: str, status: str, reason: str | None = None, extra: dict | None = None) -> None:
        self.db[ANALYSIS_REPORTS].update_one(
            {"request_id": request_id},
            {"$set": {"status": status, **(extra or {})}, "$push": {"status_history": _event(status, reason)}},
        )

    def _run(self, request_id: str, params: dict) -> None:
        with self._lock:
            if request_id in self._pending:
                self._pending.remove(request_id)
        try:
            self._set_status(request_id, "running")
            state = initial_state(params["symbols"], request_id=request_id,
                                  investment_amount=params.get("investment_amount"),
                                  risk_preference=params.get("risk_preference") or "moderate",
                                  portfolio_options=params.get("portfolio_options"))
            graph = self.workflow_factory(include_gdelt=params.get("include_gdelt", False))
            self._mark(request_id, AGENT_ORDER[0], "running")
            final = dict(state)
            for update in graph.stream(state, stream_mode="updates"):
                for node, values in update.items():
                    final.update({k: v for k, v in (values or {}).items()})
                    statuses = (values or {}).get("agent_status", {})
                    for agent, status in statuses.items():
                        if agent in AGENT_ORDER:
                            self._mark(request_id, agent, status)
                            nxt = AGENT_ORDER.index(agent) + 1
                            if (nxt < len(AGENT_ORDER) and status in ("completed", "partial")
                                    and self._progress.get(request_id, {}).get(AGENT_ORDER[nxt]) == "pending"):
                                self._mark(request_id, AGENT_ORDER[nxt], "running")
                    if node == "report":
                        final["final_report"] = values.get("final_report", {})
            self._finish(request_id, final)
        except Exception as exc:  # never leave a job stuck in "running"
            logger.exception("Analysis %s failed", request_id)
            self._set_status(request_id, "failed", f"internal error: {exc.__class__.__name__}",
                             {"completed_at": utc_now(),
                              "error_summary": [{"agent": "runner", "message": "Unexpected error during analysis."}]})
        finally:
            with self._lock:
                progress = self._progress.get(request_id, {})
                for agent, status in progress.items():
                    if status in ("pending", "running"):
                        progress[agent] = "skipped"
            if self.llm is not None and hasattr(self.llm, "unload"):
                try:
                    self.llm.unload()  # free the model's RAM between analyses
                except Exception:  # pragma: no cover - best effort
                    logger.warning("Could not unload the LLM after %s", request_id)

    def _mark(self, request_id: str, agent: str, status: str) -> None:
        with self._lock:
            self._progress.setdefault(request_id, {})[agent] = status

    def _finish(self, request_id: str, final: dict) -> None:
        """Write the report: references to agent_results + small headlines (database_design §2)."""
        report = final.get("final_report") or {}
        status = report.get("status", "failed")
        results = list(self.db[AGENT_RESULTS].find({"request_id": request_id}, {"_id": 1, "agent_name": 1}))

        def ids(agent: str) -> list:
            return [r["_id"] for r in results if r["agent_name"] == agent]

        market_headline = {
            s: {k: v.get(k) for k in ("last_close", "last_close_date", "period_return_pct", "rsi_zone")}
               | {"trend": (v.get("trend") or {}).get("classification"), "status": v.get("status")}
            for s, v in final.get("market_analysis", {}).items()}
        fundamentals_headline = {
            s: {k: v.get(k) for k in ("overall", "assessments", "status")}
               | {"pe": ((v.get("metrics") or {}).get("pe") or {}).get("value"),
                  "roe_pct": ((v.get("metrics") or {}).get("roe_pct") or {}).get("value")}
            for s, v in final.get("stock_analysis", {}).items()}
        risk = final.get("risk_analysis") or {}
        risk_symbols = risk.get("per_symbol") or {}
        risk_headline = {s: {"risk_classification": v.get("risk_classification"),
                             "annualized_volatility_pct": v.get("annualized_volatility_pct"),
                             "beta": (v.get("beta") or {}).get("value"), "status": v.get("status")}
                         for s, v in risk_symbols.items()}
        if risk.get("portfolio"):
            risk_headline["__portfolio__"] = {"diversification": risk["portfolio"].get("diversification")}
        news_headline = {
            s: {k: v.get(k) for k in ("overall_sentiment", "articles_analyzed", "sentiment_breakdown", "status")}
            for s, v in final.get("news_analysis", {}).items()}
        portfolio = final.get("portfolio_analysis") or {}
        portfolio_headline = ({k: portfolio.get(k) for k in ("status", "portfolio_id", "method",
                                                             "investment_amount", "leftover_cash_inr")}
                              | {"weights_pct": {a["symbol"]: a["weight_pct"] for a in portfolio.get("allocations", [])}}
                              if portfolio else {})
        fields = {
            "final_summary": report,
            "error_summary": final.get("errors", []),
            "market_analysis": SectionRef(agent_result_ids=ids("market_research"), headline=market_headline).model_dump(),
            "news_analysis": SectionRef(agent_result_ids=ids("financial_news"), headline=news_headline).model_dump(),
            "fundamental_analysis": SectionRef(agent_result_ids=ids("stock_analysis"),
                                               headline=fundamentals_headline).model_dump(),
            "risk_analysis": SectionRef(agent_result_ids=ids("risk_assessment"), headline=risk_headline).model_dump(),
            "portfolio_analysis": (SectionRef(agent_result_ids=ids(PORTFOLIO_AGENT), headline=portfolio_headline)
                                   .model_dump() if portfolio else None),
            "generated_at": utc_now(),
            "completed_at": utc_now(),
        }
        self._set_status(request_id, status, None, fields)
        self._write_risk_report(request_id, risk_symbols, risk.get("portfolio"), ids("risk_assessment"))
        self._write_portfolio(request_id, portfolio, ids(PORTFOLIO_AGENT))

    def _write_portfolio(self, request_id: str, portfolio: dict, source_ids: list) -> None:
        """Write-once `portfolios` projection, only for a successful allocation."""
        if portfolio.get("status") not in ("completed", "partial") or not portfolio.get("allocations"):
            return
        job = self.db[ANALYSIS_REPORTS].find_one({"request_id": request_id}, {"user_id": 1})
        try:
            doc = portfolio_document(portfolio, request_id, source_ids, (job or {}).get("user_id"))
            upsert_document(self.db, doc, ["request_id"])
        except Exception as exc:  # a projection must never break the job
            logger.error("portfolios not written for %s: %s", request_id, exc.__class__.__name__)

    def _write_risk_report(self, request_id: str, per_symbol: dict, portfolio: dict | None, source_ids: list) -> None:
        """Write-once `risk_reports` projection. It REQUIRES the risk-free rate used (decision D4),
        so it is only written when the rate is configured."""
        rfr = self.settings.risk_free_rate
        if not per_symbol:
            return
        if rfr is None:
            logger.warning("risk_reports not written for %s: risk-free rate not configured", request_id)
            return
        try:
            doc = RiskReportDocument(request_id=request_id, risk_free_rate=rfr, source_agent_result_ids=source_ids,
                                     **risk_report_fields(per_symbol, portfolio))
            upsert_document(self.db, doc, ["request_id"])
        except Exception as exc:  # a projection must never break the job
            logger.error("risk_reports not written for %s: %s", request_id, exc.__class__.__name__)

    # ---------------------------------------------------------------- status
    def status(self, request_id: str) -> dict | None:
        job = self.db[ANALYSIS_REPORTS].find_one({"request_id": request_id})
        if job is None:
            return None
        with self._lock:
            live = dict(self._progress.get(request_id, {}))
            position = self._pending.index(request_id) + 1 if request_id in self._pending else None
        agents = live or self._agents_from_db(request_id, job["status"], job.get("request_params") or {})
        return {
            "request_id": request_id,
            "report_id": job["report_id"],
            "status": job["status"],
            "symbols": job["symbols"],
            "agents": agents,
            "queue_position": position,
            "status_history": [{"status": e["status"], "at": e["at"], "reason": e.get("reason")}
                               for e in job.get("status_history", [])],
            "interrupted_reason": job.get("interrupted_reason"),
            "errors": job.get("error_summary", []),
            "requested_at": job.get("requested_at"),
            "completed_at": job.get("completed_at"),
        }

    def _agents_from_db(self, request_id: str, job_status: str, params: dict | None = None) -> dict[str, str]:
        """After a restart (no live progress) derive agent states from agent_results."""
        found: dict[str, list[str]] = {}
        for r in self.db[AGENT_RESULTS].find({"request_id": request_id}, {"agent_name": 1, "execution_status": 1}):
            found.setdefault(r["agent_name"], []).append(r["execution_status"])
        agents = {}
        for agent in AGENT_ORDER:
            statuses = found.get(agent)
            if not statuses:
                not_needed = agent == PORTFOLIO_AGENT and (params or {}).get("request_type") != "portfolio"
                agents[agent] = ("pending" if job_status in ("queued", "running") and not not_needed
                                 else "skipped")
            elif all(s == "completed" for s in statuses):
                agents[agent] = "completed"
            elif any(s in ("completed", "partial") for s in statuses):
                agents[agent] = "partial"
            else:
                agents[agent] = statuses[0]
        return agents

    # ---------------------------------------------------------------- recovery
    def recover(self) -> dict[str, int]:
        """Run once at startup, before new jobs are accepted."""
        jobs = self.db[ANALYSIS_REPORTS]
        interrupted = 0
        for job in jobs.find({"status": "running"}, {"request_id": 1}):
            jobs.update_one(
                {"request_id": job["request_id"]},
                {"$set": {"status": "interrupted", "interrupted_reason": "server_restart_during_run",
                          "completed_at": utc_now()},
                 "$push": {"status_history": _event("interrupted", "server_restart_during_run")}})
            self.db[AGENT_RESULTS].update_many(
                {"request_id": job["request_id"], "execution_status": {"$in": ["pending", "running"]}},
                {"$set": {"execution_status": "interrupted", "updated_at": utc_now()}})
            interrupted += 1
        requeued = 0
        for job in jobs.find({"status": "queued"}).sort("requested_at", ASCENDING):
            jobs.update_one({"request_id": job["request_id"]},
                            {"$push": {"status_history": _event("queued", "requeued_after_restart")}})
            self._enqueue(job["request_id"], job["request_params"])
            requeued += 1
        if interrupted or requeued:
            logger.warning("Startup recovery: %d interrupted, %d re-queued", interrupted, requeued)
        return {"interrupted": interrupted, "requeued": requeued}

    def rerun(self, request_id: str) -> dict:
        """Re-run an interrupted/failed analysis as a NEW request linked by retry_of."""
        job = self.db[ANALYSIS_REPORTS].find_one({"request_id": request_id})
        if job is None:
            raise AppError(404, "analysis_not_found", "No analysis with this request_id.")
        if job["status"] not in ("interrupted", "failed"):
            raise AppError(409, "not_rerunnable", "Only interrupted or failed analyses can be re-run.")
        params = job["request_params"]
        new = self.submit(job["symbols"], params.get("include_gdelt", False), job.get("user_id"),
                          investment_amount=params.get("investment_amount"),
                          risk_preference=params.get("risk_preference") or "moderate",
                          portfolio_options=params.get("portfolio_options"))
        self.db[ANALYSIS_REPORTS].update_one({"request_id": new["request_id"]}, {"$set": {"retry_of": request_id}})
        return {**new, "retry_of": request_id}

    def wait_idle(self, timeout: float = 60) -> None:
        """Block until queued work is done (used by tests)."""
        self._executor.submit(lambda: None).result(timeout=timeout)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
