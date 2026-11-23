"""Run the full multi-agent workflow from the command line (live checks, Phases 5-10).

Uses real data, the local LLM (adaptive 1.7B/0.6B) and MongoDB. A job record is written to
`analysis_reports` so every saved agent result belongs to a request. The background
runner and API arrive in Phase 6.

Usage (from backend/, venv active, Ollama running):
    python scripts/run_analysis.py RELIANCE
    python scripts/run_analysis.py RELIANCE TCS --no-gdelt --no-store
    python scripts/run_analysis.py RELIANCE TCS INFY --amount 100000 --risk moderate --no-gdelt
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Windows consoles default to cp1252, which cannot print characters such as the rupee sign.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


import psutil  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.data.errors import InvalidSymbolError  # noqa: E402
from app.data.symbols import normalize_symbol  # noqa: E402
from app.database.database import close_client, get_database, initialize_database  # noqa: E402
from app.agents.portfolio_optimizer import portfolio_document  # noqa: E402
from app.database.models import AGENT_RESULTS, ANALYSIS_REPORTS, AnalysisReportDocument, StatusEvent  # noqa: E402
from app.database.repository import insert_document, upsert_document  # noqa: E402
from app.llm.ollama_client import OllamaClient  # noqa: E402
from app.orchestration.graph import build_graph, initial_state  # noqa: E402
from app.utils.timing import utc_now  # noqa: E402


def free_gb() -> float:
    return psutil.virtual_memory().available / 1024**3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--no-gdelt", action="store_true")
    parser.add_argument("--no-store", action="store_true", help="do not write anything to MongoDB")
    parser.add_argument("--amount", type=float, help="investment amount in INR (2+ stocks: adds Portfolio Optimization)")
    parser.add_argument("--risk", choices=["conservative", "moderate", "aggressive"], default="moderate")
    parser.add_argument("--method", help="optimisation method (overrides the risk preference)")
    args = parser.parse_args()

    settings = get_settings()
    valid = []
    for raw in args.symbols:
        try:
            valid.append(normalize_symbol(raw))
        except InvalidSymbolError as exc:
            print(f"Skipping '{raw}': {exc}")
    db = None if args.no_store or not valid else get_database(settings)
    options = {"method": args.method} if args.method else {}
    state = initial_state(args.symbols, request_id=uuid.uuid4().hex, investment_amount=args.amount,
                          risk_preference=args.risk, portfolio_options=options)
    portfolio_request = bool(args.amount) and len(dict.fromkeys(valid)) >= 2
    if db is not None:
        initialize_database(db)
        insert_document(db, AnalysisReportDocument(
            report_id=uuid.uuid4().hex, request_id=state["request_id"], symbols=list(dict.fromkeys(valid)),
            request_params={"raw_symbols": args.symbols, "source": "scripts/run_analysis.py",
                            "request_type": "portfolio" if portfolio_request else "single_stock",
                            "investment_amount": args.amount, "risk_preference": args.risk,
                            "portfolio_options": options},
            status="running", status_history=[StatusEvent(status="queued"), StatusEvent(status="running")]))

    print(f"Request {state['request_id']} | free RAM {free_gb():.2f} GB | LLM {settings.llm_primary_model} "
          f"(fallback {settings.llm_fallback_model}, switch below {settings.llm_min_free_ram_mb} MB free)")
    t0, min_free = time.perf_counter(), free_gb()
    with OllamaClient(settings) as llm:
        if not llm.is_available():
            print("WARNING: Ollama is not running; explanations will use templates.")
        final = build_graph(llm=llm, db=db, settings=settings, include_gdelt=not args.no_gdelt).invoke(state)
        min_free = min(min_free, free_gb())
        llm.unload()
    elapsed = time.perf_counter() - t0
    report = final["final_report"]

    if db is not None:
        status = report["status"]
        db[ANALYSIS_REPORTS].update_one(
            {"request_id": state["request_id"]},
            {"$set": {"status": status, "final_summary": report, "error_summary": final["errors"],
                      "agent_runs": {node: {**t, "status": final["agent_status"].get(node)}
                                for node, t in final["timestamps"].items()},
                      "generated_at": utc_now(), "completed_at": utc_now()},
             "$push": {"status_history": StatusEvent(status=status).model_dump()}})
        pa = final.get("portfolio_analysis") or {}
        if pa.get("status") in ("completed", "partial") and pa.get("allocations"):
            ids = [d["_id"] for d in db[AGENT_RESULTS].find(
                {"request_id": state["request_id"], "agent_name": "portfolio_optimization"}, {"_id": 1})]
            upsert_document(db, portfolio_document(pa, state["request_id"], ids), ["request_id"])
        close_client()

    print(f"\nStatus: {report['status']} | agents {final['agent_status']} | {elapsed:.1f} s total")
    for node, t in final["timestamps"].items():
        print(f"  {node:16} {t['duration_s']:6.1f} s")
    for symbol in final["stock_symbols"]:
        m, n = final["market_analysis"].get(symbol) or {}, final["news_analysis"].get(symbol) or {}
        if m.get("status") not in ("completed", "partial"):
            print(f"\n=== {symbol}: no market data ({'; '.join(m.get('errors') or [])}) ===")
            continue
        ind = m.get("indicators") or {}
        print(f"\n=== {symbol}: {m.get('company_name')} ===")
        print(f"Close {m['last_close']} (as of {m['last_close_date']}) | trend {m['trend']['classification']} | "
              f"SMA20 {ind.get('sma_20')} SMA50 {ind.get('sma_50')} SMA200 {ind.get('sma_200')} | "
              f"RSI {ind.get('rsi_14')} ({m['rsi_zone']}) | MACD hist {(ind.get('macd') or {}).get('histogram')}")
        b = m.get("benchmark_comparison") or {}
        print(f"1y return vs NIFTY 50: {b.get('stock_return_pct')}% vs {b.get('benchmark_return_pct')}% "
              f"(relative {b.get('relative_pct')} pts)")
        print(f"Explanation: {m['explanation']}")
        print(f"News: {n.get('articles_analyzed')} analysed | overall {n.get('overall_sentiment')} "
              f"{json.dumps(n.get('sentiment_breakdown'))}")
        print(f"Digest: {n.get('digest')}")
        sa = final.get("stock_analysis", {}).get(symbol)
        if sa:
            mt = sa.get("metrics", {})
            v = {k: (mt.get(k) or {}).get("value") for k in mt}
            print(f"Fundamentals ({sa['status']}, FY ending {sa['statement_periods'].get('income_statement')}, "
                  f"bank={sa['is_bank']}): overall {sa['overall']} {sa['assessments']}")
            print(f"  revenue YoY {v.get('revenue_growth_yoy_pct')}% (CAGR {v.get('revenue_cagr_pct')}%), "
                  f"net profit YoY {v.get('net_profit_growth_yoy_pct')}% | EPS {v.get('eps')} P/E {v.get('pe')} "
                  f"P/B {v.get('pb')} | ROE {v.get('roe_pct')}% ROA {v.get('roa_pct')}% | D/E {v.get('debt_to_equity')} "
                  f"CR {v.get('current_ratio')} | op margin {v.get('operating_margin_pct')}% net margin {v.get('net_margin_pct')}%")
            print(f"  unavailable: {[(k, mt[k]['reason']) for k in sa.get('unavailable', [])]}")
            print(f"  strengths {sa['strengths']} | weaknesses {sa['weaknesses']}")
            print(f"  explanation: {sa['explanation']}")
        rk = ((final.get("risk_analysis") or {}).get("per_symbol") or {}).get(symbol)
        if rk:
            md = rk.get("max_drawdown") or {}
            print(f"Risk ({rk['status']}, {rk['window'].get('observations')} days): {rk['risk_classification']} | "
                  f"vol {rk['annualized_volatility_pct']}% | beta {rk['beta'].get('value')} ({rk['market_sensitivity']}) | "
                  f"max drawdown {md.get('max_drawdown_pct')}% {md.get('peak_date')}->{md.get('trough_date')} "
                  f"recovered={md.get('recovered')} | Sharpe {rk['sharpe'].get('value')} {rk['sharpe'].get('reason') or ''}")
            print(f"  explanation: {rk.get('explanation')}")
        mr_out = final["market_analysis"][symbol]
        print(f"LLM: market={mr_out.get('llm')}")
        print(f"     news={final['news_analysis'].get(symbol, {}).get('llm')}")
        for w in mr_out.get("warnings", []) + final["news_analysis"].get(symbol, {}).get("warnings", []):
            print(f"  warning: {w}")
    portfolio = (final.get("risk_analysis") or {}).get("portfolio")
    if portfolio:
        print(f"\nPortfolio view: correlation {portfolio['correlation'].get('matrix')} | "
              f"concentration {portfolio['concentration']} | diversification {portfolio['diversification']}")
        for w in portfolio.get("warnings", []):
            print(f"  warning: {w}")
    pa = final.get("portfolio_analysis") or {}
    if pa:
        print(f"\nPORTFOLIO ({pa.get('status')}): {pa.get('method_label')} | requested {pa.get('method_requested')} | "
              f"risk preference {pa.get('risk_preference')} | constraints {pa.get('constraints')}")
        for a in pa.get("allocations", []):
            print(f"  {a['symbol']:13} {a['weight_pct']:6.2f}%  {a['shares']:5d} shares x {a['last_price']:>9} = "
                  f"Rs {a['amount_inr']:>11,.2f}  (exp. return {a['expected_return_pct']}%, vol {a['volatility_pct']}%)")
        print(f"  invested Rs {pa.get('invested_inr')} | leftover cash Rs {pa.get('leftover_cash_inr')}")
        print(f"  expected (in-sample): {pa.get('expected_metrics')}")
        bk = pa.get("backtest")
        if bk:
            vs = bk["vs_benchmark"]
            print(f"  backtest {bk['period']['from']} -> {bk['period']['to']} ({bk['settings']['rebalancing']}, "
                  f"{bk['settings']['transaction_cost_bps']} bps): CAGR {bk['cagr_pct']}% vol {bk['volatility_pct']}% "
                  f"Sharpe {bk['sharpe']} MDD {bk['max_drawdown_pct']}% | equal weight {vs['equal_weight']['cagr_pct']}% "
                  f"| NIFTY 50 {(vs['nifty50'] or {}).get('cagr_pct')}% | rebalances {len(bk['rebalances'])} "
                  f"(fallbacks {bk['fallbacks_used']}) costs Rs {bk['total_costs_inr']}")
        else:
            print(f"  backtest unavailable: {pa.get('backtest_reason')}")
        print(f"  explanation ({(pa.get('llm') or {}).get('source')}): {pa.get('explanation')}")
        for w in pa.get("warnings", []):
            print(f"  warning: {w}")
    print("\nREPORT: key observations "
          f"({report['key_observations']['source']}, {report['key_observations'].get('model') or 'no model'}):")
    for item in report["key_observations"]["items"]:
        print(f"  - {item}")
    tr = report["traceability"]
    print(f"  traceability: {tr['numbers_checked']} numbers checked, ok={tr['ok']} "
          f"{tr['untraced_values'][:3] or ''}{tr['untraced_in_observations'][:3] or ''}")
    v = final.get("validation") or {}
    print(f"  output validation: {v.get('issue_count')} issue(s), {v.get('text_replacements')} AI text(s) replaced")
    for agent, by_symbol in (v.get("agents") or {}).items():
        for sym, res in by_symbol.items():
            for issue in res["issues"]:
                print(f"    {agent} {sym}: {issue}")
    print(f"  retries: {final.get('retries') or 'none'} | unavailable sections: {report['unavailable_sections'] or 'none'}")
    print(f"  data limitations: {len(report['data_limitations'])} | sources: {len(report['source_references'])} | "
          f"glossary terms: {len(report['glossary'])}")
    for e in final["errors"]:
        print(f"ERROR [{e['agent']}] {e['symbol']}: {e['message']}")
    print(f"\nLowest free RAM observed: {min_free:.2f} GB | saved to MongoDB: {db is not None}")
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
