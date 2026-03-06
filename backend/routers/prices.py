"""Prices & Watchlist API routes."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_db

log = logging.getLogger("argus")

router = APIRouter()


class AddWatchlistRequest(BaseModel):
    ticker: str
    name: Optional[str] = None
    category: str = "stock"  # stock | etf


@router.get("/watchlist")
def get_watchlist():
    db = get_db()
    docs = list(db.watchlist.find().sort("ticker", 1))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/watchlist")
def add_to_watchlist(req: AddWatchlistRequest):
    """Manuell ein Asset zur Watchlist hinzufügen."""
    db = get_db()
    ticker = req.ticker.strip().upper()

    if db.watchlist.find_one({"ticker": ticker}):
        raise HTTPException(status_code=409, detail=f"'{ticker}' ist bereits in der Watchlist.")

    # Validate ticker and resolve name via yfinance
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        yf_name = info.get("shortName") or info.get("longName")
        if not yf_name:
            raise HTTPException(status_code=400, detail=f"Ticker '{ticker}' bei yfinance nicht gefunden. Bitte den korrekten Börsenkürzel verwenden (z.B. 'APP' statt 'APPLOVIN').")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"Ticker '{ticker}' konnte nicht validiert werden.")
    name = req.name or yf_name

    doc = {
        "ticker": ticker,
        "name": name,
        "category": req.category,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
    }
    result = db.watchlist.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str):
    """Asset aus der Watchlist entfernen."""
    db = get_db()
    result = db.watchlist.delete_one({"ticker": ticker.upper()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"'{ticker}' nicht in Watchlist gefunden.")
    return {"deleted": True, "ticker": ticker.upper()}


# ── Analyst News ─────────────────────────────────────────────────────────

ANALYST_NEWS_FEEDS = [
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml"},
    {"name": "Benzinga Analyst", "url": "https://www.benzinga.com/analyst-ratings/feed"},
    {"name": "MarketBeat", "url": "https://www.marketbeat.com/feed/"},
    {"name": "TipRanks", "url": "https://blog.tipranks.com/feed/"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/marketpulse"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
]

ANALYST_NEWS_SYSTEM = """\
Du bist ein Analyst-News-Filter im Argus Investment-System.

Du erhältst RSS-Headlines und filterst NUR Headlines die sich auf Analystenmeinungen, \
Kurszieländerungen, Upgrades, Downgrades, Ratings und Price Targets für ein bestimmtes \
Asset beziehen.

## ASSET
{asset_name} (Ticker: {ticker})

## BISHERIGE ANALYSEN
{previous_context}

