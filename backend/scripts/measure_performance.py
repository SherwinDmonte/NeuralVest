"""Performance measurements for Phase 13 (tasks 13.2.1-13.2.5).

  llm        LLM inference time of qwen3:1.7b and qwen3:0.6b on the same three prompts (13.2.2)
  single     one stock, full workflow: total time, per-agent time, peak memory (13.2.1, 13.2.3, 13.2.5)
  portfolio  five stocks with Portfolio Optimization (Rs 1,00,000, moderate) (same)
  db         MongoDB response times for the queries the API makes (13.2.4)

It uses the TEST database only (APP_ENV=test, MONGODB_TEST_DB_NAME), never your main data, and
writes the results to data/exports/performance_<time>.json (not committed). Prices come from the
local cache when it is fresh, as in the app. Run from backend/ with Ollama running:
    python scripts/measure_performance.py                 (everything, about 10-15 minutes)
    python scripts/measure_performance.py llm db
"""

import argparse
import json
import os
import platform
import statistics
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

os.environ["APP_ENV"] = "test"  # before the app is imported: the test database everywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import psutil  # noqa: E402

from app.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.database.database import get_database, initialize_database, ping  # noqa: E402
from app.database.models import (  # noqa: E402
    AGENT_RESULTS, ANALYSIS_REPORTS, MARKET_DATA, AnalysisReportDocument, StatusEvent,
)
from app.database.repository import insert_document  # noqa: E402
from app.llm import prompts as p  # noqa: E402
from app.llm.guards import StockFacts  # noqa: E402
from app.llm.ollama_client import OllamaClient  # noqa: E402
from app.orchestration.graph import build_graph, initial_state  # noqa: E402
from app.services.report_generator import ReportSummaryOutput  # noqa: E402
from app.utils.timing import utc_now  # noqa: E402

MB = 1024 ** 2
MODELS = ("qwen3:1.7b", "qwen3:0.6b")
SINGLE = ["RELIANCE.NS"]
PORTFOLIO = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]


# ---------------------------------------------------------------- memory sampling (13.2.3)
def ollama_rss_mb() -> float:
    total = 0
    for proc in psutil.process_iter(["name", "memory_info"]):
        name = (proc.info["name"] or "").lower()
        if name.startswith(("ollama", "llama")) and proc.info["memory_info"]:
            total += proc.info["memory_info"].rss
    return total / MB


class MemorySampler:
    """Samples every 0.5 s: this process (the backend code), Ollama (server + model runner) and
    the whole system. Keeps the peaks."""

    def __init__(self):
        self.me = psutil.Process()
        self.peak = {"backend_mb": 0.0, "ollama_mb": 0.0, "system_used_mb": 0.0}
        self.min_available_mb = float("inf")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        vm = psutil.virtual_memory()
        values = {"backend_mb": self.me.memory_info().rss / MB, "ollama_mb": ollama_rss_mb(),
                  "system_used_mb": (vm.total - vm.available) / MB}
        for k, v in values.items():
            self.peak[k] = max(self.peak[k], v)
        self.min_available_mb = min(self.min_available_mb, vm.available / MB)

    def _run(self):
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(0.5)

    def __enter__(self):
        self._sample()
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self._sample()

    def result(self):
        return {**{k: round(v) for k, v in self.peak.items()}, "min_available_mb": round(self.min_available_mb)}


