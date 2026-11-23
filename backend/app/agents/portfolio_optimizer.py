"""Agent 5: Portfolio Optimization.

Responsibility: turn the selected stocks, an investment amount and a risk preference into an
ILLUSTRATIVE allocation (weights, rupee amounts, whole shares) and test the same allocation
rule on history (walk-forward backtest). It reuses the prices already in the workflow state
and only uses stocks whose risk could be measured. All numbers come from Python
(app/analysis/optimization.py and backtesting.py); the LLM only explains them.
This is not investment advice.
"""

import logging
import time
import uuid
from typing import Any

import pandas as pd
from pymongo.database import Database

from app.agents.common import LLMClient, save_agent_result
from app.agents.risk_assessment import frame_from_records
from app.analysis import backtesting as bt
from app.analysis import optimization as opt
from app.analysis import risk_metrics as rm
from app.config import Settings, get_settings
from app.database.models import PortfolioDocument, StockAllocation
from app.llm import prompts as p
from app.schemas.agents import DataSource, PortfolioOptimizationInput, PortfolioOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.portfolio_optimizer")
AGENT_NAME = "portfolio_optimization"
LEFTOVER_WARNING_PCT = 5.0
CONCENTRATION_WARNING_PCT = 40.0
SIMILAR_CAGR_PTS = 0.5  # backtest CAGRs closer than this are reported as "about the same"


def _money(value: float) -> str:
    return f"₹{value:,.0f}"


def readings(out: PortfolioOutput) -> dict[str, str]:
    r: dict[str, str] = {}
    label = opt.METHOD_LABELS.get(out.method or "", out.method)
    if out.fallback_reason:
        r["method_reading"] = f"the method actually used is {label}, because {out.fallback_reason}"
    elif out.method_source == "risk_preference":
        r["method_reading"] = f"the {label} method was used because the risk preference is {out.risk_preference}"
    else:
        r["method_reading"] = f"the {label} method was used as requested"
    held = [a for a in out.allocations if a["weight_pct"] > 0]
    if held:
        top, low = held[0], held[-1]
        r["split_reading"] = (f"the largest share of the money goes to {top['symbol']} ({top['weight_pct']}%)"
                              + (f" and the smallest to {low['symbol']} ({low['weight_pct']}%)" if low is not top else ""))
    zero = [a["symbol"] for a in out.allocations if a["weight_pct"] == 0]
    if zero:
        r["excluded_reading"] = f"the method gave no money to {', '.join(zero)}"
    eff = out.concentration.get("effective_number_of_stocks")
    if eff is not None:
        r["spread_reading"] = f"the money is spread like {eff} equally sized holdings (effective number of stocks)"
    em = out.expected_metrics
    if em.get("annual_return_pct") is not None:
        r["history_reading"] = (f"over the estimation window this mix had an average annual return of "
                                f"{em['annual_return_pct']}% with volatility of {em['annual_volatility_pct']}%; "
                                "these are past figures, not forecasts")
    bk = out.backtest
    if bk and bk.get("cagr_pct") is not None:
        eq = (bk["vs_benchmark"].get("equal_weight") or {}).get("cagr_pct")
        nifty = (bk["vs_benchmark"].get("nifty50") or {}).get("cagr_pct")
        text = (f"in the backtest from {bk['period']['from']} to {bk['period']['to']} the rule returned "
                f"{bk['cagr_pct']}% a year (CAGR, after costs), compared with {eq}% for equal weights")
        if nifty is not None:
            text += f" and {nifty}% for the NIFTY 50"
        pairs = [(name, v) for name, v in (("equal weights", eq), ("the NIFTY 50", nifty)) if v is not None]
        same = [n for n, v in pairs if abs(bk["cagr_pct"] - v) < SIMILAR_CAGR_PTS]
        better = [n for n, v in pairs if bk["cagr_pct"] - v >= SIMILAR_CAGR_PTS]
        worse = [n for n, v in pairs if v - bk["cagr_pct"] >= SIMILAR_CAGR_PTS]
        if better:
            text += f"; it did better than {' and '.join(better)}"
        if same:
            text += f"; it did about the same as {' and '.join(same)} (less than {SIMILAR_CAGR_PTS} points apart)"
        if worse:
            text += f"; it did worse than {' and '.join(worse)}"
        r["backtest_reading"] = text
    if out.invested_inr is not None:
        shares = sum(a["shares"] for a in out.allocations)
        r["cash_reading"] = (f"{shares} whole shares cost {_money(out.invested_inr)} and "
                             f"{_money(out.leftover_cash_inr)} is left as cash")
    return r