## REGELN
- Filtere NUR Headlines die DIREKT Analysten-Bewertungen, Kursziele oder Ratings \
für dieses spezifische Asset betreffen
- Ignoriere allgemeine Marktnachrichten, Earnings, Produktnews etc.
- Bewerte den Gesamttrend der Analystenstimmung
- development: Was ist NEU seit der letzten Analyse?
- recurring: Was bestätigt sich?
- Alle Texte auf Deutsch

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON:
{{
  "summary": "2-3 Sätze: Wie steht die Analystenstimmung aktuell?",
  "development": "Neue Entwicklungen bei Analystenbewertungen",
  "recurring": "Wiederkehrende Muster/Trends bei den Analysten",
  "relevant_headlines": [
    {{"title": "Headline auf Deutsch", "source": "Quelle", "link": "url", "sentiment": "positive|negative|neutral"}}
  ],
  "sentiment_count": {{"positive": 0, "negative": 0, "neutral": 0}},
  "trend": "improving|stable|deteriorating",
  "trend_reasoning": "Begründung",
  "consensus_direction": "bullish|neutral|bearish",
  "ampel_relevance": "Ein Satz zur Relevanz für die Gesamtbewertung"
}}\
"""


def _fetch_analyst_headlines(ticker: str):
    """Fetch RSS headlines for analyst news about a ticker.

    Uses general finance feeds + ticker-specific Google News RSS.
    Returns (all_headlines, ticker_specific_count).
    """
    import feedparser
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from urllib.parse import quote

    db = get_db()
    wl = db.watchlist.find_one({"ticker": ticker.upper()})
    asset_name = wl["name"].split()[0] if wl and wl.get("name") else ticker.upper()

    # Ticker-specific feeds via Google News RSS
    search_queries = [
        f"{ticker}+analyst+rating",
        f"{ticker}+price+target",
        f"{asset_name}+analyst+upgrade+downgrade",
    ]
    ticker_feeds = [
        {"name": f"Google News ({ticker})", "url": f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en"}
        for q in search_queries
    ]

    all_feeds = ANALYST_NEWS_FEEDS + ticker_feeds
    all_headlines = []

    def fetch_feed(feed):
        try:
            parsed = feedparser.parse(feed["url"])
            results = []
            for entry in parsed.entries[:20]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                results.append({
                    "title": title,
                    "source": feed["name"],
                    "link": entry.get("link", ""),
                    "date": entry.get("published", ""),
                })
            return results
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=min(len(all_feeds), 12)) as executor:
        futures = {executor.submit(fetch_feed, f): f["name"] for f in all_feeds}
        for future in as_completed(futures):
            try:
                all_headlines.extend(future.result())
            except Exception:
                pass

    # Deduplicate, prioritize ticker-specific (Google News) headlines first
    ticker_lower = ticker.lower()
    name_variants = [ticker_lower]
    if wl and wl.get("name"):
        name_variants.append(wl["name"].split()[0].lower())

    seen = set()
    specific = []
    general = []
    for h in all_headlines:
        key = h["title"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        title_lower = h["title"].lower()
        if any(v in title_lower for v in name_variants):
            specific.append(h)
        else:
            general.append(h)

    # Ticker-specific first, then general
    result = specific + general
    log.info("Analyst-News %s: %d spezifisch + %d allgemein = %d unique",
             ticker, len(specific), len(general), len(result))
    return result


def sync_analyst_news_for_ticker(db, ticker: str, all_headlines=None):
    """Fetch and analyze analyst news for a single ticker."""
    from ..llm import call_llm
    from ampel_auto import extract_json

    ticker_upper = ticker.upper()
    wl = db.watchlist.find_one({"ticker": ticker_upper})
    if not wl:
        return None

    asset_name = wl.get("name", ticker_upper)
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Fetch headlines
    headlines = _fetch_analyst_headlines(ticker_upper)

    # Previous results for context
    previous = list(
        db.analyst_news.find(
            {"ticker": ticker_upper},
            {"raw_headlines": 0},
        ).sort("date", -1).limit(5)
    )
    prev_context = "Keine bisherigen Analysen."
    if previous:
        parts = []
        for p in previous:
            parts.append(f"- {p['date']}: {p.get('trend', '?')} — {p.get('summary', '')}")
        prev_context = "\n".join(parts)

    headlines_to_analyze = headlines[:50]

    if not headlines_to_analyze:
        doc = {
            "ticker": ticker_upper,
            "date": date_str,
            "name": asset_name,
            "summary": "Keine relevanten Analysten-News heute.",
            "development": "",
            "recurring": "",
            "relevant_headlines": [],
            "sentiment_count": {"positive": 0, "negative": 0, "neutral": 0},
            "trend": "stable",
            "trend_reasoning": "Keine Headlines verfügbar.",
            "consensus_direction": "neutral",
            "ampel_relevance": "Keine neuen Analysten-Impulse.",
            "headlines_fetched": 0,
            "updated_at": datetime.now().isoformat(),
        }
        db.analyst_news.update_one(
            {"ticker": ticker_upper, "date": date_str},
            {"$set": doc},
            upsert=True,
        )
        return doc

    headlines_text = "\n".join(
        f"- [{h['source']}] {h['title']} | link: {h.get('link', '')}"
        for h in headlines_to_analyze
    )

    system = ANALYST_NEWS_SYSTEM.format(
        asset_name=asset_name,
        ticker=ticker_upper,
        previous_context=prev_context,
    )
    user_prompt = (
        f"## HEADLINES ({len(headlines_to_analyze)} Stück)\n{headlines_text}"
    )

    try:
        llm_text = call_llm(system, [{"role": "user", "content": user_prompt}], max_tokens=4096)
        result = extract_json(llm_text)
    except Exception as e:
        log.error("Analyst-News LLM-Analyse für %s fehlgeschlagen: %s", ticker_upper, e)
        result = {
            "summary": f"Analyse-Fehler: {e}",
            "relevant_headlines": [],
            "trend": "stable",
            "sentiment_count": {"positive": 0, "negative": 0, "neutral": 0},
            "consensus_direction": "neutral",
            "ampel_relevance": "Keine Aussage möglich.",
        }

    doc = {
        "ticker": ticker_upper,
        "date": date_str,
        "name": asset_name,
        "summary": result.get("summary", ""),
        "development": result.get("development", ""),
        "recurring": result.get("recurring", ""),
        "relevant_headlines": result.get("relevant_headlines", []),
        "sentiment_count": result.get("sentiment_count", {}),
        "trend": result.get("trend", "stable"),
        "trend_reasoning": result.get("trend_reasoning", ""),
        "consensus_direction": result.get("consensus_direction", "neutral"),
        "ampel_relevance": result.get("ampel_relevance", ""),
        "headlines_fetched": len(headlines_to_analyze),
        "updated_at": datetime.now().isoformat(),
    }

    db.analyst_news.update_one(
        {"ticker": ticker_upper, "date": date_str},
        {"$set": doc},
        upsert=True,
    )

    # Index for semantic search
    try:
        from ..embeddings import index_news
        existing = db.analyst_news.find_one({"ticker": ticker_upper, "date": date_str})
        if existing:
            news_doc = {**doc, "topic": f"analyst-news-{ticker_upper.lower()}", "title": f"Analysten-News {asset_name}"}
            index_news(str(existing["_id"]), news_doc)
    except Exception as e:
        log.warning("Analyst-News Indizierung fehlgeschlagen für %s: %s", ticker_upper, e)

    log.info("Analyst-News %s: trend=%s, %d Headlines", ticker_upper, doc["trend"], len(doc["relevant_headlines"]))
    return doc


def sync_all_analyst_news(db=None):
    """Sync analyst news for all watchlist tickers."""
    if db is None:
        db = get_db()

    watchlist = list(db.watchlist.find().sort("ticker", 1))
    results = []
    for wl in watchlist:
        ticker = wl["ticker"]
        try:
            doc = sync_analyst_news_for_ticker(db, ticker)
            results.append({"ticker": ticker, "status": "ok", "trend": doc.get("trend") if doc else "?"})
        except Exception as e:
            log.error("Analyst-News Sync für %s fehlgeschlagen: %s", ticker, e)
            results.append({"ticker": ticker, "status": "error"})
    return results


@router.post("/analyst-news/sync")
def sync_analyst_news_endpoint():
    """Sync analyst news for all watchlist tickers."""
    db = get_db()
    results = sync_all_analyst_news(db)
    return {"results": results, "synced": len([r for r in results if r["status"] == "ok"])}


@router.get("/analyst-news/{ticker}")
def get_analyst_news(ticker: str, limit: int = 5):
    """Get latest analyst news for a ticker."""
    db = get_db()
    docs = list(
        db.analyst_news.find(
            {"ticker": ticker.upper()},
        ).sort("date", -1).limit(limit)
    )
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


def _fetch_analyst_data(ticker: str):
    """Fetch analyst ratings from yfinance for a single ticker. Returns dict or None."""
    import yfinance as yf
    from datetime import timedelta

    try:
        t = yf.Ticker(ticker.upper())

        # Aggregated recommendations (current month)
        recs = t.recommendations
        summary = {"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}
        if recs is not None and not recs.empty:
            current = recs[recs["period"] == "0m"]
            if not current.empty:
                row = current.iloc[0]
                summary = {
                    "strongBuy": int(row.get("strongBuy", 0)),
                    "buy": int(row.get("buy", 0)),
                    "hold": int(row.get("hold", 0)),
                    "sell": int(row.get("sell", 0)),
                    "strongSell": int(row.get("strongSell", 0)),
                }

        # Individual upgrades/downgrades from last 3 weeks
        upgrades = t.upgrades_downgrades
        individual = []
        if upgrades is not None and not upgrades.empty:
            cutoff = datetime.now() - timedelta(weeks=3)
            for idx, row in upgrades.iterrows():
                grade_date = idx
                if hasattr(grade_date, 'to_pydatetime'):
                    grade_date = grade_date.to_pydatetime()
                if hasattr(grade_date, 'replace'):
                    grade_date_naive = grade_date.replace(tzinfo=None) if grade_date.tzinfo else grade_date
                else:
                    continue
                if grade_date_naive < cutoff:
                    continue
                entry = {
                    "date": grade_date_naive.strftime("%Y-%m-%d"),
                    "firm": row.get("Firm", ""),
                    "toGrade": row.get("ToGrade", ""),
                    "fromGrade": row.get("FromGrade", ""),
                    "action": row.get("Action", ""),
                }
                # Price targets
                current_pt = row.get("currentPriceTarget")
                prior_pt = row.get("priorPriceTarget")
                if current_pt and not (current_pt != current_pt):  # NaN check
                    entry["currentPriceTarget"] = round(float(current_pt), 2)
                if prior_pt and not (prior_pt != prior_pt):  # NaN check
                    entry["priorPriceTarget"] = round(float(prior_pt), 2)
                individual.append(entry)

        return {
            "ticker": ticker.upper(),
            "summary": summary,
            "total": sum(summary.values()),
            "individual": individual,
        }
    except Exception as e:
        log.error("Analyst-Ratings für %s fehlgeschlagen: %s", ticker, e)
        return None


def sync_analyst_ratings(db=None):
    """Fetch and store analyst ratings for all watchlist tickers. Returns list of results."""
    if db is None:
        db = get_db()

    watchlist = list(db.watchlist.find().sort("ticker", 1))
    date_str = datetime.now().strftime("%Y-%m-%d")
    results = []

    for wl in watchlist:
        ticker = wl["ticker"]
        data = _fetch_analyst_data(ticker)
        if not data:
            results.append({"ticker": ticker, "status": "error"})
            continue

        doc = {
            "ticker": ticker,
            "date": date_str,
            "name": wl.get("name", ticker),
            "summary": data["summary"],
            "total": data["total"],
            "individual": data["individual"],
            "updated_at": datetime.now().isoformat(),
        }

        result = db.analyst_ratings.update_one(
            {"ticker": ticker, "date": date_str},
            {"$set": doc},
            upsert=True,
        )

        # Index for semantic search
        try:
            from ..embeddings import index_analyst_rating
            rating_id = str(result.upserted_id) if result.upserted_id else None
            if not rating_id:
                existing = db.analyst_ratings.find_one({"ticker": ticker, "date": date_str})
                rating_id = str(existing["_id"]) if existing else f"{ticker}_{date_str}"
            index_analyst_rating(rating_id, doc)
        except Exception as e:
            log.warning("Analyst-Rating Indizierung fehlgeschlagen für %s: %s", ticker, e)

        results.append({"ticker": ticker, "status": "ok", "total": data["total"]})
        log.info("Analyst-Ratings %s: %d Analysten", ticker, data["total"])

    return results


@router.post("/analyst-ratings/sync")
def sync_analyst_ratings_endpoint():
    """Sync analyst ratings for all watchlist tickers."""
    db = get_db()
    results = sync_analyst_ratings(db)
    return {"results": results, "synced": len([r for r in results if r["status"] == "ok"])}


@router.get("/analyst-ratings/{ticker}")
def get_analyst_ratings(ticker: str):
    """Analystenmeinungen für ein Asset (latest aus DB, fallback live)."""
    db = get_db()
    ticker_upper = ticker.upper()

    # Try latest from DB first
    doc = db.analyst_ratings.find_one(
        {"ticker": ticker_upper},
        sort=[("date", -1)],
    )

    if doc:
        doc["_id"] = str(doc["_id"])
        return doc

    # Fallback: live fetch
    data = _fetch_analyst_data(ticker_upper)
    if not data:
        raise HTTPException(status_code=500, detail=f"Analyst-Ratings für {ticker_upper} nicht verfügbar.")

    wl = db.watchlist.find_one({"ticker": ticker_upper})
    data["name"] = wl["name"] if wl else ticker_upper
    return data


@router.get("/analyst-ratings/{ticker}/history")
def get_analyst_ratings_history(ticker: str, limit: int = 30):
    """Historische Analystenmeinungen für ein Asset."""
    db = get_db()
    docs = list(
        db.analyst_ratings.find(
            {"ticker": ticker.upper()},
            {"individual": 0},
        ).sort("date", -1).limit(limit)
    )
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    docs.reverse()
    return docs


@router.get("/asset-news/{ticker}")
def get_asset_news(ticker: str, limit: int = 5):
    """Neueste News-Ergebnisse für ein Asset (aus verknüpften News-Topics)."""
    db = get_db()
    ticker_upper = ticker.upper()

    # Find all news topics linked to this asset
    topics = list(db.news_topics.find({"asset": ticker_upper}, {"topic": 1, "title": 1}))
    if not topics:
        return []

    topic_slugs = [t["topic"] for t in topics]
    topic_titles = {t["topic"]: t.get("title", t["topic"]) for t in topics}

    # Get latest results for each topic
    results = list(
        db.news_results.find(
            {"topic": {"$in": topic_slugs}},
            {"raw_headlines": 0, "relevant_headlines": 0},
        ).sort("date", -1).limit(limit * len(topic_slugs))
    )

    # Group by topic, take latest per topic
    seen = {}
    output = []
    for r in results:
        r["_id"] = str(r["_id"])
        r["topic_title"] = topic_titles.get(r["topic"], r["topic"])
        key = r["topic"]
        if key not in seen:
            seen[key] = 0
        if seen[key] < limit:
            output.append(r)
            seen[key] += 1

    return output


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