# ---------------------------------------------------------------- 13.2.2 LLM benchmark
FACTS_MARKET = {
    "symbol": "RELIANCE.NS", "company": "Reliance Industries Limited", "as_of": "2026-11-20", "last_close": 1402.5,
    "period_return_pct": 4.12, "gap_vs_nifty_pct_points": 6.1, "trend": "sideways", "rsi_14": 48.3,
    "rsi_zone": "neutral", "macd": -3.1, "macd_signal": -1.4, "macd_histogram": -1.7, "sma_20": 1398.2,
    "sma_50": 1410.7, "sma_200": 1361.9, "volume_vs_20d_avg": 0.92,
    "macd_reading": "MACD is below its signal line (momentum weakening)",
    "long_term_reading": "the price is above its 200-day average",
    "benchmark_reading": "the stock outperformed the NIFTY 50 by 6.1 percentage points over the period (4.12% for "
                         "the stock vs -1.98% for the NIFTY 50)",
    "rsi_reading": "RSI is in the neutral zone (between 30 and 70)",
}
OBS_STOCKS = [
    StockFacts("RELIANCE.NS", ("RELIANCE.NS", "RELIANCE", "Reliance Industries"),
               ("RELIANCE.NS: the stock outperformed the NIFTY 50 by 6.1 percentage points over the period "
                "(4.12% for the stock vs -1.98% for the NIFTY 50)", "RELIANCE.NS: historical risk is moderate (annualised volatility 22.4%)",
                "RELIANCE.NS: the financial statements look mixed overall"), 6.1),
    StockFacts("TCS.NS", ("TCS.NS", "TCS", "Tata Consultancy Services"),
               ("TCS.NS: the stock underperformed the NIFTY 50 by 16.33 percentage points over the period "
                "(-18.31% for the stock vs -1.98% for the NIFTY 50)", "TCS.NS: historical risk is low (annualised volatility 18.9%)",
                "TCS.NS: the financial statements look solid overall"), -16.33),
]
# keys as report_generator.observation_facts names them
FACTS_OBS = {f"{s.symbol.split('.')[0].lower()}_{k}": f for s in OBS_STOCKS
             for k, f in zip(("benchmark_reading", "risk_reading", "fundamentals_reading"), s.facts)}


def benchmark_specs():
    return [
        ("market_explanation", p.market_explanation_prompt(FACTS_MARKET), p.MarketExplanationOutput,
         p.market_explanation_fallback(FACTS_MARKET)),
        ("news_analysis", p.news_analysis_prompt("Reliance Industries Limited", "RELIANCE.NS",
                                                 "Reliance Industries reports higher quarterly revenue as retail grows",
                                                 "Revenue rose while refining margins were lower.", "Business Standard",
                                                 datetime(2026, 11, 19, tzinfo=UTC)),
         p.NewsAnalysisOutput, p.news_analysis_fallback("Reliance Industries reports higher revenue", True)),
        ("report_summary", p.report_summary_prompt(FACTS_OBS, OBS_STOCKS), ReportSummaryOutput,
         lambda: ReportSummaryOutput(observations=list(FACTS_OBS.values())[:5])),
    ]


def run_llm(repeats: int) -> dict:
    base = get_settings()
    out = {}
    with OllamaClient(base) as probe:
        if not probe.is_available():
            return {"error": "Ollama is not running"}
        installed = probe.installed_models()
        probe.unload()
    for model in MODELS:
        if model not in installed:
            out[model] = {"error": "not installed"}
            continue
        settings = base.model_copy(update={"llm_primary_model": model, "llm_fallback_model": None,
                                           "llm_min_free_ram_mb": 0})
        rows = {}
        with OllamaClient(settings) as llm, MemorySampler() as mem:
            t0 = time.perf_counter()
            llm.generate_structured(p.PromptSpec(name="warmup", system="Return JSON with one field, explanation.",
                                                 user="Say that the model is ready.", max_tokens=60),
                                    p.MarketExplanationOutput,
                                    lambda: p.MarketExplanationOutput(explanation="warm-up"))
            load_s = time.perf_counter() - t0
            for name, spec, schema, fallback in benchmark_specs():
                runs = []
                for _ in range(repeats):
                    res = llm.generate_structured(spec, schema, fallback)
                    runs.append({"seconds": round(res.duration_seconds, 2), "source": res.source,
                                 "tokens": res.eval_tokens, "tokens_per_second": res.tokens_per_second,
                                 "attempts": len(res.attempts),
                                 "rejected": [a["reason"] for a in res.attempts if not a["ok"]]})
                secs = [r["seconds"] for r in runs]
                tps = [r["tokens_per_second"] for r in runs if r["tokens_per_second"]]
                rows[name] = {"median_seconds": round(statistics.median(secs), 2), "max_seconds": max(secs),
                              "median_tokens_per_second": round(statistics.median(tps), 1) if tps else None,
                              "accepted": sum(r["source"] == "llm" for r in runs), "runs": runs}
                print(f"  {model} {name:20} median {rows[name]['median_seconds']:5.1f} s | "
                      f"{rows[name]['median_tokens_per_second']} tok/s | accepted {rows[name]['accepted']}/{repeats}")
            llm.unload()
        out[model] = {"first_call_with_load_seconds": round(load_s, 2), "prompts": rows, "memory": mem.result()}
        print(f"  {model}: load + first call {load_s:.1f} s | peak Ollama RAM {out[model]['memory']['ollama_mb']} MB")
    return out


