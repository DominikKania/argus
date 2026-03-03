"""Ampel API routes — Multi-Stage Pipeline."""

import json
import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import sys
from pathlib import Path

# Ensure project root is in path for ampel_data import
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ..db import get_db
from ..llm import call_llm, stream_llm
from ampel_data import fetch_all_market_data, calculate_mechanical_signals
from ampel_auto import (
    TREND_ANALYST_PROMPT,
    VOLATILITY_ANALYST_PROMPT,
    MACRO_ANALYST_PROMPT,
    SENTIMENT_ANALYST_PROMPT,
    SYNTHESIS_PROMPT,
    extract_json,
    merge_multistage_analysis,
    run_stage1,
)
from backend.prompt_builder import (
    build_news_context,
    build_trend_analyst_prompt,
    build_volatility_analyst_prompt,
    build_macro_analyst_prompt,
    build_sentiment_analyst_prompt,
    build_synthesis_prompt,
)

log = logging.getLogger("argus")

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────

class UpdateThesisRequest(BaseModel):
    statement: Optional[str] = None
    catalyst: Optional[str] = None
    catalyst_date: Optional[str] = None
    expected_if_positive: Optional[str] = None
    expected_if_negative: Optional[str] = None
    lessons_learned: Optional[str] = None


class ExtractLessonsRequest(BaseModel):
    messages: list[dict]


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
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700\u20ac, 100%

## DEINE AUFGABE
- Lies die Original-These und den Gespr\u00e4chsverlauf
- Integriere alle Verbesserungsvorschl\u00e4ge, W\u00fcnsche und Feedback des Benutzers
- Erstelle eine verbesserte Version der These
- Behalte gute Aspekte des Originals bei, verbessere schwache Stellen
- Stelle sicher, dass die These spezifisch, testbar und relevant f\u00fcr das Portfolio ist

## SPRACHE & VERST\u00c4NDLICHKEIT
- Schreibe ALLE Texte in klarem, einfachem Deutsch
- KEINE Fachk\u00fcrzel, Paragraphen-Nummern oder Gesetzesbezeichnungen
- Stattdessen das Konzept in einfachen Worten erkl\u00e4ren
- Kurze, klare S\u00e4tze. Jeder Satz muss ohne Vorwissen verst\u00e4ndlich sein
- Konkrete Auswirkungen beschreiben, nicht abstrakte Mechanismen

## REGELN
- Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text drumherum)
- Das JSON hat exakt diese Felder:
  - "statement": Die Kernaussage der These
  - "catalyst": Was genau muss passieren?
  - "catalyst_date": Datum im Format YYYY-MM-DD — max. 4-6 Wochen in der Zukunft!
  - "expected_if_positive": Was passiert f\u00fcr mein Portfolio wenn die These eintritt?
  - "expected_if_negative": Was passiert f\u00fcr mein Portfolio wenn die These nicht eintritt?
