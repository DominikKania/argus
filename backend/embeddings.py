"""Semantic search module using ChromaDB with built-in ONNX embeddings.

Provides embedding storage and similarity search for theses, analyses,
lessons, and news. Uses ChromaDB's default all-MiniLM-L6-v2 model
(runs locally via ONNX, no API calls needed).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb

log = logging.getLogger("argus.embeddings")

# Persistent ChromaDB storage in project directory
_CHROMA_DIR = str(Path(__file__).resolve().parent.parent / "chroma_data")
_client = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=_CHROMA_DIR)
        log.info("ChromaDB initialisiert: %s", _CHROMA_DIR)
    return _client


def get_collection(name: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    return _get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ── Index Functions ──────────────────────────────────────────────────────


def index_thesis(thesis_id: str, thesis: dict):
    """Index a thesis for semantic search."""
    text = _build_thesis_text(thesis)
    if not text:
        return

    col = get_collection("theses")
    col.upsert(
        ids=[thesis_id],
        documents=[text],
        metadatas=[{
            "status": thesis.get("status", "open"),
            "target_level": thesis.get("target_level", ""),
            "stop_loss": thesis.get("stop_loss", ""),
            "created_date": thesis.get("created_date", ""),
        }],
    )
    log.info("These indiziert: %s", thesis_id)


def index_analysis(analysis_id: str, analysis: dict):
    """Index an analysis for historical comparison."""
    parts = []
    rating = analysis.get("rating", {})
    if rating.get("reasoning"):
        parts.append(rating["reasoning"])

    for name in ["trend", "volatility", "macro", "sentiment"]:
        sig = analysis.get("signals", {}).get(name, {})
        if sig.get("note"):
            parts.append(f"{name}: {sig['note']}")

    rec = analysis.get("recommendation", {})
    if rec.get("detail"):
        parts.append(rec["detail"])

    hist = analysis.get("historical_comparison")
    if hist:
        parts.append(hist)

    text = "\n".join(parts)
    if not text.strip():
        return

    col = get_collection("analyses")
    col.upsert(
        ids=[analysis_id],
        documents=[text],
        metadatas=[{
            "date": analysis.get("date", ""),
            "overall": rating.get("overall", ""),
            "score": str(rating.get("mechanical_score", "")),
        }],
    )


def index_lesson(thesis_id: str, thesis: dict):
    """Index a resolved thesis with lessons for retrieval."""
    lessons = thesis.get("lessons_learned", "")
    if not lessons:
        return

    statement = thesis.get("statement", "")
    resolution = thesis.get("resolution", "")
    text = f"These: {statement}\nAufloesung: {resolution}\nRegeln: {lessons}"

    col = get_collection("lessons")
    col.upsert(
        ids=[thesis_id],
        documents=[text],
        metadatas=[{
            "statement": statement[:200],
            "resolution_date": thesis.get("resolution_date", ""),
        }],
    )
    log.info("Lesson indiziert: %s", thesis_id)


def index_research(research_id: str, research: dict):
    """Index a research result for semantic search."""
    parts = []
    if research.get("title"):
        parts.append(research["title"])
    if research.get("relevance_summary"):
        parts.append(research["relevance_summary"])
    if research.get("results"):
        # Include first meaningful lines of results for embedding
        lines = [l.strip() for l in research["results"].split("\n")
                 if l.strip() and not l.startswith("#")]
        parts.append("\n".join(lines[:20]))

    text = "\n".join(parts)
    if not text.strip():
        return

    col = get_collection("research")
    col.upsert(
        ids=[research_id],
        documents=[text[:2000]],  # ChromaDB has doc size limits
        metadatas=[{
            "title": research.get("title", ""),
            "status": research.get("status", ""),
            "last_run_date": research.get("last_run_date", ""),
        }],
    )
    log.info("Research indiziert: %s — %s", research_id, research.get("title", "?"))


def index_analyst_rating(rating_id: str, rating: dict):
    """Index analyst rating data for semantic search."""
    parts = []
    ticker = rating.get("ticker", "")
    name = rating.get("name", ticker)
    date = rating.get("date", "")

    s = rating.get("summary", {})
    parts.append(f"Analystenmeinungen {name} ({ticker}) vom {date}")
    parts.append(
        f"Strong Buy: {s.get('strongBuy', 0)}, Buy: {s.get('buy', 0)}, "
        f"Hold: {s.get('hold', 0)}, Sell: {s.get('sell', 0)}, "
        f"Strong Sell: {s.get('strongSell', 0)}, Total: {rating.get('total', 0)}"
    )

    # Include individual ratings
    for ind in rating.get("individual", [])[:15]:
        grade_info = f"{ind.get('firm', '')}: {ind.get('toGrade', '')}"
        if ind.get("fromGrade"):
            grade_info += f" (vorher: {ind['fromGrade']})"
        if ind.get("action"):
            grade_info += f" [{ind['action']}]"
        parts.append(grade_info)

    text = "\n".join(parts)
    if not text.strip():
        return

    col = get_collection("analyst_ratings")
    col.upsert(
        ids=[rating_id],
        documents=[text[:2000]],
        metadatas=[{
            "ticker": ticker,
            "date": date,
            "total": str(rating.get("total", 0)),
        }],
    )
    log.info("Analyst-Rating indiziert: %s %s", ticker, date)


def index_news(news_id: str, news: dict):
    """Index a news result for semantic search."""
    parts = []
    if news.get("title"):
        parts.append(news["title"])
    if news.get("summary"):
        parts.append(news["summary"])
    if news.get("development"):
        parts.append(news["development"])
    if news.get("ampel_relevance"):
        parts.append(news["ampel_relevance"])

    text = "\n".join(parts)
    if not text.strip():
        return

    col = get_collection("news")
    col.upsert(
        ids=[news_id],
        documents=[text],
        metadatas=[{
            "topic": news.get("topic", ""),
            "date": news.get("date", ""),
            "trend": news.get("trend", ""),
        }],
    )


# ── Search Functions ─────────────────────────────────────────────────────


def find_similar_theses(query: str, n: int = 5, status: str = None) -> list[dict]:
    """Find theses semantically similar to a query."""
    col = get_collection("theses")
    if col.count() == 0:
        return []

    kwargs = {"query_texts": [query], "n_results": min(n, col.count())}
    if status:
        kwargs["where"] = {"status": status}

    results = col.query(**kwargs)
    return _format_results(results)


def find_similar_analyses(query: str, n: int = 5) -> list[dict]:
    """Find past analyses similar to current market situation."""
    col = get_collection("analyses")
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
    )
    return _format_results(results)


def find_relevant_lessons(query: str, n: int = 3) -> list[dict]:
    """Find lessons most relevant to the current situation."""
    col = get_collection("lessons")
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
    )
    return _format_results(results)


def find_similar_research(query: str, n: int = 5) -> list[dict]:
    """Find research results semantically similar to a query."""
    col = get_collection("research")
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
    )
    return _format_results(results)


def find_similar_analyst_ratings(query: str, n: int = 5) -> list[dict]:
    """Find analyst ratings semantically similar to a query."""
    col = get_collection("analyst_ratings")
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
    )
    return _format_results(results)


def find_similar_news(query: str, n: int = 5) -> list[dict]:
    """Find news semantically similar to a query."""
    col = get_collection("news")
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
    )
    return _format_results(results)


def check_thesis_duplicate(thesis: dict, threshold: float = 0.15) -> Optional[dict]:
    """Check if a thesis is semantically a duplicate of an existing open thesis.

    Returns the most similar existing thesis if distance < threshold, else None.
    Lower distance = more similar (cosine distance: 0 = identical, 2 = opposite).
    """
    text = _build_thesis_text(thesis)
    if not text:
        return None

    col = get_collection("theses")
    if col.count() == 0:
        return None

    results = col.query(
        query_texts=[text],
        n_results=1,
        where={"status": "open"},
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"][0]:
        return None

    distance = results["distances"][0][0]
    if distance < threshold:
        return {
            "id": results["ids"][0][0],
            "distance": distance,
            "document": results["documents"][0][0],
            "metadata": results["metadatas"][0][0],
        }
    return None


# ── Bulk Index (for backfilling existing data) ───────────────────────────


def reindex_all(db):
    """Reindex all existing data from MongoDB into ChromaDB."""
    count = {"theses": 0, "analyses": 0, "lessons": 0, "news": 0, "research": 0, "analyst_ratings": 0}

    # Theses
    for doc in db.theses.find():
        tid = str(doc["_id"])
        index_thesis(tid, doc)
        if doc.get("status") == "resolved" and doc.get("lessons_learned"):
            index_lesson(tid, doc)
            count["lessons"] += 1
        count["theses"] += 1

    # Analyses
    for doc in db.analyses.find():
        index_analysis(str(doc["_id"]), doc)
        count["analyses"] += 1

    # News
    for doc in db.news_results.find():
        index_news(str(doc["_id"]), doc)
        count["news"] += 1

    # Research
    for doc in db.researches.find({"status": "completed"}):
        index_research(str(doc["_id"]), doc)
        count["research"] += 1

    # Analyst Ratings
    for doc in db.analyst_ratings.find():
        index_analyst_rating(str(doc["_id"]), doc)
        count["analyst_ratings"] += 1

    log.info("Reindex abgeschlossen: %s", count)
    return count


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_thesis_text(thesis: dict) -> str:
    """Build a searchable text from thesis fields."""
    parts = []
    if thesis.get("title"):
        parts.append(thesis["title"])
    if thesis.get("statement"):
        parts.append(thesis["statement"])
    if thesis.get("catalyst"):
        parts.append(f"Katalysator: {thesis['catalyst']}")
    if thesis.get("expected_if_positive"):
        parts.append(f"Positiv: {thesis['expected_if_positive']}")
    if thesis.get("expected_if_negative"):
        parts.append(f"Negativ: {thesis['expected_if_negative']}")
    return "\n".join(parts)


def _format_results(results: dict) -> list[dict]:
    """Format ChromaDB query results into a simple list."""
    items = []
    if not results["ids"][0]:
        return items

    for i, doc_id in enumerate(results["ids"][0]):
        item = {
            "id": doc_id,
            "document": results["documents"][0][i] if results.get("documents") else None,
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else None,
        }
        if results.get("distances"):
            item["distance"] = results["distances"][0][i]
        items.append(item)
    return items
