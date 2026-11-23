"""Shared workflow state (docs/architecture.md §4).

One dictionary travels through the LangGraph graph. Each agent reads what it needs and
writes ONLY its own section. Bookkeeping fields use reducers, so updates are merged instead of
overwritten. This matters when agents run in parallel (Phase 10).

Every value is JSON-serialisable (records, not DataFrames), so the state can be checkpointed
and stored. In parallel mode several agents write at the same time: each writes only its own
key, and the shared bookkeeping keys merge (dicts) or append (lists) through their reducers.
"""

import operator
from typing import Annotated, Any, Literal, TypedDict


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


RiskPreference = Literal["conservative", "moderate", "aggressive"]


class NeuralVestState(TypedDict, total=False):
    # ----- request -----
    request_id: str
    user_id: str | None
    raw_symbols: list[str]  # as typed by the user
    stock_symbols: list[str]  # validated + normalized, e.g. ["RELIANCE.NS"]
    investment_amount: float | None
    risk_preference: RiskPreference
    # Optional Portfolio Optimization settings (method, constraints, rebalance, costs), Phase 9
    portfolio_options: dict[str, Any]
    request_type: Literal["single_stock", "portfolio"]

    # ----- agent outputs (each written by exactly one agent; keyed by symbol) -----
    market_data: Annotated[dict[str, Any], merge_dicts]  # prices shared with later agents
    market_analysis: Annotated[dict[str, Any], merge_dicts]
    news_data: Annotated[dict[str, Any], merge_dicts]  # collection stats per symbol
    news_analysis: Annotated[dict[str, Any], merge_dicts]
    financial_data: Annotated[dict[str, Any], merge_dicts]  # Phase 7
    stock_analysis: Annotated[dict[str, Any], merge_dicts]  # Phase 7
    risk_analysis: Annotated[dict[str, Any], merge_dicts]  # Phase 8
    portfolio_analysis: dict[str, Any]  # Phase 9 (request level: one allocation per request)

    # ----- supervisor (Phase 10) -----
    execution_plan: dict[str, Any]  # which agents run, which are skipped and why; sequential/parallel
    workflow_started_at: str  # ISO time; the retry time budget is measured from it
    validation: dict[str, Any]  # output-validation summary (issues, portfolio candidates)
    retries: Annotated[list[dict[str, Any]], operator.add]  # {agent, symbol, attempt, retried, reason, at}

    # ----- bookkeeping -----
    agent_status: Annotated[dict[str, str], merge_dicts]
    errors: Annotated[list[dict[str, Any]], operator.add]  # {agent, symbol, message}
    data_sources: Annotated[list[dict[str, Any]], operator.add]
    timestamps: Annotated[dict[str, dict], merge_dicts]  # {node: {started_at, finished_at, duration_s}}

    final_report: dict[str, Any]
