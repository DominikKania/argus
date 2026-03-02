"""Ampel API routes."""

import json
import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys
from pathlib import Path

# Ensure project root is in path for ampel_data import
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ..db import get_db
from ..llm import call_llm
from ampel_data import fetch_all_market_data, calculate_mechanical_signals
from ampel_auto import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger("argus")

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────

class UpdateThesisRequest(BaseModel):
    statement: Optional[str] = None
    catalyst: Optional[str] = None
    catalyst_date: Optional[str] = None
    expected_if_positive: Optional[str] = None
    expected_if_negative: Optional[str] = None


class RefineThesisRequest(BaseModel):
    thesis: dict
    chat_history: list[dict]


# ── System Prompts ────────────────────────────────────────────────────────

REFINE_THESIS_SYSTEM = """\
Du bist ein Investment-Analyst im Argus Investment-System. Der Benutzer hat eine \
Investment-These mit einem Tutor besprochen. Basierend auf dem Gesprächsverlauf sollst du \
die These optimieren.

## HEUTIGES DATUM
{today}

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## DEINE AUFGABE
- Lies die Original-These und den Gesprächsverlauf
- Integriere alle Verbesserungsvorschläge, Wünsche und Feedback des Benutzers
- Erstelle eine verbesserte Version der These
- Behalte gute Aspekte des Originals bei, verbessere schwache Stellen
- Stelle sicher, dass die These spezifisch, testbar und relevant für das Portfolio ist

## SPRACHE & VERSTÄNDLICHKEIT
- Schreibe ALLE Texte in klarem, einfachem Deutsch — wie für einen interessierten Laien
- KEINE Fachkürzel, Paragraphen-Nummern oder Gesetzesbezeichnungen (NICHT "Section 122", "IEEPA", "Art. 122 AEUV" etc.)
- Stattdessen das Konzept in einfachen Worten erklären (z.B. "US-Notfallzölle" statt "Section-122-Zölle")
- Kurze, klare Sätze. Jeder Satz muss ohne Vorwissen verständlich sein
- Konkrete Auswirkungen beschreiben, nicht abstrakte Mechanismen

## REGELN
- Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text drumherum)
- Das JSON hat exakt diese Felder:
  - "statement": Die Kernaussage der These — ein klarer, verständlicher Satz
  - "catalyst": Was genau muss passieren? In einfachen Worten
  - "catalyst_date": Datum im Format YYYY-MM-DD — max. 4-6 Wochen in der Zukunft!
  - "expected_if_positive": Was passiert für mein Portfolio wenn die These eintritt?
  - "expected_if_negative": Was passiert für mein Portfolio wenn die These nicht eintritt?
- Die These muss testbar und zeitlich eingrenzbar sein
- WICHTIG: Zeithorizont max. 4-6 Wochen! Lieber einen konkreten nächsten Schritt \
testen als ein vages Langfrist-Szenario. Keine Thesen über Monate hinweg.
- Alle Daten müssen im aktuellen Jahr ({year}) oder später liegen!"""


