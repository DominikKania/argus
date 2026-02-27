"""Ampel API routes."""

from fastapi import APIRouter
from ..db import get_db

router = APIRouter()


def _serialize_doc(doc):
    """Convert MongoDB ObjectId fields to strings for JSON serialization."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    if "analysis_id" in doc:
        doc["analysis_id"] = str(doc["analysis_id"])
    return doc


@router.get("/latest")
def get_latest():
    db = get_db()
    doc = db.analyses.find_one(sort=[("date", -1)])
    return _serialize_doc(doc)


@router.get("/history")
def get_history(limit: int = 10):
    db = get_db()
    cursor = db.analyses.find(sort=[("date", -1)]).limit(limit)
    return [_serialize_doc(doc) for doc in cursor]


@router.get("/theses")
def get_theses():
    db = get_db()
    cursor = db.theses.find({"status": "open"}).sort("created_date", -1)
    return [_serialize_doc(doc) for doc in cursor]