# ---------------------------------------------------------------- 13.2.1 / 13.2.5 workflow runs
def run_workflow(symbols: list[str], amount: float | None) -> dict:
    settings = get_settings()
    db = get_database(settings)
    initialize_database(db)
    state = initial_state(symbols, request_id=uuid.uuid4().hex, investment_amount=amount, risk_preference="moderate")
    insert_document(db, AnalysisReportDocument(
        report_id=uuid.uuid4().hex, request_id=state["request_id"], symbols=symbols,
        request_params={"raw_symbols": symbols, "source": "scripts/measure_performance.py",
                        "request_type": "portfolio" if amount else "single_stock", "investment_amount": amount,
                        "risk_preference": "moderate"},
        status="running", status_history=[StatusEvent(status="queued"), StatusEvent(status="running")]))
    free_before = psutil.virtual_memory().available / MB
    with OllamaClient(settings) as llm, MemorySampler() as mem:
        llm.unload()
        t0 = time.perf_counter()
        final = build_graph(llm=llm, db=db, settings=settings).invoke(state)
        total = time.perf_counter() - t0
        llm.unload()
    report = final["final_report"]
    db[ANALYSIS_REPORTS].update_one({"request_id": state["request_id"]},
                                    {"$set": {"status": report["status"], "final_summary": report,
                                              "completed_at": utc_now()}})

    def agent_seconds(key):
        section = final.get(key) or {}
        return {s: round(v.get("execution_seconds") or 0, 2) for s, v in section.items() if isinstance(v, dict)}

    llm_calls = []
    for key in ("market_analysis", "stock_analysis", "news_analysis"):
        for sym, v in (final.get(key) or {}).items():
            if isinstance(v, dict) and v.get("llm"):
                llm_calls.append({"agent": key, "symbol": sym, **{k: v["llm"].get(k) for k in (
                    "source", "model", "duration_seconds", "calls", "models", "template_results") if k in v["llm"]}})
    risk = final.get("risk_analysis") or {}
    result = {
        "symbols": symbols, "investment_amount": amount, "request_id": state["request_id"],
        "status": report["status"], "total_seconds": round(total, 1),
        "nodes": {n: round(t["duration_s"], 2) for n, t in final["timestamps"].items()},
        "agent_seconds": {"market_research": agent_seconds("market_analysis"),
                          "financial_news": agent_seconds("news_analysis"),
                          "stock_analysis": agent_seconds("stock_analysis"),
                          "risk_assessment": {s: round(v.get("execution_seconds") or 0, 2)
                                              for s, v in (risk.get("per_symbol") or {}).items()}},
        "llm_calls": llm_calls,
        "key_observations": {"source": report["key_observations"]["source"],
                             "model": report["key_observations"].get("model"),
                             "rejected": report["key_observations"].get("rejected_attempts")},
        "traceability_ok": report["traceability"]["ok"],
        "free_ram_before_mb": round(free_before), "memory": mem.result(),
    }
    print(f"  {len(symbols)} stock(s): {result['status']} in {result['total_seconds']} s | nodes {result['nodes']}")
    print(f"  peak: backend {result['memory']['backend_mb']} MB, Ollama {result['memory']['ollama_mb']} MB, "
          f"system {result['memory']['system_used_mb']} MB used (lowest free {result['memory']['min_available_mb']} MB)")
    return result


