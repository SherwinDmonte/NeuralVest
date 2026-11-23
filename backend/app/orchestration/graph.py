"""LangGraph workflow (Phase 5: minimal graph with the first two agents).

    START -> validate_input --(no valid symbol)----------------------------> report -> END
                     |
                     v
              market_research --(no symbol succeeded)--------------------> report
                     |
                     v
              financial_news -> stock_analysis --------------------------> report

Execution is sequential (8 GB RAM). Each node runs one agent for every symbol and returns
only the state keys it owns. The full supervisor (retries, output validation, agents 3-5,
optional parallel fan-out) is added in Phase 10.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from pymongo.database import Database

from app.agents.common import LLMClient
from app.agents.financial_news import run_financial_news
from app.agents.market_research import run_market_research
from app.agents.stock_analysis import run_stock_analysis
from app.config import Settings, get_settings
from app.data.errors import InvalidSymbolError
from app.data.symbols import base_ticker, normalize_symbol
from app.orchestration.state import NeuralVestState
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.graph")

MAX_SYMBOLS = 10
OK_STATUSES = ("completed", "partial")


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


def build_graph(llm: LLMClient | None = None, db: Database | None = None, settings: Settings | None = None,
                include_gdelt: bool = True, news_transport=None):
    """Compile the workflow. Dependencies (LLM client, database) are injected, so tests can
    run the same graph with fakes."""
    settings = settings or get_settings()

    # ------------------------------------------------------------ nodes
    def validate_input(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        symbols, errors = [], []
        for raw in state.get("raw_symbols", []):
            try:
                symbol = normalize_symbol(raw)
            except InvalidSymbolError as exc:
                errors.append({"agent": "validate_input", "symbol": str(raw), "message": str(exc)})
                continue
            if symbol not in symbols:
                symbols.append(symbol)
        if len(symbols) > MAX_SYMBOLS:
            errors.append({"agent": "validate_input", "symbol": None,
                           "message": f"At most {MAX_SYMBOLS} symbols per analysis; extra symbols ignored."})
            symbols = symbols[:MAX_SYMBOLS]
        if not symbols:
            errors.append({"agent": "validate_input", "symbol": None, "message": "No valid stock symbol provided."})

        amount = state.get("investment_amount")
        if amount is not None and amount <= 0:
            errors.append({"agent": "validate_input", "symbol": None, "message": "Investment amount must be positive."})
            amount = None
        request_type = "portfolio" if len(symbols) >= 2 and amount else "single_stock"
        return {"stock_symbols": symbols, "investment_amount": amount, "request_type": request_type,
                "errors": errors, "agent_status": {"validate_input": "completed" if symbols else "failed"},
                "timestamps": _timing("validate_input", started_at, t0)}

    def market_research(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, market_data, errors, sources, statuses = {}, {}, [], [], []
        for symbol in state["stock_symbols"]:
            out, history = run_market_research(symbol, llm=llm, db=db, request_id=state.get("request_id"),
                                               settings=settings)
            analysis[symbol] = out.model_dump(mode="json")
            statuses.append(out.status)
            sources += [s.model_dump(mode="json") | {"agent": "market_research", "symbol": symbol}
                        for s in out.data_sources]
            errors += [{"agent": "market_research", "symbol": symbol, "message": e} for e in out.errors]
            if history is not None:
                market_data[symbol] = {"records": history.to_records(), **history.provenance(),
                                       "validation": history.report.model_dump()}
        return {"market_analysis": analysis, "market_data": market_data, "errors": errors, "data_sources": sources,
                "agent_status": {"market_research": _aggregate(statuses)},
                "timestamps": _timing("market_research", started_at, t0)}

    def financial_news(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, stats, errors, sources, statuses = {}, {}, [], [], []
        for symbol in state["stock_symbols"]:
            mr = state.get("market_analysis", {}).get(symbol, {})
            if mr.get("status") not in OK_STATUSES:
                continue  # no reliable data for this symbol: news is skipped, not guessed
            company = mr.get("company_name") or base_ticker(symbol)
            out = run_financial_news(symbol, company, llm=llm, db=db, request_id=state.get("request_id"),
                                     include_gdelt=include_gdelt, settings=settings, transport=news_transport)
            analysis[symbol] = out.model_dump(mode="json")
            stats[symbol] = {"collected": out.articles_collected, "analyzed": out.articles_analyzed,
                             "duplicates_removed": out.duplicates_removed, "source_status": out.source_status}
            statuses.append(out.status)
            sources += [s.model_dump(mode="json") | {"agent": "financial_news", "symbol": symbol}
                        for s in out.data_sources]
            errors += [{"agent": "financial_news", "symbol": symbol, "message": e} for e in out.errors]
        return {"news_analysis": analysis, "news_data": stats, "errors": errors, "data_sources": sources,
                "agent_status": {"financial_news": _aggregate(statuses)},
                "timestamps": _timing("financial_news", started_at, t0)}

    def stock_analysis(state: NeuralVestState) -> dict[str, Any]:
        started_at, t0 = utc_now(), time.perf_counter()
        analysis, fin_data, errors, sources, statuses = {}, {}, [], [], []
        for symbol in state["stock_symbols"]:
            mr = state.get("market_analysis", {}).get(symbol, {})
            if mr.get("status") not in OK_STATUSES:
                continue
            out, fs = run_stock_analysis(symbol, last_close=mr.get("last_close"), price_date=mr.get("last_close_date"),
                                         llm=llm, db=db, request_id=state.get("request_id"), settings=settings)
            analysis[symbol] = out.model_dump(mode="json")
            if fs is not None:
                fin_data[symbol] = {"latest_period": fs.latest_period, "missing_key_items": fs.missing_key_items,
                                    "is_stale": fs.is_stale, "source": fs.source,
                                    "fetched_at": fs.fetched_at.isoformat()}
            statuses.append(out.status)
            sources += [s.model_dump(mode="json") | {"agent": "stock_analysis", "symbol": symbol}
                        for s in out.data_sources]
            errors += [{"agent": "stock_analysis", "symbol": symbol, "message": e} for e in out.errors]
        return {"stock_analysis": analysis, "financial_data": fin_data, "errors": errors, "data_sources": sources,
                "agent_status": {"stock_analysis": _aggregate(statuses)},
                "timestamps": _timing("stock_analysis", started_at, t0)}

    def report(state: NeuralVestState) -> dict[str, Any]:
        """REPORT STUB (Phase 5): collects key results per symbol. The full report with all
        sections, explanations and source references is generated in Phase 10."""
        statuses = {k: v for k, v in state.get("agent_status", {}).items() if k != "validate_input"}
        if not state.get("stock_symbols") or statuses.get("market_research") in (None, "failed", "skipped"):
            overall = "failed"
        elif all(v in ("completed", "skipped") for v in statuses.values()):
            overall = "completed"
        else:
            overall = "partial"
        sections = {}
        for symbol in state.get("stock_symbols", []):
            mr = state.get("market_analysis", {}).get(symbol, {})
            news = state.get("news_analysis", {}).get(symbol, {})
            sa = state.get("stock_analysis", {}).get(symbol, {})
            sections[symbol] = {
                "company_name": mr.get("company_name"),
                "market_research": {k: mr.get(k) for k in ("status", "last_close", "last_close_date", "trend",
                                                           "indicators", "rsi_zone", "benchmark_comparison",
                                                           "explanation")},
                "financial_news": {k: news.get(k) for k in ("status", "overall_sentiment", "sentiment_breakdown",
                                                            "digest", "articles_analyzed", "disclaimer")},
                "stock_analysis": {k: sa.get(k) for k in ("status", "overall", "assessments", "strengths",
                                                          "weaknesses", "statement_periods", "explanation")},
            }
        return {"final_report": {"status": overall, "request_id": state.get("request_id"),
                                 "symbols": state.get("stock_symbols", []), "sections": sections,
                                 "errors": state.get("errors", []), "generated_at": utc_now().isoformat(),
                                 "note": "Report stub (Phase 5). The full report is generated in Phase 10."},
                "agent_status": {"report": "completed"}}

    # ------------------------------------------------------------ wiring
    graph = StateGraph(NeuralVestState)
    graph.add_node("validate_input", validate_input)
    graph.add_node("market_research", market_research)
    graph.add_node("financial_news", financial_news)
    graph.add_node("stock_analysis", stock_analysis)
    graph.add_node("report", report)

    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges("validate_input", lambda s: "market_research" if s.get("stock_symbols") else "report",
                                {"market_research": "market_research", "report": "report"})
    graph.add_conditional_edges(
        "market_research",
        lambda s: "financial_news" if s.get("agent_status", {}).get("market_research") in OK_STATUSES else "report",
        {"financial_news": "financial_news", "report": "report"},
    )
    graph.add_edge("financial_news", "stock_analysis")
    graph.add_edge("stock_analysis", "report")
    graph.add_edge("report", END)
    return graph.compile()


def initial_state(symbols: list[str], request_id: str | None = None, user_id: str | None = None,
                  investment_amount: float | None = None, risk_preference: str = "moderate") -> NeuralVestState:
    return NeuralVestState(
        request_id=request_id or uuid.uuid4().hex, user_id=user_id, raw_symbols=list(symbols),
        investment_amount=investment_amount, risk_preference=risk_preference,
        market_data={}, market_analysis={}, news_data={}, news_analysis={}, financial_data={},
        stock_analysis={}, risk_analysis={}, portfolio_analysis={},
        agent_status={}, errors=[], data_sources=[], timestamps={}, final_report={},
    )
