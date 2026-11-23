"""Phase 6 milestone check: the full RELIANCE.NS flow through the real API, as the dashboard
does it, while sampling system RAM (tasks 6.3.1-6.3.6, 6.3.8).

Starts uvicorn, waits for /api/health, POSTs an analysis, polls its status, reads the
result, indicators and news, stops the server and prints a checklist.

Usage (from backend/, venv active, Ollama running):
    python scripts/milestone_check.py
"""

import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import psutil

# Windows consoles default to cp1252, which cannot print characters such as the rupee sign.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8011/api"


class RamSampler(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak_used_gb, self.min_free_gb, self.peak_runner_mb, self.stop = 0.0, 99.0, 0.0, False

    def run(self) -> None:
        while not self.stop:
            vm = psutil.virtual_memory()
            self.peak_used_gb = max(self.peak_used_gb, (vm.total - vm.available) / 1024**3)
            self.min_free_gb = min(self.min_free_gb, vm.available / 1024**3)
            runner = sum(p.info["memory_info"].rss for p in psutil.process_iter(["name", "memory_info"])
                         if p.info["name"] and "llama-server" in p.info["name"].lower())
            self.peak_runner_mb = max(self.peak_runner_mb, runner / 1024**2)
            time.sleep(0.5)


def process_tree_mb(pid: int) -> float:
    """RSS of a process plus its children (on Windows the venv python.exe is a launcher
    that starts the real interpreter as a child process)."""
    try:
        proc = psutil.Process(pid)
        return sum(p.memory_info().rss for p in [proc, *proc.children(recursive=True)]) / 1024**2
    except psutil.Error:
        return 0.0


def main() -> int:
    include_gdelt = "--gdelt" in sys.argv
    sampler = RamSampler()
    sampler.start()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8011"], cwd=BACKEND,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    checks: list[tuple[str, bool, str]] = []
    try:
        with httpx.Client(timeout=60) as c:
            for _ in range(60):
                try:
                    if c.get(f"{API}/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(1)
            backend_rss = process_tree_mb(server.pid)

            t0 = time.perf_counter()
            job = c.post(f"{API}/analysis/start", json={"symbols": ["RELIANCE"], "include_gdelt": include_gdelt}).json()
            rid = job["request_id"]
            while True:
                status = c.get(f"{API}/analysis/{rid}/status").json()
                backend_rss = max(backend_rss, process_tree_mb(server.pid))
                if status["status"] in ("completed", "partial", "failed", "interrupted"):
                    break
                time.sleep(2)
            elapsed = time.perf_counter() - t0
            result = c.get(f"{API}/analysis/{rid}").json()
            indicators = c.get(f"{API}/stocks/RELIANCE.NS/indicators").json()
            news_api = c.get(f"{API}/news/RELIANCE.NS").json()
            health = c.get(f"{API}/health/db").json()
            backend_rss = max(backend_rss, process_tree_mb(server.pid))
    finally:
        server.terminate()
        server.wait(timeout=30)
        sampler.stop = True
        sampler.join()

    mr = result["market_research"].get("RELIANCE.NS", {})
    news = result["financial_news"].get("RELIANCE.NS", {})
    ind = mr.get("indicators", {})
    latest = indicators["series"][-1]
    checks += [
        ("6.3.1 one year of RELIANCE.NS data", mr.get("validation", {}).get("rows_valid", 0) >= 240,
         f"{mr.get('validation', {}).get('rows_valid')} validated rows (2y lookback; 1y analysis window), as of {mr.get('last_close_date')}"),
        ("6.3.2 SMA20/SMA50/RSI/MACD computed", all(ind.get(k) is not None for k in ("sma_20", "sma_50", "rsi_14")),
         f"SMA20 {ind.get('sma_20')}, SMA50 {ind.get('sma_50')}, RSI {ind.get('rsi_14')}, MACD {ind.get('macd')}"),
        ("    tiles agree with chart series", round(latest["rsi_14"], 2) == ind.get("rsi_14")
         and round(latest["sma_20"], 2) == ind.get("sma_20"), f"chart RSI {latest['rsi_14']:.2f} / SMA20 {latest['sma_20']:.2f}"),
        # Strict: zero articles is NOT a pass (it only means the sources had nothing today).
        ("6.3.3 relevant news collected", news.get("articles_collected", 0) > 0,
         f"{news.get('articles_collected')} collected, {news.get('articles_analyzed')} analysed, overall "
         f"{news.get('overall_sentiment')}, sources {news.get('source_status', {}).get('gdelt', 'gdelt off')}"),
        ("6.3.4 news summarized by local Qwen", news.get("articles_analyzed", 0) > 0
         and bool(news.get("llm", {}).get("models")) and news.get("llm", {}).get("template_results", 1) == 0,
         f"models {news.get('llm', {}).get('models')}, template results {news.get('llm', {}).get('template_results')}"),
        ("6.3.5 market research report generated", bool(result.get("report")) and bool(mr.get("explanation")),
         f"report status {result.get('report', {}).get('status')}; explanation by {mr.get('llm', {}).get('model')}"),
        ("6.3.6 saved in MongoDB Atlas", status["status"] in ("completed", "partial") and news_api["total"] >= news.get("articles_analyzed", 0),
         f"job {rid[:8]}… {status['status']}; financial_news total {news_api['total']}; storage {health['storage']['used_pct']}%"),
    ]
    print(f"\nRELIANCE.NS analysis via API: {status['status']} in {elapsed:.1f} s | agents {status['agents']}\n")
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    print(f"\n  6.3.8 RAM: peak system use {sampler.peak_used_gb:.2f} GB of {psutil.virtual_memory().total / 1024**3:.2f} GB, "
          f"lowest free {sampler.min_free_gb:.2f} GB | backend {backend_rss:.0f} MB | model runner peak {sampler.peak_runner_mb:.0f} MB")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