def _warnings(out: PortfolioOutput, result: opt.OptimizationResult, alloc: dict, notes: list[str]) -> list[str]:
    w = list(notes)
    if result.fallback_reason:
        w.append(f"Method changed: {result.fallback_reason[0].upper()}{result.fallback_reason[1:]}.")
    mu = result.expected_returns_pct
    if mu and all(v is not None and v < 0 for v in mu.values()):
        w.append("Every selected stock had a negative average return in the estimation window, so the allocation "
                 "is driven by limiting losses and volatility, not by expected gains.")
    for a in out.allocations:
        if a["weight_pct"] > 0 and a["shares"] == 0:
            w.append(f"The amount is too small to buy one share of {a['symbol']} "
                     f"(last price {_money(a['last_price'])}); its target weight stays in cash.")
    if alloc["leftover_pct"] > LEFTOVER_WARNING_PCT:
        w.append(f"{alloc['leftover_pct']}% of the amount stays as cash because only whole shares can be bought.")
    largest = out.concentration.get("largest_weight_pct")
    unavoidable = 100 / max(len(out.allocations), 1) + 0.01  # e.g. 50% with 2 stocks cannot be lower
    if largest is not None and largest > max(CONCENTRATION_WARNING_PCT, unavoidable):
        w.append(f"Concentrated: one stock receives {largest}% of the money.")
    return w


def optimisation_kwargs(inp: PortfolioOptimizationInput, chosen: dict, rfr: dict | None) -> dict[str, Any]:
    return {"min_weight": chosen["min_weight"], "max_weight": chosen["max_weight"],
            "risk_free_rate_pct": rfr["value_pct"] if rfr else None,
            "target_volatility_pct": inp.target_volatility_pct, "target_return_pct": inp.target_return_pct,
            "returns_model": inp.returns_model, "covariance_model": inp.covariance_model}


def backtest_rule(prices: pd.DataFrame, method: str, kwargs: dict[str, Any], *, rebalance: str,
                  cost_bps: float, capital: float, benchmark: pd.Series | None) -> dict[str, Any]:
    """Walk-forward backtest of `method` with the same settings as the live allocation."""
    def weight_fn(history: pd.DataFrame):
        r = opt.optimize(history, method, **kwargs)
        return r.weights, r.method, r.fallback_reason

    return bt.run_backtest(prices, weight_fn, lookback=opt.LOOKBACK_DAYS, rebalance=rebalance, cost_bps=cost_bps,
                           capital=capital, risk_free_rate_pct=kwargs["risk_free_rate_pct"], benchmark=benchmark)