- WICHTIG: Zeithorizont max. 4-6 Wochen!
- Alle Daten m\u00fcssen im aktuellen Jahr ({year}) oder sp\u00e4ter liegen!"""


def _sanitize_floats(obj):
    """Replace NaN/Infinity with None for JSON compatibility."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _serialize_doc(doc):
    """Convert MongoDB ObjectId fields to strings and sanitize floats for JSON."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    if "analysis_id" in doc:
        doc["analysis_id"] = str(doc["analysis_id"])
    return _sanitize_floats(doc)


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
    """Shows the multi-stage prompt structure for the current analysis."""
    db = get_db()
    analysis = db.analyses.find_one(sort=[("date", -1)])
    if not analysis:
        raise HTTPException(status_code=404, detail="Keine Analyse vorhanden")

    market = analysis.get("market", {})
    signals, score = calculate_mechanical_signals(market)

    history = list(db.analyses.find({}, {"_id": 0}).sort("date", -1).limit(6))[1:]
    theses = list(db.theses.find({"status": "open"}))
    researches = list(db.researches.find(
        {"status": "completed", "relevance_summary": {"$ne": None}},
    ))
    news_results = []
    seen_topics = set()
    for nr in db.news_results.find(
        {}, {"raw_headlines": 0}
    ).sort("date", -1):
        topic = nr.get("topic", "")
        if topic not in seen_topics:
            seen_topics.add(topic)
            news_results.append(nr)
    lessons = list(db.theses.find(
        {"status": "resolved", "lessons_learned": {"$ne": None}},
        {"statement": 1, "lessons_learned": 1},
    ))

    return {
        "stages": {
            "trend": {
                "system": TREND_ANALYST_PROMPT,
                "user": build_trend_analyst_prompt(market, signals, researches),
            },
            "volatility": {
                "system": VOLATILITY_ANALYST_PROMPT,
                "user": build_volatility_analyst_prompt(market, signals, researches),
            },
            "macro": {
                "system": MACRO_ANALYST_PROMPT,
                "user": build_macro_analyst_prompt(market, signals, researches),
            },
            "sentiment": {
                "system": SENTIMENT_ANALYST_PROMPT,
                "user": build_sentiment_analyst_prompt(market, signals, news_results, researches),
            },
            "synthesis": {
                "system": SYNTHESIS_PROMPT,
                "user": build_synthesis_prompt(
                    market, signals, score, {},
                    history, theses, researches, news_results, lessons,
                ),
            },
        },
    }


def _sse_event(event_type: str, data) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
    return f"data: {payload}\n\n"


@router.post("/run")
def run_ampel_analysis():
    """Run full multi-stage Ampel analysis with streaming output."""
    def generate():
        try:
            db = get_db()
            date_str = datetime.now().strftime("%Y-%m-%d")

            # Delete existing analysis for today
            existing = db.analyses.find_one({"date": date_str})
            if existing:
                db.analyses.delete_one({"date": date_str})
                db.theses.delete_many({"analysis_id": existing["_id"]})
                yield _sse_event("status", f"Bestehende Analyse f\u00fcr {date_str} gel\u00f6scht.")

            # 1. Sync prices first (update latest close)
            yield _sse_event("status", "Synchronisiere Kursdaten...")
            try:
                from .prices import sync_prices
                sync_result = sync_prices()
                total_new = sync_result.get("total_new_records", 0)
                yield _sse_event("status", f"Kursdaten synchronisiert ({total_new} neue Einträge).")
            except Exception as e:
                yield _sse_event("status", f"Kurs-Sync fehlgeschlagen: {e}")

            # 2. Market data
            yield _sse_event("status", "Hole Marktdaten...")
            market = fetch_all_market_data(db)
            mech_signals, mech_score = calculate_mechanical_signals(market)
            yield _sse_event("status", f"Marktdaten geladen. Score: {mech_score}/4")

            # 3. News
            active_news = db.news_topics.count_documents({"active": True})
            if active_news > 0:
                yield _sse_event("status", f"Sammle News f\u00fcr {active_news} Topics...")
                try:
                    from news import run_all_news_topics
                    news_count = run_all_news_topics(db)
                    yield _sse_event("status", f"{news_count or 0} News-Topics aktualisiert.")
                except Exception as e:
                    yield _sse_event("status", f"News-Sammlung fehlgeschlagen: {e}")

            # 4. Load context
            yield _sse_event("status", "Lade Kontext (Historie, Thesen, Research, News)...")
            history = list(db.analyses.find(sort=[("date", -1)]).limit(5))
            theses = list(db.theses.find({"status": "open"}).sort("created_date", -1))
            researches = list(db.researches.find(
                {"status": "completed", "relevance_summary": {"$ne": None}},
            ))
            news_results = list(db.news_results.find(
                {"date": date_str}, {"raw_headlines": 0},
            ))

            # 5. Stage 1: Signal-Analysten (4 parallel)
            yield _sse_event("status", "Stage 1: Bewerte Signale (4 Analysten parallel)...")
            stage1_results = run_stage1(market, mech_signals, news_results, researches)

            # Emit signal results
            for name in ["trend", "volatility", "macro", "sentiment"]:
                r = stage1_results.get(name)
                if r:
                    yield _sse_event("signal", {
                        "name": name,
                        "context": r.get("context"),
                        "note": r.get("note", ""),
                    })
                else:
                    yield _sse_event("signal", {
                        "name": name,
                        "context": mech_signals[name],
                        "note": "Fallback auf mechanisches Signal",
                    })

            # 4b. Load lessons from resolved theses
            lessons = list(db.theses.find(
                {"status": "resolved", "lessons_learned": {"$ne": None}},
                {"statement": 1, "lessons_learned": 1},
            ))

            # 5. Stage 2: Synthese (streamed)
            yield _sse_event("status", "Stage 2: Synthese...")
            synthesis_user = build_synthesis_prompt(
                market, mech_signals, mech_score, stage1_results,
                history, theses, researches, news_results, lessons,
            )
            yield _sse_event("prompt", {"system": SYNTHESIS_PROMPT, "user": synthesis_user})

            llm_chunks = []
            for chunk in stream_llm(
                SYNTHESIS_PROMPT,
                [{"role": "user", "content": synthesis_user}],
                max_tokens=4096,
            ):
                llm_chunks.append(chunk)
                yield _sse_event("chunk", chunk)

            synthesis_text = "".join(llm_chunks)

            # 6. Parse JSON
            yield _sse_event("status", "Parse JSON...")
            try:
                stage2_result = extract_json(synthesis_text)
            except (json.JSONDecodeError, ValueError) as e:
                yield _sse_event("status", f"JSON-Parsing fehlgeschlagen: {e} \u2014 Retry...")
                retry_prompt = (
                    f"{synthesis_user}\n\n"
                    f"WICHTIG: Dein vorheriger Versuch war kein g\u00fcltiges JSON. "
                    f"Fehler: {e}\n"
                    f"Antworte NUR mit dem JSON-Objekt."
                )
                retry_text = call_llm(
                    SYNTHESIS_PROMPT,
                    [{"role": "user", "content": retry_prompt}],
                    max_tokens=4096,
                )
                stage2_result = extract_json(retry_text)
                synthesis_text = retry_text

            # 7. Merge & validate
            analysis = merge_multistage_analysis(
                date_str, market, mech_signals, mech_score, stage1_results, stage2_result,
            )

            from argus import validate_analysis
            errors = validate_analysis(analysis)
            if errors:
                yield _sse_event("status", f"Validierungsfehler: {', '.join(errors)} \u2014 Retry...")
                retry_prompt = (
                    f"{synthesis_user}\n\n"
                    f"WICHTIG: Validierungsfehler:\n"
                    + "\n".join(f"- {e}" for e in errors)
                    + "\nBitte korrigiere diese Fehler im JSON."
                )
                retry_text = call_llm(
                    SYNTHESIS_PROMPT,
                    [{"role": "user", "content": retry_prompt}],
                    max_tokens=4096,
                )
                stage2_result = extract_json(retry_text)
                analysis = merge_multistage_analysis(
                    date_str, market, mech_signals, mech_score, stage1_results, stage2_result,
                )
                errors = validate_analysis(analysis)
                if errors:
                    yield _sse_event("error", f"Validierung nach Retry fehlgeschlagen: {', '.join(errors)}")
                    return

            # 8. Save
            analysis["llm_output"] = synthesis_text
            analysis["stage1_outputs"] = {
                name: json.dumps(r, ensure_ascii=False) if r else None
                for name, r in stage1_results.items()
            }
            yield _sse_event("status", "Speichere Analyse...")
            from argus import save_analysis
            save_analysis(db, analysis)

            yield _sse_event("done", {
                "rating": analysis["rating"]["overall"],
                "score": analysis["rating"]["mechanical_score"],
                "action": analysis["recommendation"]["action"],
            })

        except Exception as e:
            log.error("Ampel-Run fehlgeschlagen: %s", e, exc_info=True)
            yield _sse_event("error", str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/latest")
def get_latest():
    db = get_db()
    doc = db.analyses.find_one(sort=[("date", -1)])
    return JSONResponse(content=_serialize_doc(doc))


@router.get("/history")
def get_history(limit: int = 10):
    db = get_db()
    cursor = db.analyses.find(sort=[("date", -1)]).limit(limit)
    return JSONResponse(content=[_serialize_doc(doc) for doc in cursor])


@router.get("/theses")
def get_theses():
    db = get_db()
    cursor = db.theses.find({"status": "open"}).sort("created_date", -1)
    return [_serialize_doc(doc) for doc in cursor]


@router.get("/theses/resolved")
def get_resolved_theses():
    """Get resolved theses for learning/review, newest first."""
    db = get_db()
    cursor = db.theses.find({"status": "resolved"}).sort("resolution_date", -1).limit(20)
    return [_serialize_doc(doc) for doc in cursor]


@router.put("/theses/{thesis_id}")
def update_thesis(thesis_id: str, req: UpdateThesisRequest):
    """Update an open thesis."""
    db = get_db()
    try:
        oid = ObjectId(thesis_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ung\u00fcltige Thesis-ID.")

    doc = db.theses.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="These nicht gefunden.")

    update = {}
    for field in ("statement", "catalyst", "catalyst_date", "expected_if_positive", "expected_if_negative", "lessons_learned"):
        val = getattr(req, field, None)
        if val is not None:
            update[field] = val

    if not update:
        raise HTTPException(status_code=400, detail="Keine \u00c4nderungen angegeben.")

    db.theses.update_one({"_id": oid}, {"$set": update})
    updated = db.theses.find_one({"_id": oid})
    return _serialize_doc(updated)


@router.post("/theses/{thesis_id}/extract-lessons")
def extract_lessons(thesis_id: str, req: ExtractLessonsRequest):
    """Extract actionable lessons from a full chat conversation about a resolved thesis."""
    db = get_db()
    try:
        oid = ObjectId(thesis_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige Thesis-ID.")

    doc = db.theses.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="These nicht gefunden.")

    # Build conversation transcript
    transcript_lines = []
    for msg in req.messages:
        role = "User" if msg.get("role") == "user" else "Tutor"
        transcript_lines.append(f"{role}: {msg.get('content', '')}")
    transcript = "\n\n".join(transcript_lines)

    system_prompt = """\
