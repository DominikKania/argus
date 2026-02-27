"""News API routes for RSS-based news monitoring topics."""

import logging
import re
from typing import Optional
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..llm import call_llm

log = logging.getLogger("argus")

router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────

UMLAUT_MAP = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}


def slugify(title: str) -> str:
    """Convert title to URL-safe slug. Handles German umlauts."""
    slug = title.lower()
    for char, repl in UMLAUT_MAP.items():
        slug = slug.replace(char, repl)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _resolve_topic(db, id_or_slug: str):
    """Resolve a news topic by ObjectId or slug."""
    try:
        doc = db.news_topics.find_one({"_id": ObjectId(id_or_slug)})
        if doc:
            return doc
    except Exception:
        pass
    doc = db.news_topics.find_one({"topic": id_or_slug})
    if doc:
        return doc
    return None


def _serialize(doc):
    """Convert MongoDB doc for JSON response."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── System Prompts ───────────────────────────────────────────────────────

PROMPT_HELPER_SYSTEM = """\
Du erstellst fokussierte News-Analyse-Prompts für das Argus Investment-System.

Der Prompt wird täglich verwendet um RSS-Headlines zu einem bestimmten Thema zu analysieren.
Er soll Claude anweisen:
- Welche Art von Headlines relevant sind
- Worauf genau geachtet werden soll (Eskalation/De-Eskalation, Tonwechsel, Zeitplan etc.)
- Welche Trigger-Events wichtig wären
- Wie das Thema das IWDA-Portfolio (100% MSCI World ETF, ~6.700€) betrifft

## REGELN
- Schreibe den Prompt auf Deutsch, klar und spezifisch
- Maximal 10-15 Zeilen
- Gib NUR den Prompt-Text zurück, keine Erklärung\
"""

REFINE_PROMPT_SYSTEM = """\
Du bist ein News-Prompt-Experte im Argus Investment-System. Der Benutzer hat einen \
News-Analyse-Prompt mit einem Tutor besprochen. Basierend auf dem Gesprächsverlauf sollst du \
den Prompt optimieren.

## HEUTIGES DATUM
{today}

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## DEINE AUFGABE
- Lies den Original-Prompt und den Gesprächsverlauf
- Integriere alle Verbesserungsvorschläge, Wünsche und Feedback des Benutzers
- Erstelle eine verbesserte Version des News-Analyse-Prompts
- Der Prompt wird täglich auf RSS-Headlines angewendet

## REGELN
- Antworte NUR mit dem verbesserten Prompt-Text
- Kein JSON, kein Markdown-Wrapper, keine Erklärungen
- Der Prompt soll auf Deutsch sein\
"""


# ── Models ───────────────────────────────────────────────────────────────

class CreateNewsTopicRequest(BaseModel):
    title: str
    prompt: Optional[str] = None
    direction: Optional[str] = None
    rss_feeds: Optional[list[dict]] = None


class UpdateNewsTopicRequest(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    active: Optional[bool] = None
    rss_feeds: Optional[list[dict]] = None


class GeneratePromptRequest(BaseModel):
    title: str
    direction: Optional[str] = None


class RefinePromptRequest(BaseModel):
    topic_title: str
    original_prompt: str
    chat_history: list[dict]


# ── Endpoints: Topics ───────────────────────────────────────────────────

@router.get("/topics")
def list_topics():
    """List all news topics."""
    db = get_db()
    docs = list(db.news_topics.find().sort("updated_date", -1))
    for doc in docs:
        _serialize(doc)
        # Letzte Ergebnisse dazuladen
        latest = db.news_results.find_one(
            {"topic": doc["topic"]},
            {"raw_headlines": 0},
            sort=[("date", -1)],
        )
        doc["latest_result"] = _serialize(latest) if latest else None
    return docs


@router.get("/topics/{id_or_slug}")
def get_topic(id_or_slug: str):
    """Get a news topic with latest results."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="News-Topic nicht gefunden.")
    _serialize(doc)

    # Letzte 5 Ergebnisse dazuladen
    results = list(
        db.news_results.find(
            {"topic": doc["topic"]},
            {"raw_headlines": 0},
        ).sort("date", -1).limit(5)
    )
    for r in results:
        _serialize(r)
    doc["results_history"] = results

    return doc


