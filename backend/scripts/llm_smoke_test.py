"""Phase 4 live check (task 4.4.2): analyse real headlines with the local model.

Collects recent headlines from the RSS feeds, runs the news-analysis prompt on up to 3 of
them, and reports latency, tokens/second and RAM before/after, then unloads the model.

Usage (from backend/, venv active, Ollama running):
    python scripts/llm_smoke_test.py
    python scripts/llm_smoke_test.py --model qwen3:1.7b
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.data.news_data import collect_news  # noqa: E402
from app.data.stock_data import get_company_profile  # noqa: E402
from app.llm import prompts as p  # noqa: E402
from app.llm.ollama_client import OllamaClient  # noqa: E402

SYMBOLS = ["HDFCBANK.NS", "TCS.NS", "SBIN.NS", "INFY.NS", "ICICIBANK.NS", "RELIANCE.NS"]


def runner_mb() -> float:
    return sum(proc.info["memory_info"].rss for proc in psutil.process_iter(["name", "memory_info"])
               if proc.info["name"] and "llama-server" in proc.info["name"].lower()) / 1024**2


def free_mb() -> float:
    return psutil.virtual_memory().available / 1024**2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="override LLM_PRIMARY_MODEL for this run")
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    settings = get_settings()
    if args.model:
        settings = settings.model_copy(update={"llm_primary_model": args.model})

    # 1. Real headlines (RSS only: fast and not rate-limited).
    picked = []
    for symbol in SYMBOLS:
        profile = get_company_profile(symbol, settings=settings)
        news = collect_news(symbol, profile["company_name"], include_gdelt=False, settings=settings)
        for article in news.articles[:1]:
            picked.append((symbol, profile["company_name"], article))
        if len(picked) >= args.count:
            break
    if not picked:
        print("No headlines found in the RSS feeds right now; try again later.")
        return 1

    with OllamaClient(settings) as client:
        if not client.is_available():
            print("Ollama is not running. Start it from the Start menu and retry.")
            return 1
        print(f"Model: {settings.llm_primary_model} (fallback: {settings.llm_fallback_model or 'template'})")
        print(f"Free RAM before: {free_mb():.0f} MB\n")
        peak_runner = 0.0
        for symbol, company, art in picked:
            spec = p.news_analysis_prompt(company, symbol, art.headline, art.snippet, art.publisher, art.published_at)
            result = client.generate_structured(spec, p.NewsAnalysisOutput,
                                                p.news_analysis_fallback(art.headline, bool(art.matched_terms)))
            peak_runner = max(peak_runner, runner_mb())
            v = result.value
            print(f"[{symbol}] {art.publisher}: {art.headline[:100]}")
            print(f"   -> {v.sentiment} | {v.category} | relevance {v.relevance} | source={result.source} "
                  f"model={result.model} | {result.duration_seconds:.1f} s | {result.tokens_per_second} tok/s")
            print(f"   summary: {v.summary}")
            if result.used_fallback:
                print(f"   attempts: {result.attempts}")
        print(f"\nModel runner RAM (peak): {peak_runner:.0f} MB | free RAM with model loaded: {free_mb():.0f} MB")
        unloaded = client.unload()
    print(f"Unloaded {unloaded}; free RAM after unload: {free_mb():.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