def usable_prices(price_records: dict[str, list[dict]], symbols: list[str],
                  risk_per_symbol: dict[str, dict] | None) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Frames of the stocks that can be optimised + reasons for the ones that cannot."""
    frames, excluded = {}, {}
    for symbol in symbols:
        if symbol not in price_records:
            excluded[symbol] = "no validated price data"
            continue
        risk = (risk_per_symbol or {}).get(symbol)
        if risk is not None and risk.get("status") not in ("completed", "partial"):
            excluded[symbol] = "its risk could not be measured (" + "; ".join(risk.get("errors") or ["no reason"]) + ")"
            continue
        frames[symbol] = frame_from_records(price_records[symbol])
    return frames, excluded


def run_portfolio_optimization(
    price_records: dict[str, list[dict]],
    request: PortfolioOptimizationInput | dict,
    *,
    benchmark_frame: pd.DataFrame | None = None,
    risk_per_symbol: dict[str, dict] | None = None,
    llm: LLMClient | None = None,
    db: Database | None = None,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> PortfolioOutput:
    """`price_records`: {symbol: [{date, ..., close, adjusted_close, ...}]} from the workflow state.
    `risk_per_symbol`: the Risk Assessment output per symbol (stocks it could not measure are
    left out)."""
    started = time.perf_counter()
    settings = settings or get_settings()
    rfr = settings.risk_free_rate
    inp = request if isinstance(request, PortfolioOptimizationInput) else PortfolioOptimizationInput(**request)
    out = PortfolioOutput(status="failed", generated_at=utc_now(), portfolio_id=uuid.uuid4().hex,
                          symbols=list(inp.symbols), investment_amount=inp.investment_amount,
                          risk_preference=inp.risk_preference, method_requested=inp.method,
                          rules=opt.OPTIMISATION_RULES, risk_free_rate=rfr)

    def finish() -> PortfolioOutput:
        out.execution_seconds = time.perf_counter() - started
        if warning := save_agent_result(db, request_id, out, inp.model_dump(mode="json"), scope="request"):
            out.warnings.append(warning)
        return out

    frames, out.excluded_symbols = usable_prices(price_records, list(inp.symbols), risk_per_symbol)
    for symbol, reason in out.excluded_symbols.items():
        out.warnings.append(f"{symbol} was left out: {reason}.")
    out.symbols = list(frames)
    try:
        if len(frames) < 2:
            raise opt.OptimizationError("a portfolio needs at least 2 stocks with enough price history "
                                        f"({len(frames)} available)")
        prices = opt.price_matrix({s: f["adjusted_close"] for s, f in frames.items()})
        c = inp.constraints
        chosen = opt.resolve_settings(inp.risk_preference, len(frames), inp.method, c.min_weight_pct / 100,
                                      None if c.max_weight_pct is None else c.max_weight_pct / 100)
        kwargs = optimisation_kwargs(inp, chosen, rfr)
        result = opt.optimize(prices, chosen["method"], **kwargs)
    except opt.OptimizationError as exc:
        out.errors.append(f"Portfolio could not be optimised: {exc}.")
        return finish()

    out.method, out.method_source = result.method, chosen["method_source"]
    out.method_requested = chosen["method"]
    out.method_label = opt.METHOD_LABELS[result.method]
    out.fallback_reason = result.fallback_reason
    out.constraints = {"min_weight_pct": round(chosen["min_weight"] * 100, 2),
                       "max_weight_pct": round(chosen["max_weight"] * 100, 2), "allow_short": False,
                       "max_weight_source": "requested" if c.max_weight_pct is not None else "risk_preference",
                       "notes": chosen["notes"]}
    out.assumptions = {
        "expected_returns": ("mean of daily returns x 252" if inp.returns_model == "mean"
                             else f"exponentially weighted mean of daily returns (span {opt.EMA_SPAN} days) x 252"),
        "covariance": "Ledoit-Wolf shrinkage x 252" if inp.covariance_model == "ledoit_wolf" else "sample x 252",
        "estimation_window": result.window, "lookback_days": opt.LOOKBACK_DAYS,
        "prices": "adjusted close for estimation; last unadjusted close for buying shares",
        "transaction_cost_bps": inp.transaction_cost_bps, "rebalancing": inp.rebalance,
        "parameters": result.parameters, "risk_free_rate": rfr,
    }

    last_close = pd.Series({s: float(f["close"].iloc[-1]) for s, f in frames.items()})
    last_date = {s: f.index[-1].strftime("%Y-%m-%d") for s, f in frames.items()}
    alloc = opt.discrete_allocation(result.weights, last_close, inp.investment_amount)
    pct = opt.weights_to_percent(result.weights)
    out.allocations = sorted(
        ({"symbol": s, "weight_pct": pct[s], "actual_weight_pct": alloc["actual_weight_pct"][s],
          "amount_inr": alloc["amount_inr"][s], "shares": alloc["shares"][s], "last_price": round(last_close[s], 2),
          "last_price_date": last_date[s], "expected_return_pct": result.expected_returns_pct.get(s),
          "volatility_pct": result.volatility_pct.get(s)} for s in result.weights.index),
        key=lambda a: (-a["weight_pct"], a["symbol"]))
    out.invested_inr, out.leftover_cash_inr = alloc["invested_inr"], alloc["leftover_cash_inr"]
    out.expected_metrics = {**result.expected, "risk_free_rate": rfr,
                            "basis": "historical estimates over the estimation window (in-sample), not forecasts"}
    out.inputs_per_stock = {s: {"expected_return_pct": result.expected_returns_pct.get(s),
                                "volatility_pct": result.volatility_pct.get(s)} for s in result.weights.index}
    out.concentration = rm.concentration({s: w for s, w in result.weights.items() if w > 0})

    if inp.backtest:
        bench = None
        if benchmark_frame is not None and len(benchmark_frame):
            bench = benchmark_frame["adjusted_close"]
        try:
            out.backtest = backtest_rule(prices, chosen["method"], kwargs, rebalance=inp.rebalance,
                                         cost_bps=inp.transaction_cost_bps, capital=inp.investment_amount,
                                         benchmark=bench)
        except (bt.BacktestError, opt.OptimizationError) as exc:
            out.backtest_reason = str(exc)
            out.warnings.append(f"Backtest unavailable: {exc}.")
        if out.backtest and out.backtest["fallbacks_used"]:
            out.warnings.append(f"In the backtest the requested method fell back on {out.backtest['fallbacks_used']} "
                                f"of {len(out.backtest['rebalances'])} rebalance dates.")
    else:
        out.backtest_reason = "not requested"

    out.warnings += _warnings(out, result, alloc, chosen["notes"])
    out.readings = readings(out)
    out.data_sources.append(DataSource(source="workflow state (prices fetched by the Market Research Agent)",
                                       detail=f"daily adjusted close, last {opt.LOOKBACK_DAYS} trading days",
                                       data_as_of=result.window.get("to")))
    if out.backtest and out.backtest["vs_benchmark"]["nifty50"]:
        out.data_sources.append(DataSource(source="yahoo_finance_via_yfinance", detail="NIFTY 50 benchmark"))
    if rfr:
        out.data_sources.append(DataSource(source=rfr["source"], detail=f"risk-free rate {rfr['value_pct']}%",
                                           data_as_of=rfr["as_of_date"]))

    # Each figure appears ONCE, inside the sentence that explains it: in the live check the small
    # model mixed up loose numbers (e.g. called the in-sample return "the backtest").
    facts = {"risk_preference": inp.risk_preference, "method": out.method_label,
             "weights_pct": {a["symbol"]: a["weight_pct"] for a in out.allocations}, **out.readings}
    if llm is not None:
        res = llm.generate_structured(p.portfolio_explanation_prompt(facts), p.PortfolioExplanationOutput,
                                      p.portfolio_explanation_fallback(facts))
        out.explanation, out.llm = res.value.explanation, res.metadata()
    else:
        out.explanation = p.portfolio_explanation_fallback(facts)().explanation
        out.llm = {"source": "template", "model": None, "used_fallback": True}

    complete = not out.fallback_reason and not out.excluded_symbols and (out.backtest or not inp.backtest)
    out.status = "completed" if complete else "partial"
    return finish()


def portfolio_document(out: dict[str, Any], request_id: str, source_ids: list | None = None,
                       user_id: str | None = None) -> PortfolioDocument:
    """Write-once `portfolios` projection (the equity curve stays in agent_results)."""
    bk = out.get("backtest") or {}
    return PortfolioDocument(
        portfolio_id=out["portfolio_id"], request_id=request_id, user_id=user_id,
        stock_allocations=[StockAllocation(symbol=a["symbol"], weight_pct=a["weight_pct"], amount_inr=a["amount_inr"],
                                           shares=a["shares"], last_price=a["last_price"])
                           for a in out["allocations"]],
        investment_amount=out["investment_amount"], optimization_method=out["method"],
        expected_metrics={
            **{k: out["expected_metrics"].get(k) for k in ("annual_return_pct", "annual_volatility_pct",
                                                            "sharpe_ratio", "basis")},
            "risk_free_rate": out.get("risk_free_rate"),
            "risk_preference": out["risk_preference"], "method_requested": out.get("method_requested"),
            "fallback_reason": out.get("fallback_reason"), "constraints": out.get("constraints"),
            "leftover_cash_inr": out.get("leftover_cash_inr"),
            "backtest": {k: bk.get(k) for k in ("period", "cagr_pct", "volatility_pct", "sharpe", "max_drawdown_pct",
                                                "total_costs_inr")} | {
                "equal_weight_cagr_pct": ((bk.get("vs_benchmark") or {}).get("equal_weight") or {}).get("cagr_pct"),
                "nifty50_cagr_pct": ((bk.get("vs_benchmark") or {}).get("nifty50") or {}).get("cagr_pct"),
            } if bk else None,
        },
        source_agent_result_ids=source_ids or [],
    )