@router.post("/topics")
def create_topic(req: CreateNewsTopicRequest):
    """Create a new news topic. Auto-generates prompt if not provided."""
    db = get_db()
    topic_slug = slugify(req.title)

    if db.news_topics.find_one({"topic": topic_slug}):
        raise HTTPException(status_code=409, detail=f"Topic '{topic_slug}' existiert bereits.")

    now = datetime.now().strftime("%Y-%m-%d")

    # Auto-generate prompt if not provided
    prompt = req.prompt
    if not prompt:
        try:
            user_msg = f"Erstelle einen News-Analyse-Prompt zum Thema: {req.title}"
            if req.direction:
                user_msg += f"\n\nFokus/Richtung des Users: {req.direction}"
            prompt = call_llm(
                PROMPT_HELPER_SYSTEM,
                [{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            log.error("News-Prompt-Generierung fehlgeschlagen: %s", e)
            prompt = ""

    doc = {
        "topic": topic_slug,
        "title": req.title,
        "prompt": prompt,
        "active": True,
        "rss_feeds": req.rss_feeds,
        "created_date": now,
        "updated_date": now,
    }

    result = db.news_topics.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.post("/generate-prompt")
def generate_prompt(req: GeneratePromptRequest):
    """Generate a news prompt without saving (for preview)."""
    try:
        user_msg = f"Erstelle einen News-Analyse-Prompt zum Thema: {req.title}"
        if req.direction:
            user_msg += f"\n\nFokus/Richtung des Users: {req.direction}"
        prompt = call_llm(
            PROMPT_HELPER_SYSTEM,
            [{"role": "user", "content": user_msg}],
        )
        return {"prompt": prompt}
    except Exception as e:
        log.error("News-Prompt-Generierung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Prompt-Generierung fehlgeschlagen.")


@router.post("/refine-prompt")
def refine_prompt(req: RefinePromptRequest):
    """Refine a news prompt based on chat conversation."""
    try:
        parts = [f"## Original-Prompt zum Thema: {req.topic_title}\n\n{req.original_prompt}"]
        parts.append("\n## Gesprächsverlauf")
        for msg in req.chat_history:
            role = "Benutzer" if msg.get("role") == "user" else "Tutor"
            parts.append(f"\n**{role}:** {msg.get('content', '')}")
        parts.append("\n\nErstelle jetzt den verbesserten Prompt.")

        system = REFINE_PROMPT_SYSTEM.format(today=datetime.now().strftime("%Y-%m-%d"))
        refined = call_llm(
            system,
            [{"role": "user", "content": "\n".join(parts)}],
        )
        return {"prompt": refined}
    except Exception as e:
        log.error("News-Prompt-Verfeinerung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Prompt-Verfeinerung fehlgeschlagen.")


@router.put("/topics/{id_or_slug}")
def update_topic(id_or_slug: str, req: UpdateNewsTopicRequest):
    """Update a news topic's title, prompt, active status, or RSS feeds."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="News-Topic nicht gefunden.")

    update = {"updated_date": datetime.now().strftime("%Y-%m-%d")}
    if req.title is not None:
        update["title"] = req.title
        update["topic"] = slugify(req.title)
    if req.prompt is not None:
        update["prompt"] = req.prompt
    if req.active is not None:
        update["active"] = req.active
    if req.rss_feeds is not None:
        update["rss_feeds"] = req.rss_feeds

    db.news_topics.update_one({"_id": doc["_id"]}, {"$set": update})

    updated = db.news_topics.find_one({"_id": doc["_id"]})
    return _serialize(updated)


@router.delete("/topics/{id_or_slug}")
def delete_topic(id_or_slug: str):
    """Delete a news topic and all its results."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="News-Topic nicht gefunden.")

    db.news_topics.delete_one({"_id": doc["_id"]})
    deleted_results = db.news_results.delete_many({"topic": doc["topic"]})
    return {
        "deleted": True,
        "topic": doc["topic"],
        "results_deleted": deleted_results.deleted_count,
    }


# ── Endpoints: Run & Results ────────────────────────────────────────────

@router.post("/topics/{id_or_slug}/run")
def run_topic(id_or_slug: str):
    """Run news analysis for a single topic."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="News-Topic nicht gefunden.")

    if not doc.get("prompt", "").strip():
        raise HTTPException(status_code=400, detail="Kein Prompt definiert.")

    try:
        from news import run_news_topic
        result = run_news_topic(db, doc["topic"])
        if result:
            _serialize(result)
            return result
        raise HTTPException(status_code=500, detail="News-Analyse hat kein Ergebnis geliefert.")
    except Exception as e:
        log.error("News-Analyse fehlgeschlagen für '%s': %s", doc["topic"], e)
        raise HTTPException(status_code=500, detail=f"News-Analyse fehlgeschlagen: {e}")


@router.post("/run-all")
def run_all_topics():
    """Run news analysis for all active topics."""
    db = get_db()
    try:
        from news import run_all_news_topics
        count = run_all_news_topics(db)
        return {"topics_analyzed": count}
    except Exception as e:
        log.error("News run-all fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=f"News-Analyse fehlgeschlagen: {e}")


@router.get("/results/{topic_slug}")
def get_results(topic_slug: str, limit: int = 10):
    """Get result history for a topic."""
    db = get_db()
    results = list(
        db.news_results.find(
            {"topic": topic_slug},
            {"raw_headlines": 0},
        ).sort("date", -1).limit(limit)
    )
    for r in results:
        _serialize(r)
    return results


@router.get("/latest")
def get_latest_results():
    """Get the most recent result for each active topic."""
    db = get_db()
    topics = list(db.news_topics.find({"active": True}))
    results = []
    for topic in topics:
        latest = db.news_results.find_one(
            {"topic": topic["topic"]},
            {"raw_headlines": 0},
            sort=[("date", -1)],
        )
        if latest:
            _serialize(latest)
            latest["title"] = topic["title"]
            results.append(latest)
    return results
