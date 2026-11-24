"""Write the landing page snapshot from a real, stored analysis (landing redesign, Phase 12B).

The public landing page shows figures from one real run instead of invented examples. This
script copies the numbers it needs (with their dates, periods, formulas and the agent that
computed them) from MongoDB into frontend/src/landing/snapshot.json. It only reads.

Usage (from the backend/ folder, venv active):
    python scripts/make_landing_snapshot.py                    # latest finished run with 2+ stocks
    python scripts/make_landing_snapshot.py --request-id ID    # a specific run
    python scripts/make_landing_snapshot.py --test-db          # read the test database
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.api.routes.analysis import assemble_result  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database.database import close_client, get_client  # noqa: E402
from app.database.models import ANALYSIS_REPORTS  # noqa: E402

OUT = ROOT.parent / "frontend" / "src" / "landing" / "snapshot.json"
CURVE_POINTS = 60
AGENT_ORDER = ["market_research", "financial_news", "stock_analysis", "risk_assessment",
               "portfolio_optimization", "report"]


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _downsample(rows: list[dict], n: int) -> list[dict]:
    if len(rows) <= n:
        return rows
    step = (len(rows) - 1) / (n - 1)
    return [rows[round(i * step)] for i in range(n)]


def _metric(m: dict, key: str) -> dict | None:
    v = m.get(key) or {}
    if v.get("value") is None:
        return None
    return {"value": v["value"], "period": v.get("period"), "formula": v.get("formula")}


def build(result: dict) -> dict:
    symbols = result["symbols"]
    mr, sa, ra = result["market_research"], result["stock_analysis"], result["risk_assessment"]
    po = result.get("portfolio_optimization") or {}
    po = po.get("__request__", po) if isinstance(po, dict) else {}
    request_risk = ra.get("__request__", {})

    stocks = {}
    for s in symbols:
        m, r = mr.get(s, {}), ra.get(s, {})
        bench = m.get("benchmark_comparison") or {}
        metrics = (sa.get(s) or {}).get("metrics") or {}
        dd = r.get("max_drawdown") or {}
        stocks[s] = {
            "name": m.get("company_name"),
            "last_close": m.get("last_close"),
            "last_close_date": m.get("last_close_date"),
            "return_1y_pct": bench.get("stock_return_pct"),
            "nifty_return_pct": bench.get("benchmark_return_pct"),
            "window": {"from": bench.get("from"), "to": bench.get("to"), "trading_days": bench.get("trading_days")},
            "trend": (m.get("trend") or {}).get("classification"),
            "rsi_14": (m.get("indicators") or {}).get("rsi_14"),
            "volatility_pct": r.get("annualized_volatility_pct"),
            "beta": (r.get("beta") or {}).get("value"),
            "beta_observations": (r.get("beta") or {}).get("observations"),
            "sharpe": (r.get("sharpe") or {}).get("value"),
            "max_drawdown": {"pct": dd.get("max_drawdown_pct"), "peak": dd.get("peak_date"),
                             "trough": dd.get("trough_date"), "recovered": dd.get("recovered")},
            "risk_class": r.get("risk_classification"),
            "risk_window": r.get("window"),
            "fundamentals": {k: _metric(metrics, k) for k in
                             ("pe", "roe_pct", "debt_to_equity", "net_margin_pct", "revenue_growth_yoy_pct")},
        }

    backtest = po.get("backtest") or {}
    vs = backtest.get("vs_benchmark") or {}
    portfolio = None
    if po.get("allocations"):
        portfolio = {
            "amount_inr": po.get("investment_amount"),
            "method_label": po.get("method_label"),
            "allocations": [{k: a.get(k) for k in ("symbol", "weight_pct", "shares", "amount_inr")}
                            for a in po["allocations"]],
            "expected": {k: (po.get("expected_metrics") or {}).get(k) for k in ("annual_return_pct", "annual_volatility_pct")},
            "backtest": {
                "from": (backtest.get("period") or {}).get("from"),
                "to": (backtest.get("period") or {}).get("to"),
                "cagr_pct": backtest.get("cagr_pct"),
                "equal_weight_cagr_pct": (vs.get("equal_weight") or {}).get("cagr_pct"),
                "nifty50_cagr_pct": (vs.get("nifty50") or {}).get("cagr_pct"),
                "curve": [{k: p.get(k) for k in ("date", "strategy", "nifty50")}
                          for p in _downsample(backtest.get("equity_curve") or [], CURVE_POINTS)],
            } if backtest else None,
        }

    report = result.get("report") or {}
    runs = result.get("agent_runs") or {}
    rf = request_risk.get("risk_free_rate") or {}
    return {
        "note": "Copied from a real stored analysis by backend/scripts/make_landing_snapshot.py. Do not edit by hand.",
        "run": {
            "symbols": symbols,
            "requested_at": _iso(result.get("requested_at")),
            "completed_at": _iso(result.get("completed_at")),
            "status": result.get("status"),
            "numbers_traced": (report.get("traceability") or {}).get("numbers_checked"),
            "traced_ok": (report.get("traceability") or {}).get("ok"),
            "agent_seconds": {k: (runs.get(k) or {}).get("duration_s") for k in AGENT_ORDER},
        },
        "risk_free_rate": {"value_pct": rf.get("value_pct"), "as_of": rf.get("as_of_date"), "source": rf.get("source")},
        "correlation": ((request_risk.get("correlation") or {}).get("matrix") or {}),
        "diversification": (request_risk.get("diversification") or {}).get("assessment"),
        "stocks": stocks,
        "portfolio": portfolio,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--request-id", help="analysis to copy (default: the latest finished run with 2+ stocks)")
    parser.add_argument("--test-db", action="store_true", help="use the test database")
    args = parser.parse_args()

    settings = get_settings()
    db = get_client(settings)[settings.mongodb_test_db_name if args.test_db else settings.mongodb_db_name]
    query = {"request_id": args.request_id} if args.request_id else {
        "status": {"$in": ["completed", "partial"]}, "symbols.1": {"$exists": True}}
    job = db[ANALYSIS_REPORTS].find_one(query, sort=[("completed_at", -1)])
    if not job:
        print("No matching analysis found.")
        close_client()
        return 1
    snapshot = build(assemble_result(db, job))
    close_client()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} from {job['request_id']} ({', '.join(job['symbols'])}, {snapshot['run']['completed_at']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
