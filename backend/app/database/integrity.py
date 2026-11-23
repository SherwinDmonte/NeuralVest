"""Read-only integrity check (database_design.md §5.3).

Reports problems; never repairs anything. It finds documents that:
  * fail the current `$jsonSchema` validator (e.g. written before a rule was tightened),
  * break cross-field rules that `$jsonSchema` cannot express,
  * are projections whose source agent_results no longer exist,
  * are agent_results whose request has no analysis_reports job record (orphans).
"""

from typing import Any

from pymongo.database import Database

from app.database import models as m
from app.database.schema_validators import VALIDATORS

SAMPLE_SIZE = 5


def _sample(cursor) -> list[str]:
    return [str(d["_id"]) for d in cursor.limit(SAMPLE_SIZE)]


def check_integrity(db: Database) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    existing = set(db.list_collection_names())

    def add(check: str, collection: str, query: dict[str, Any]) -> None:
        count = db[collection].count_documents(query)
        if count:
            issues.append(
                {"check": check, "collection": collection, "count": count,
                 "sample_ids": _sample(db[collection].find(query, {"_id": 1}))}
            )

    # 1. Schema violations (works even if a validator was added after the data).
    for name, validator in VALIDATORS.items():
        if name in existing:
            add("schema_violation", name, {"$nor": [validator]})

    # 2. Cross-field rules.
    if m.MARKET_DATA in existing:
        add("price_order", m.MARKET_DATA, {"$expr": {"$or": [
            {"$gt": ["$low", "$open"]}, {"$gt": ["$low", "$close"]},
            {"$lt": ["$high", "$open"]}, {"$lt": ["$high", "$close"]},
        ]}})
    if m.PORTFOLIOS in existing:
        add("weights_not_100", m.PORTFOLIOS, {"$expr": {"$gt": [
            {"$abs": {"$subtract": [{"$sum": "$stock_allocations.weight_pct"}, 100]}}, 0.01,
        ]}})
    if m.AGENT_RESULTS in existing:
        add("scope_key_mismatch", m.AGENT_RESULTS, {"$or": [
            {"scope": "symbol", "$expr": {"$ne": ["$scope_key", "$symbol"]}},
            {"scope": "request", "scope_key": {"$ne": m.REQUEST_SCOPE_KEY}},
        ]})

    # 3. Projections whose source agent_results are missing.
    for projection in (m.RISK_REPORTS, m.PORTFOLIOS):
        if projection in existing:
            pipeline = [
                {"$match": {"source_agent_result_ids.0": {"$exists": True}}},
                {"$lookup": {"from": m.AGENT_RESULTS, "localField": "source_agent_result_ids",
                             "foreignField": "_id", "as": "src"}},
                {"$match": {"$expr": {"$lt": [{"$size": "$src"}, {"$size": "$source_agent_result_ids"}]}}},
                {"$project": {"_id": 1}},
            ]
            ids = [str(d["_id"]) for d in db[projection].aggregate(pipeline)]
            if ids:
                issues.append({"check": "projection_source_missing", "collection": projection,
                               "count": len(ids), "sample_ids": ids[:SAMPLE_SIZE]})

    # 4. Orphan agent_results (no job record for their request_id).
    if m.AGENT_RESULTS in existing:
        pipeline = [
            {"$group": {"_id": "$request_id"}},
            {"$lookup": {"from": m.ANALYSIS_REPORTS, "localField": "_id", "foreignField": "request_id",
                         "as": "job"}},
            {"$match": {"job": {"$size": 0}}},
        ]
        orphans = [d["_id"] for d in db[m.AGENT_RESULTS].aggregate(pipeline)]
        if orphans:
            issues.append({"check": "orphan_agent_results", "collection": m.AGENT_RESULTS,
                           "count": len(orphans), "sample_request_ids": orphans[:SAMPLE_SIZE]})

    return {"ok": not issues, "issue_count": len(issues), "issues": issues}