def _serialize_doc(doc):
    """Convert MongoDB ObjectId fields to strings for JSON serialization."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    if "analysis_id" in doc:
        doc["analysis_id"] = str(doc["analysis_id"])
    return doc


@router.get("/market-data")
def get_market_data():
    """Fetch fresh market data from yfinance."""
    try:
        db = get_db()
        market = fetch_all_market_data(db)
        signals, score = calculate_mechanical_signals(market)
        return {
            "market": market,
            "mechanical_signals": signals,
            "mechanical_score": score,
        }
    except Exception as e:
        log.error("Marktdaten-Abruf fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=f"Marktdaten-Abruf fehlgeschlagen: {e}")


@router.get("/prompts")
def get_prompts():
    """Baut den Analyse-Prompt live aus der aktuellen Analyse zusammen."""
    db = get_db()
    analysis = db.analyses.find_one(sort=[("date", -1)])
    if not analysis:
        raise HTTPException(status_code=404, detail="Keine Analyse vorhanden")

    today = datetime.now().strftime("%Y-%m-%d")

    market = analysis.get("market", {})
    signals, score = calculate_mechanical_signals(market)

    history = list(db.analyses.find({}, {"_id": 0}).sort("date", -1).limit(6))[1:]
    theses = list(db.theses.find({"status": "open"}, {"_id": 0}))
    researches = list(db.researches.find(
        {"status": "completed", "relevance_summary": {"$ne": None}},
        {"_id": 0},
    ))
    # Neueste News pro Topic (nicht nur Analyse-Datum)
    news_results = []
    seen_topics = set()
    for nr in db.news_results.find(
        {}, {"raw_headlines": 0, "_id": 0}
    ).sort("date", -1):
        topic = nr.get("topic", "")
        if topic not in seen_topics:
            seen_topics.add(topic)
            news_results.append(nr)

    user_prompt = build_user_prompt(
        market, signals, score, history, theses, researches, news_results
    )

    return {
        "system": SYSTEM_PROMPT,
        "user": user_prompt,
    }


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


@router.put("/theses/{thesis_id}")
def update_thesis(thesis_id: str, req: UpdateThesisRequest):
    """Update an open thesis."""
    db = get_db()
    try:
        oid = ObjectId(thesis_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige Thesis-ID.")

    doc = db.theses.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="These nicht gefunden.")

    update = {}
    for field in ("statement", "catalyst", "catalyst_date", "expected_if_positive", "expected_if_negative"):
        val = getattr(req, field, None)
        if val is not None:
            update[field] = val

    if not update:
        raise HTTPException(status_code=400, detail="Keine Änderungen angegeben.")

    db.theses.update_one({"_id": oid}, {"$set": update})
    updated = db.theses.find_one({"_id": oid})
    return _serialize_doc(updated)


def _build_news_context(db) -> str:
    """Build news context from latest results for all active topics."""
    results = list(
        db.news_results.find(
            {},
            {"raw_headlines": 0, "_id": 0},
        ).sort("date", -1).limit(10)
    )
    if not results:
        return ""

    parts = ["\n## AKTUELLE NEWS-DATEN"]
    seen_topics = set()
    for r in results:
        topic = r.get("topic", "")
        if topic in seen_topics:
            continue
        seen_topics.add(topic)

        parts.append(f"\n### {topic} ({r.get('date', '?')}) — Trend: {r.get('trend', '?')}")
        if r.get("development"):
            parts.append(f"Neue Entwicklung: {r['development']}")
        if r.get("recurring"):
            parts.append(f"Bestätigt sich: {r['recurring']}")
        if r.get("summary"):
            parts.append(f"Einordnung: {r['summary']}")
        if r.get("triggers_detected"):
            parts.append(f"Trigger: {', '.join(r['triggers_detected'])}")
        if r.get("ampel_relevance"):
            parts.append(f"Ampel-Relevanz: {r['ampel_relevance']}")

        headlines = r.get("relevant_headlines", [])
        high = [h for h in headlines if h.get("relevance") == "high"]
        if high:
            parts.append("Wichtigste Schlagzeilen:")
            for h in high[:5]:
                sentiment = h.get("sentiment", "neutral")
                parts.append(f"  - [{sentiment}] {h.get('title', '?')}")

        if r.get("deep_research"):
            # First 500 chars of deep research as context
            preview = r["deep_research"][:500]
            if len(r["deep_research"]) > 500:
                preview += "..."
            parts.append(f"Deep-Research-Auszug: {preview}")

    return "\n".join(parts)


@router.post("/theses/refine")
def refine_thesis(req: RefineThesisRequest):
    """Refine a thesis based on chat conversation."""
    try:
        db = get_db()

        parts = [
            "## Original-These",
            f"**Statement:** {req.thesis.get('statement', '')}",
        ]
        if req.thesis.get("catalyst"):
            parts.append(f"**Katalysator:** {req.thesis['catalyst']}")
        if req.thesis.get("catalyst_date"):
            parts.append(f"**Katalysator-Datum:** {req.thesis['catalyst_date']}")
        if req.thesis.get("expected_if_positive"):
            parts.append(f"**Wenn positiv:** {req.thesis['expected_if_positive']}")
        if req.thesis.get("expected_if_negative"):
            parts.append(f"**Wenn negativ:** {req.thesis['expected_if_negative']}")

        # Add news context
        news_ctx = _build_news_context(db)
        if news_ctx:
            parts.append(news_ctx)

        parts.append("\n## Gesprächsverlauf")
        for msg in req.chat_history:
            role = "Benutzer" if msg.get("role") == "user" else "Tutor"
            parts.append(f"\n**{role}:** {msg.get('content', '')}")
        parts.append("\n\nErstelle jetzt die verbesserte These als JSON. Nutze die News-Daten als Faktengrundlage.")

        now = datetime.now()
        system = REFINE_THESIS_SYSTEM.format(today=now.strftime("%Y-%m-%d"), year=now.year)
        result = call_llm(
            system,
            [{"role": "user", "content": "\n".join(parts)}],
        )

        # Parse JSON from response (strip markdown fences if present)
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        thesis_data = json.loads(cleaned)
        return {"thesis": thesis_data}
    except json.JSONDecodeError as e:
        log.error("Thesis-Verfeinerung JSON-Parse-Fehler: %s\nAntwort: %s", e, result)
        raise HTTPException(status_code=500, detail="LLM-Antwort konnte nicht als JSON geparst werden.")
    except Exception as e:
        log.error("Thesis-Verfeinerung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Thesis-Verfeinerung fehlgeschlagen.")
