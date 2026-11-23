"""LangGraph workflow (Phase 5 graph, extended by one agent per phase).

    START -> validate_input --(no valid symbol)----------------------------> report -> END
                     |
                     v
              market_research --(no symbol succeeded)--------------------> report
                     |
                     v
              financial_news -> stock_analysis -> risk_assessment --(single stock / no amount)--> report
                                                        |
                                                        v (portfolio request: >= 2 stocks + amount)
                                                 portfolio_optimization -------------------------> report

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
from pydantic import ValidationError
from pymongo.database import Database

from app.agents.common import LLMClient
from app.agents.financial_news import run_financial_news
from app.agents.market_research import run_market_research
from app.agents.portfolio_optimizer import run_portfolio_optimization
from app.agents.risk_assessment import run_risk_assessment
from app.agents.stock_analysis import run_stock_analysis
from app.config import Settings, get_settings
from app.data.errors import DataError, InvalidSymbolError
from app.data.stock_data import get_benchmark_history
from app.data.symbols import base_ticker, normalize_symbol
from app.orchestration.state import NeuralVestState
from app.schemas.agents import PortfolioOptimizationInput
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
        if amount is not None and len(symbols) < 2:
            errors.append({"agent": "validate_input", "symbol": None,
                           "message": "A portfolio needs at least 2 valid stocks; the amount was ignored."})
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

    def risk_assessment(state: NeuralVestState) -> dict[str, Any]:
        """Reuses the prices in the shared state (fetched once by Market Research)."""
        started_at, t0 = utc_now(), time.perf_counter()
        records = {s: state["market_data"][s]["records"] for s in state["stock_symbols"]
                   if state.get("market_analysis", {}).get(s, {}).get("status") in OK_STATUSES
                   and s in state.get("market_data", {})}
        try:  # NIFTY 50: already in the file cache from the Market Research Agent (no new download)
            bench = get_benchmark_history(period="2y", settings=settings).frame
        except DataError:
            bench = None
        results, portfolio = run_risk_assessment(records, benchmark_frame=bench, llm=llm, db=db,
                                                 request_id=state.get("request_id"), settings=settings)
        statuses = [o.status for o in results.values()] + ([portfolio.status] if portfolio else [])
        errors = [{"agent": "risk_assessment", "symbol": s, "message": e} for s, o in results.items() for e in o.errors]
        sources = [d.model_dump(mode="json") | {"agent": "risk_assessment", "symbol": s}
                   for s, o in results.items() for d in o.data_sources]
        return {"risk_analysis": {"per_symbol": {s: o.model_dump(mode="json") for s, o in results.items()},
                                  "portfolio": portfolio.model_dump(mode="json") if portfolio else None},
                "errors": errors, "data_sources": sources,
                "agent_status": {"risk_assessment": _aggregate(statuses)},
                "timestamps": _timing("risk_assessment", started_at, t0)}

    def portfolio_optimization(state: NeuralVestState) -> dict[str, Any]:
        """Runs only for portfolio requests, after Risk Assessment: it uses the same prices and
        leaves out stocks whose risk could not be measured."""
        started_at, t0 = utc_now(), time.perf_counter()
        risk = (state.get("risk_analysis") or {}).get("per_symbol") or {}
        records = {s: state["market_data"][s]["records"] for s in state["stock_symbols"]
                   if state.get("market_analysis", {}).get(s, {}).get("status") in OK_STATUSES
                   and s in state.get("market_data", {})}
        try:
            request = PortfolioOptimizationInput(
                symbols=state["stock_symbols"], investment_amount=state["investment_amount"],
                risk_preference=state.get("risk_preference") or "moderate", **(state.get("portfolio_options") or {}))
        except ValidationError as exc:
            message = "Invalid portfolio settings: " + "; ".join(e["msg"] for e in exc.errors())
            return {"portfolio_analysis": {"status": "failed", "errors": [message]},
                    "errors": [{"agent": "portfolio_optimization", "symbol": None, "message": message}],
                    "agent_status": {"portfolio_optimization": "failed"},
                    "timestamps": _timing("portfolio_optimization", started_at, t0)}
        try:
            bench = get_benchmark_history(period="2y", settings=settings).frame
        except DataError:
            bench = None
        out = run_portfolio_optimization(records, request, benchmark_frame=bench, risk_per_symbol=risk, llm=llm,
                                         db=db, request_id=state.get("request_id"), settings=settings)
        return {"portfolio_analysis": out.model_dump(mode="json"),
                "errors": [{"agent": "portfolio_optimization", "symbol": None, "message": e} for e in out.errors],
                "data_sources": [d.model_dump(mode="json") | {"agent": "portfolio_optimization", "symbol": None}
                                 for d in out.data_sources],
                "agent_status": {"portfolio_optimization": out.status},
                "timestamps": _timing("portfolio_optimization", started_at, t0)}

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
            risk = (state.get("risk_analysis", {}).get("per_symbol") or {}).get(symbol, {})
            sections[symbol] = {
                "company_name": mr.get("company_name"),
                "market_research": {k: mr.get(k) for k in ("status", "last_close", "last_close_date", "trend",
                                                           "indicators", "rsi_zone", "benchmark_comparison",
                                                           "explanation")},
                "financial_news": {k: news.get(k) for k in ("status", "overall_sentiment", "sentiment_breakdown",
                                                            "digest", "articles_analyzed", "disclaimer")},
                "stock_analysis": {k: sa.get(k) for k in ("status", "overall", "assessments", "strengths",
                                                          "weaknesses", "statement_periods", "explanation")},
                "risk_assessment": {k: risk.get(k) for k in ("status", "risk_classification", "annualized_volatility_pct",
                                                             "beta", "max_drawdown", "sharpe", "readings",
                                                             "explanation", "disclaimer")},
            }
        portfolio_risk = (state.get("risk_analysis") or {}).get("portfolio")
        po = state.get("portfolio_analysis") or {}
        portfolio = None
        if po:
            bk = po.get("backtest") or {}
            portfolio = {k: po.get(k) for k in ("status", "portfolio_id", "investment_amount", "risk_preference",
                                                "method", "method_label", "fallback_reason", "allocations",
                                                "invested_inr", "leftover_cash_inr", "expected_metrics", "readings",
                                                "explanation", "warnings", "errors", "disclaimer")}
            portfolio["backtest"] = ({k: v for k, v in bk.items() if k not in ("equity_curve", "rebalances")}
                                     if bk else None)
        return {"final_report": {"status": overall, "request_id": state.get("request_id"),
                                 "portfolio_risk": portfolio_risk, "portfolio": portfolio,
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
    graph.add_node("risk_assessment", risk_assessment)
    graph.add_node("portfolio_optimization", portfolio_optimization)
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
    graph.add_edge("stock_analysis", "risk_assessment")
    graph.add_conditional_edges(
        "risk_assessment",
        lambda s: "portfolio_optimization" if s.get("request_type") == "portfolio" else "report",
        {"portfolio_optimization": "portfolio_optimization", "report": "report"},
    )
    graph.add_edge("portfolio_optimization", "report")
    graph.add_edge("report", END)
    return graph.compile()


def initial_state(symbols: list[str], request_id: str | None = None, user_id: str | None = None,
                  investment_amount: float | None = None, risk_preference: str = "moderate",
                  portfolio_options: dict[str, Any] | None = None) -> NeuralVestState:
    return NeuralVestState(
        request_id=request_id or uuid.uuid4().hex, user_id=user_id, raw_symbols=list(symbols),
        investment_amount=investment_amount, risk_preference=risk_preference,
        portfolio_options=dict(portfolio_options or {}),
        market_data={}, market_analysis={}, news_data={}, news_analysis={}, financial_data={},
        stock_analysis={}, risk_analysis={}, portfolio_analysis={},
        agent_status={}, errors=[], data_sources=[], timestamps={}, final_report={},
    )