Du bist ein Experte für Investment-Lernprozesse. Du analysierst Gespräche über aufgelöste Investment-Thesen \
und extrahierst daraus konkrete, umsetzbare Regeln für zukünftige Analysen.

## DEINE AUFGABE
Lies das gesamte Gespräch und extrahiere die KERNERKENNTNISSE als klare Regeln.

## FORMAT
- Formuliere jede Erkenntnis als konkrete Handlungsregel (z.B. "Bei SMA50-Bruch sofort prüfen ob...")
- Maximal 3-5 Regeln, nur die wichtigsten
- Jede Regel auf 1-2 Sätze
- Formuliere so, dass ein LLM die Regeln direkt in einer Analyse anwenden kann
- Trenne die Regeln mit Zeilenumbrüchen
- KEIN Markdown, keine Nummerierung, keine Überschriften — nur die reinen Regeln"""

    user_msg = f"""## AUFGELÖSTE THESE
Statement: {doc.get('statement', '')}
Resolution: {doc.get('resolution', '')}

## GESAMTES GESPRÄCH
{transcript}

Extrahiere die wichtigsten Erkenntnisse als klare Regeln:"""

    from ..llm import call_llm
    lessons = call_llm(system_prompt, [{"role": "user", "content": user_msg}], max_tokens=1024)

    # Save to DB
    db.theses.update_one({"_id": oid}, {"$set": {"lessons_learned": lessons.strip()}})
    updated = db.theses.find_one({"_id": oid})
    return _serialize_doc(updated)


def _build_news_context_for_thesis(db) -> str:
    """Build news context string for thesis refinement."""
    results = []
    seen_topics = set()
    for nr in db.news_results.find(
        {}, {"raw_headlines": 0, "_id": 0}
    ).sort("date", -1):
        topic = nr.get("topic", "")
        if topic not in seen_topics:
            seen_topics.add(topic)
            results.append(nr)
    if not results:
        return ""
    lines = build_news_context(results)
    return "\n".join(lines)


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
        news_ctx = _build_news_context_for_thesis(db)
        if news_ctx:
            parts.append(news_ctx)

        parts.append("\n## Gespr\u00e4chsverlauf")
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

        # Parse JSON from response
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
