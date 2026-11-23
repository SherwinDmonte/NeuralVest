"""Generic repository helpers: the single write path for application code and scripts.

Every write takes a Pydantic document model, so documents are validated before they
reach MongoDB (the database validators then check them again).
"""

from collections.abc import Iterable, Sequence
from typing import Any

from bson import ObjectId
from pymongo import UpdateOne
from pymongo.database import Database

from app.database.models import MongoDocument
from app.schemas.common import MAX_PAGE_SIZE

BULK_BATCH_SIZE = 500


def _check_model(model: MongoDocument) -> str:
    if not isinstance(model, MongoDocument):
        raise TypeError("expected a MongoDocument model instance")
    return model.collection


def insert_document(db: Database, model: MongoDocument) -> ObjectId:
    """Insert one validated document. Duplicate natural keys raise DuplicateKeyError."""
    collection = _check_model(model)
    return db[collection].insert_one(model.to_document()).inserted_id


def upsert_document(db: Database, model: MongoDocument, key_fields: Sequence[str]) -> dict[str, Any]:
    """Insert or replace the document identified by `key_fields` (its natural key).

    Uses $set so an existing document keeps its _id. Returns {"matched", "upserted_id"}.
    """
    collection = _check_model(model)
    doc = model.to_document()
    key = {f: doc[f] for f in key_fields}
    result = db[collection].update_one(key, {"$set": doc}, upsert=True)
    return {"matched": result.matched_count, "upserted_id": result.upserted_id}


def bulk_upsert(db: Database, models: Iterable[MongoDocument], key_fields: Sequence[str]) -> dict[str, int]:
    """Upsert many documents in batches (e.g. 250 daily prices in one round trip).

    Keeps well under the Atlas free-tier limit of 100 operations per second.
    """
    totals = {"upserted": 0, "modified": 0, "matched": 0}
    batch: list[UpdateOne] = []
    collection: str | None = None

    def flush() -> None:
        if batch and collection:
            res = db[collection].bulk_write(batch, ordered=False)
            totals["upserted"] += res.upserted_count
            totals["modified"] += res.modified_count
            totals["matched"] += res.matched_count
            batch.clear()

    for model in models:
        name = _check_model(model)
        if collection is None:
            collection = name
        elif name != collection:
            raise ValueError("bulk_upsert expects documents of a single collection")
        doc = model.to_document()
        batch.append(UpdateOne({f: doc[f] for f in key_fields}, {"$set": doc}, upsert=True))
        if len(batch) >= BULK_BATCH_SIZE:
            flush()
    flush()
    return totals


def serialize_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Make a raw MongoDB document JSON-friendly (ObjectId -> str, _id -> id)."""
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            out["id"] = str(value)
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, list):
            out[key] = [str(v) if isinstance(v, ObjectId) else serialize_document(v) if isinstance(v, dict) else v for v in value]
        elif isinstance(value, dict):
            out[key] = serialize_document(value)
        else:
            out[key] = value
    return out


def find_page(
    db: Database,
    collection: str,
    query: dict[str, Any] | None = None,
    sort: list[tuple[str, int]] | None = None,
    page: int = 1,
    page_size: int = 20,
    projection: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Paginated find. page_size is capped at MAX_PAGE_SIZE (100)."""
    if page < 1:
        raise ValueError("page must be >= 1")
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    query = query or {}
    coll = db[collection]
    total = coll.count_documents(query)
    cursor = coll.find(query, projection)
    if sort:
        cursor = cursor.sort(sort)
    items = [serialize_document(d) for d in cursor.skip((page - 1) * page_size).limit(page_size)]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": page * page_size < total,
    }


def find_one(db: Database, collection: str, query: dict[str, Any]) -> dict[str, Any] | None:
    doc = db[collection].find_one(query)
    return serialize_document(doc) if doc else None