# ---------------------------------------------------------------- 13.2.4 database
def run_db(repeats: int) -> dict:
    settings = get_settings()
    db = get_database(settings)
    some = db[ANALYSIS_REPORTS].find_one({}, {"request_id": 1}) or {}
    rid = some.get("request_id", "none")
    since = utc_now().replace(year=utc_now().year - 1)
    queries = {
        "ping": lambda: ping(settings),
        "report_by_request_id": lambda: db[ANALYSIS_REPORTS].find_one({"request_id": rid}),
        "reports_list_20": lambda: list(db[ANALYSIS_REPORTS].find({}, {"final_summary": 0}).sort("created_at", -1)
                                        .limit(20)),
        "agent_results_of_request": lambda: list(db[AGENT_RESULTS].find({"request_id": rid}, {"output": 0})),
        "market_data_1y_one_symbol": lambda: list(db[MARKET_DATA].find({"symbol": "RELIANCE.NS",
                                                                         "date": {"$gte": since}}).sort("date", 1)),
        "status_update": lambda: db[ANALYSIS_REPORTS].update_one({"request_id": rid},
                                                                 {"$set": {"updated_at": utc_now()}}),
    }
    out = {}
    for name, fn in queries.items():
        fn()  # warm the connection pool
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        out[name] = {"median_ms": round(statistics.median(times), 1), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1),
                     "max_ms": round(times[-1], 1), "runs": repeats}
        print(f"  {name:28} median {out[name]['median_ms']:7.1f} ms | p95 {out[name]['p95_ms']:7.1f} ms")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parts", nargs="*", default=["llm", "single", "portfolio", "db"],
                        choices=["llm", "single", "portfolio", "db"])
    parser.add_argument("--repeats", type=int, default=3, help="LLM calls per prompt and model")
    args = parser.parse_args()
    settings = get_settings()
    vm = psutil.virtual_memory()
    env = {"measured_at": datetime.now(UTC).isoformat(timespec="seconds"), "os": platform.platform(),
           "cpu": platform.processor(), "logical_cpus": psutil.cpu_count(), "total_ram_mb": round(vm.total / MB),
           "free_ram_at_start_mb": round(vm.available / MB), "python": platform.python_version(),
           "database": settings.active_db_name, "llm_primary": settings.llm_primary_model,
           "llm_fallback": settings.llm_fallback_model, "llm_min_free_ram_mb": settings.llm_min_free_ram_mb,
           "llm_num_ctx": settings.llm_num_ctx}
    assert settings.active_db_name.endswith("_test"), "refusing to measure against a non-test database"
    print(f"{env['total_ram_mb']} MB RAM, {env['free_ram_at_start_mb']} MB free, {env['logical_cpus']} CPUs, "
          f"database {env['database']}")
    results: dict = {"environment": env}
    if "llm" in args.parts:
        print("LLM inference (13.2.2)")
        results["llm"] = run_llm(args.repeats)
    if "single" in args.parts:
        print("Single stock (13.2.1, 13.2.3, 13.2.5)")
        results["single"] = run_workflow(SINGLE, None)
    if "portfolio" in args.parts:
        print("Five-stock portfolio (13.2.1, 13.2.3, 13.2.5)")
        results["portfolio"] = run_workflow(PORTFOLIO, 100_000)
    if "db" in args.parts:
        print("Database (13.2.4)")
        results["db"] = run_db(20)
    out_dir = PROJECT_ROOT / "data" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
