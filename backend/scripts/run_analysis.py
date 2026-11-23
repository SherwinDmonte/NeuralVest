"""Run the multi-agent workflow from the command line (Phase 5 live check, task 5.4.4).

Uses real data, the local LLM (adaptive 1.7B/0.6B) and MongoDB. A job record is written to
`analysis_reports` so every saved agent result belongs to a request. The background
runner and API arrive in Phase 6.

Usage (from backend/, venv active, Ollama running):
    python scripts/run_analysis.py RELIANCE
    python scripts/run_analysis.py RELIANCE TCS --no-gdelt --no-store
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.data.errors import InvalidSymbolError  # noqa: E402
from app.data.symbols import normalize_symbol  # noqa: E402
from app.database.database import close_client, get_database, initialize_database  # noqa: E402
from app.database.models import ANALYSIS_REPORTS, AnalysisReportDocument, StatusEvent  # noqa: E402
from app.database.repository import insert_document  # noqa: E402
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
    args = parser.parse_args()

    settings = get_settings()
    valid = []
    for raw in args.symbols:
        try:
            valid.append(normalize_symbol(raw))
        except InvalidSymbolError as exc:
            print(f"Skipping '{raw}': {exc}")
    db = None if args.no_store or not valid else get_database(settings)
    state = initial_state(args.symbols, request_id=uuid.uuid4().hex)
    if db is not None:
        initialize_database(db)
        insert_document(db, AnalysisReportDocument(
            report_id=uuid.uuid4().hex, request_id=state["request_id"], symbols=list(dict.fromkeys(valid)),
            request_params={"raw_symbols": args.symbols, "source": "scripts/run_analysis.py"},
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
                      "generated_at": utc_now(), "completed_at": utc_now()},
             "$push": {"status_history": StatusEvent(status=status).model_dump()}})
        close_client()

    print(f"\nStatus: {report['status']} | agents {final['agent_status']} | {elapsed:.1f} s total")
    for node, t in final["timestamps"].items():
        print(f"  {node:16} {t['duration_s']:6.1f} s")
    for symbol, sec in report["sections"].items():
        m, n = sec["market_research"], sec["financial_news"]
        ind = m.get("indicators") or {}
        print(f"\n=== {symbol}: {sec['company_name']} ===")
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
        mr_out = final["market_analysis"][symbol]
        print(f"LLM: market={mr_out.get('llm')}")
        print(f"     news={final['news_analysis'].get(symbol, {}).get('llm')}")
        for w in mr_out.get("warnings", []) + final["news_analysis"].get(symbol, {}).get("warnings", []):
            print(f"  warning: {w}")
    for e in final["errors"]:
        print(f"ERROR [{e['agent']}] {e['symbol']}: {e['message']}")
    print(f"\nLowest free RAM observed: {min_free:.2f} GB | saved to MongoDB: {db is not None}")
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
