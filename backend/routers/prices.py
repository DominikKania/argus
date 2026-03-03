"""Prices & Watchlist API routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from ..db import get_db

log = logging.getLogger("argus")

router = APIRouter()


@router.get("/watchlist")
def get_watchlist():
    db = get_db()
    docs = list(db.watchlist.find().sort("ticker", 1))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/sync")
def sync_prices():
    """Incrementally sync prices: only fetch missing days for all watchlist tickers."""
    import yfinance as yf

    db = get_db()
    watchlist = list(db.watchlist.find().sort("ticker", 1))
    if not watchlist:
        raise HTTPException(status_code=400, detail="Watchlist ist leer.")

    results = []
    today = datetime.now().strftime("%Y-%m-%d")

    for wl_entry in watchlist:
        ticker = wl_entry["ticker"]
        try:
            # Find latest date in DB for this ticker
            latest_doc = db.prices.find_one(
                {"ticker": ticker},
                sort=[("date", -1)],
            )
            latest_date = latest_doc["date"] if latest_doc else None

            # Fetch 2y history for SMA calculation
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            if hist.empty:
                results.append({"ticker": ticker, "new_records": 0, "status": "no_data"})
                continue

            close = hist["Close"]
            sma50_series = close.rolling(50).mean()
            sma200_series = close.rolling(200).mean()

            # Only store days after the latest date in DB
            # Always re-fetch the latest day to get updated close price
            count = 0
            for idx in hist.index:
                date_str = idx.strftime("%Y-%m-%d")
                if latest_date and date_str < latest_date:
                    continue

                row = hist.loc[idx]
                sma50_val = sma50_series.get(idx)
                sma200_val = sma200_series.get(idx)

                doc = {
                    "ticker": ticker,
                    "date": date_str,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
                if sma50_val and not (sma50_val != sma50_val):  # NaN check
                    doc["sma50"] = round(float(sma50_val), 2)
                if sma200_val and not (sma200_val != sma200_val):  # NaN check
                    doc["sma200"] = round(float(sma200_val), 2)

                db.prices.update_one(
                    {"ticker": ticker, "date": date_str},
                    {"$set": doc},
                    upsert=True,
                )
                count += 1

            status = "synced" if count > 0 else "up_to_date"
            results.append({"ticker": ticker, "new_records": count, "status": status})
            log.info("Price sync %s: %d neue Tage", ticker, count)

        except Exception as e:
            log.error("Price sync %s fehlgeschlagen: %s", ticker, e)
            results.append({"ticker": ticker, "new_records": 0, "status": "error", "error": str(e)})

    total = sum(r["new_records"] for r in results)
    return {"total_new_records": total, "results": results}


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
