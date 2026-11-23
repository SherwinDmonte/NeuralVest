"""LangGraph workflow: the supervisor and the five agents (Phase 10).

Sequential mode (default, 8 GB RAM):

    START -> validate_input --(no valid symbol)--------------------------------------> report -> END
                   |
                   v
            market_research --(no symbol has prices)---------------------------------> report
                   |
                   v
            financial_news -> stock_analysis -> risk_assessment -> output_validation
                                                                        |
                                    (portfolio request and >= 2 validated stocks)
                                                                        v
                                                          portfolio_optimization -> report
                                                     (otherwise) -------------------> report

Parallel mode (AGENT_EXECUTION_MODE=parallel): after market_research the three middle agents
are started together (fan-out) and output_validation waits for all of them (deferred node).
Only network waits overlap: LLM inferences stay one at a time (OllamaClient lock).

Each agent node returns only the state keys it owns. The supervisor rules (validation,
routing, retries, output checks) live in supervisor.py; the report in
services/report_generator.py.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pymongo.database import Database

from app.agents.common import LLMClient
from app.agents.financial_news import run_financial_news
from app.agents.market_research import run_market_research
from app.agents.portfolio_optimizer import run_portfolio_optimization
from app.agents.risk_assessment import run_risk_assessment
from app.agents.stock_analysis import run_stock_analysis
from app.config import Settings, get_settings
from app.data.errors import DataError
from app.data.stock_data import get_benchmark_history
from app.data.symbols import base_ticker
from app.orchestration import supervisor as sup
from app.orchestration.state import NeuralVestState
from app.schemas.agents import PortfolioOptimizationInput
from app.services.report_generator import build_report
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.graph")

MAX_SYMBOLS = sup.MAX_SYMBOLS
OK_STATUSES = sup.OK_STATUSES
NODE_RETRY = RetryPolicy(max_attempts=2, initial_interval=2.0, retry_on=sup.transient_exception)


def _aggregate(statuses: list[str]) -> str:
    """Per-symbol statuses -> one agent status. 'skipped' symbols (e.g. an index for the
    fundamentals agent) do not count as failures."""
    statuses = [s for s in statuses if s != "skipped"] or (["skipped"] if statuses else [])
    if not statuses or statuses == ["skipped"]:
        return "skipped"
    if all(s == "completed" for s in statuses):
        return "completed"
    if any(s in OK_STATUSES for s in statuses):
        return "partial"
    return "failed"


def _timing(name: str, started_at: datetime, t0: float) -> dict:
    return {name: {"started_at": started_at.isoformat(), "finished_at": utc_now().isoformat(),
                   "duration_s": round(time.perf_counter() - t0, 2)}}


def _sources(agent: str, symbol: str | None, out) -> list[dict]:
    return [s.model_dump(mode="json") | {"agent": agent, "symbol": symbol} for s in out.data_sources]


def _errors(agent: str, symbol: str | None, out) -> list[dict]:
    return [{"agent": agent, "symbol": symbol, "message": e} for e in out.errors]


def build_graph(llm: LLMClient | None = None, db: Database | None = None, settings: Settings | None = None,
                include_gdelt: bool = True, news_transport=None, mode: str | None = None, checkpointer=None,
                sleep=time.sleep):
    """Compile the workflow. Dependencies (LLM client, database, checkpointer) are injected, so
    tests can run the same graph with fakes. `mode` overrides AGENT_EXECUTION_MODE."""
    settings = settings or get_settings()
    mode = mode or settings.agent_execution_mode

    def retry(call, output_of, agent: str, symbol: str | None, state):
        return sup.run_with_retry(call, output_of, agent=agent, symbol=symbol, state=state, settings=settings,
                                  sleep=sleep)

    def usable(state) -> list[str]:
        return [s for s in state["stock_symbols"]
                if state.get("market_analysis", {}).get(s, {}).get("status") in OK_STATUSES]

    # ------------------------------------------------------------ supervisor nodes
    def validate_input(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        return {**sup.validate_request(state, mode), "timestamps": _timing("validate_input", started_at, t0)}

    def output_validation(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        updates = sup.validate_outputs(state)
        sup.persist_corrections(db, state.get("request_id"), updates.pop("_corrections"))
        return {**updates, "agent_status": {"output_validation": "completed"},
                "timestamps": _timing("output_validation", started_at, t0)}

    # ------------------------------------------------------------ agent nodes
    def market_research(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, market_data, errors, sources, statuses, retries = {}, {}, [], [], [], []
        for symbol in state["stock_symbols"]:
            (out, history), events = retry(
                lambda s=symbol: run_market_research(s, llm=llm, db=db, request_id=state.get("request_id"),
                                                     settings=settings),
                lambda r: r[0], "market_research", symbol, state)
            retries += events
            analysis[symbol] = out.model_dump(mode="json")
            statuses.append(out.status)
            sources += _sources("market_research", symbol, out)
            errors += _errors("market_research", symbol, out)
            if history is not None:
                market_data[symbol] = {"records": history.to_records(), **history.provenance(),
                                       "validation": history.report.model_dump()}
        return {"market_analysis": analysis, "market_data": market_data, "errors": errors, "data_sources": sources,
                "retries": retries, "agent_status": {"market_research": _aggregate(statuses)},
                "timestamps": _timing("market_research", started_at, t0)}

    def financial_news(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, stats, errors, sources, statuses, retries = {}, {}, [], [], [], []
        for symbol in usable(state):  # no reliable prices for a symbol: news is skipped, not guessed
            mr = state["market_analysis"][symbol]
            company = mr.get("company_name") or base_ticker(symbol)
            out, events = retry(
                lambda s=symbol, c=company: run_financial_news(
                    s, c, llm=llm, db=db, request_id=state.get("request_id"), include_gdelt=include_gdelt,
                    settings=settings, transport=news_transport),
                lambda r: r, "financial_news", symbol, state)
            retries += events
            analysis[symbol] = out.model_dump(mode="json")
            stats[symbol] = {"collected": out.articles_collected, "analyzed": out.articles_analyzed,
                             "duplicates_removed": out.duplicates_removed, "source_status": out.source_status}
            statuses.append(out.status)
            sources += _sources("financial_news", symbol, out)
            errors += _errors("financial_news", symbol, out)
        return {"news_analysis": analysis, "news_data": stats, "errors": errors, "data_sources": sources,
                "retries": retries, "agent_status": {"financial_news": _aggregate(statuses)},
                "timestamps": _timing("financial_news", started_at, t0)}

    def stock_analysis(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, fin_data, errors, sources, statuses, retries = {}, {}, [], [], [], []
        for symbol in usable(state):
            mr = state["market_analysis"][symbol]
            (out, fs), events = retry(
                lambda s=symbol, m=mr: run_stock_analysis(
                    s, last_close=m.get("last_close"), price_date=m.get("last_close_date"), llm=llm, db=db,
                    request_id=state.get("request_id"), settings=settings),
                lambda r: r[0], "stock_analysis", symbol, state)
            retries += events
            analysis[symbol] = out.model_dump(mode="json")
            if fs is not None:
                fin_data[symbol] = {"latest_period": fs.latest_period, "missing_key_items": fs.missing_key_items,
                                    "is_stale": fs.is_stale, "source": fs.source,
                                    "fetched_at": fs.fetched_at.isoformat()}
            statuses.append(out.status)
            sources += _sources("stock_analysis", symbol, out)
            errors += _errors("stock_analysis", symbol, out)
        return {"stock_analysis": analysis, "financial_data": fin_data, "errors": errors, "data_sources": sources,
                "retries": retries, "agent_status": {"stock_analysis": _aggregate(statuses)},
                "timestamps": _timing("stock_analysis", started_at, t0)}

    def risk_assessment(state: NeuralVestState) -> dict[str, Any]:
        """Reuses the prices in the shared state (fetched once by Market Research)."""
        started_at, t0 = utc_now(), time.perf_counter()
        records = {s: state["market_data"][s]["records"] for s in usable(state) if s in state.get("market_data", {})}
        try:  # NIFTY 50: already in the file cache from the Market Research Agent (no new download)
            bench = get_benchmark_history(period="2y", settings=settings).frame
        except DataError:
            bench = None
        results, portfolio = run_risk_assessment(records, benchmark_frame=bench, llm=llm, db=db,
                                                 request_id=state.get("request_id"), settings=settings)
        statuses = [o.status for o in results.values()] + ([portfolio.status] if portfolio else [])
        errors = [e for s, o in results.items() for e in _errors("risk_assessment", s, o)]
        sources = [d for s, o in results.items() for d in _sources("risk_assessment", s, o)]
        return {"risk_analysis": {"per_symbol": {s: o.model_dump(mode="json") for s, o in results.items()},
                                  "portfolio": portfolio.model_dump(mode="json") if portfolio else None},
                "errors": errors, "data_sources": sources,
                "agent_status": {"risk_assessment": _aggregate(statuses)},
                "timestamps": _timing("risk_assessment", started_at, t0)}

    def portfolio_optimization(state: NeuralVestState) -> dict[str, Any]:
        """Runs only for portfolio requests with >= 2 stocks that passed output validation."""
        started_at, t0 = utc_now(), time.perf_counter()
        candidates = (state.get("validation") or {}).get("portfolio_candidates") or []
        records = {s: state["market_data"][s]["records"] for s in candidates if s in state.get("market_data", {})}
        request = PortfolioOptimizationInput(  # options were validated in validate_input
            symbols=state["stock_symbols"], investment_amount=state["investment_amount"],
            risk_preference=state.get("risk_preference") or "moderate", **(state.get("portfolio_options") or {}))
        try:
            bench = get_benchmark_history(period="2y", settings=settings).frame
        except DataError:
            bench = None
        risk = (state.get("risk_analysis") or {}).get("per_symbol") or {}
        out = run_portfolio_optimization(records, request, benchmark_frame=bench, risk_per_symbol=risk, llm=llm,
                                         db=db, request_id=state.get("request_id"), settings=settings)
        return {"portfolio_analysis": out.model_dump(mode="json"), "errors": _errors("portfolio_optimization", None, out),
                "data_sources": _sources("portfolio_optimization", None, out),
                "agent_status": {"portfolio_optimization": out.status},
                "timestamps": _timing("portfolio_optimization", started_at, t0)}

    def report(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        final = build_report(state, llm=llm, use_llm=settings.report_llm_summary)
        return {"final_report": final, "agent_status": {"report": "completed"},
                "timestamps": _timing("report", started_at, t0)}

    # ------------------------------------------------------------ wiring
    graph = StateGraph(NeuralVestState)
    graph.add_node("validate_input", validate_input)
    for name, fn in (("market_research", market_research), ("financial_news", financial_news),
                     ("stock_analysis", stock_analysis), ("risk_assessment", risk_assessment),
                     ("portfolio_optimization", portfolio_optimization)):
        graph.add_node(name, fn, retry_policy=NODE_RETRY)
    # deferred: in parallel mode it waits until every fan-out branch has finished
    graph.add_node("output_validation", output_validation, defer=(mode == "parallel"))
    graph.add_node("report", report)

    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges("validate_input", sup.route_after_validation,
                                {"market_research": "market_research", "report": "report"})
    graph.add_conditional_edges("market_research", sup.route_after_market_research,
                                {"financial_news": "financial_news", "stock_analysis": "stock_analysis",
                                 "risk_assessment": "risk_assessment", "report": "report"})
    if mode == "parallel":
        for agent in sup.MIDDLE_AGENTS:
            graph.add_edge(agent, "output_validation")
    else:
        graph.add_edge("financial_news", "stock_analysis")
        graph.add_edge("stock_analysis", "risk_assessment")
        graph.add_edge("risk_assessment", "output_validation")
    graph.add_conditional_edges("output_validation", sup.route_after_output_validation,
                                {"portfolio_optimization": "portfolio_optimization", "report": "report"})
    graph.add_edge("portfolio_optimization", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def make_checkpointer(settings: Settings):
    """Optional LangGraph SQLite checkpoints (WORKFLOW_CHECKPOINTS=true). Only for workflow
    snapshots, never as the application database. Returns None when disabled or when the
    optional package is not installed (a warning explains how to enable it)."""
    if not settings.workflow_checkpoints:
        return None
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        logger.warning("WORKFLOW_CHECKPOINTS=true but langgraph-checkpoint-sqlite is not installed; "
                       "running without checkpoints (pip install langgraph-checkpoint-sqlite)")
        return None
    path = settings.data_cache_dir / "checkpoints.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def run_config(request_id: str) -> dict:
    """LangGraph config: the request_id names the checkpoint thread."""
    return {"configurable": {"thread_id": request_id}}


def initial_state(symbols: list[str], request_id: str | None = None, user_id: str | None = None,
                  investment_amount: float | None = None, risk_preference: str = "moderate",
                  portfolio_options: dict[str, Any] | None = None) -> NeuralVestState:
    return NeuralVestState(
        request_id=request_id or uuid.uuid4().hex, user_id=user_id, raw_symbols=list(symbols),
        investment_amount=investment_amount, risk_preference=risk_preference,
        portfolio_options=dict(portfolio_options or {}),
        market_data={}, market_analysis={}, news_data={}, news_analysis={}, financial_data={},
        stock_analysis={}, risk_analysis={}, portfolio_analysis={}, execution_plan={}, validation={}, retries=[],
        agent_status={}, errors=[], data_sources=[], timestamps={}, final_report={},
    )
