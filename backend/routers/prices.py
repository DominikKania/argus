"""Prices & Watchlist API routes."""

from fastapi import APIRouter
from ..db import get_db

router = APIRouter()


@router.get("/watchlist")
def get_watchlist():
    db = get_db()
    docs = list(db.watchlist.find().sort("ticker", 1))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.get("/{ticker}")
def get_prices(ticker: str, days: int = 30):
    db = get_db()
    cursor = (
        db.prices.find({"ticker": ticker.upper()})
        .sort("date", -1)
        .limit(days)
    )
    docs = list(cursor)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    # Chronologisch zurückgeben (älteste zuerst) für Charts
    docs.reverse()
    return docs
