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
    build_positions_context,
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
    title: Optional[str] = None
    statement: Optional[str] = None
    conditions: Optional[str] = None
    catalyst: Optional[str] = None
    catalyst_date: Optional[str] = None
    expected_if_positive: Optional[str] = None
    expected_if_negative: Optional[str] = None
    entry_level: Optional[str] = None
    target_level: Optional[str] = None
    stop_loss: Optional[str] = None
    lessons_learned: Optional[str] = None


class CreatePositionRequest(BaseModel):
    ticker: str = "IWDA.AS"
    entry_price: float
    entry_date: str
    quantity: Optional[float] = None
    thesis_id: Optional[str] = None
    notes: Optional[str] = None


class ClosePositionRequest(BaseModel):
    exit_price: float
    exit_date: str
    notes: Optional[str] = None


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
  - "title": 3-5 Wörter knackige Überschrift (z.B. "Tech-Earnings als Wendepunkt")
  - "statement": Die Kernaussage der These
  - "conditions": Passive Rahmenbedingungen die gelten müssen (z.B. "VIX < 22 (normale Volatilität)"). KEIN Trigger!
  - "catalyst": Der EINE auslösende Trigger — ein konkretes EREIGNIS (z.B. "Starke NVIDIA-Earnings"). KEIN Nicht-Ereignis ("keine Eskalation")!
  - "catalyst_date": Datum im Format YYYY-MM-DD — max. 4-6 Wochen in der Zukunft!
  - "expected_if_positive": +X% weil... (konkretes Kursziel in EUR für IWDA)
  - "expected_if_negative": -X% weil... (konkretes Abwärtsrisiko in EUR für IWDA)
  - "entry_level": Konkretes Einstiegsniveau in EUR (z.B. "Bei IWDA unter 112€")
  - "target_level": Konkretes Kursziel in EUR (z.B. "IWDA 118€ = +5%")
  - "stop_loss": Konkretes Ausstiegsniveau bei Verlust (z.B. "Wochenschluss unter 111€")
- BEDINGUNGEN ≠ KATALYSATOREN! conditions = passive Zustände, catalyst = aktives Ereignis
- VIX-Schwellen IMMER begründen (z.B. "VIX < 20 = historisch normal, > 26 = oberes Quartil")
- Expected Value BERECHNEN: EV = (Prob × Upside) + ((1-Prob) × Downside)
- ENTRY_LEVEL IST DIE BERECHNUNGSBASIS! Alle %-Angaben (Upside, Downside, EV) werden AB entry_level gerechnet. Bei anderem Kaufkurs wird die Rechnung ungültig.
- STOP-LOSS vs. NEGATIVES SZENARIO: Der stop_loss BEGRENZT den maximalen Verlust. expected_if_negative MUSS den Stop-Loss als Untergrenze verwenden. EV-Berechnung verwendet Downside ab Stop-Loss, nicht ein tieferes Kursziel.
- WICHTIG: Zeithorizont max. 4-6 Wochen! RECHNE die Tage aus: Von heute bis catalyst_date = X Tage. Muss 14-42 Tage sein.
- Alle Daten müssen im aktuellen Jahr ({year}) oder später liegen!"""


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
    if "thesis_id" in doc and doc["thesis_id"] is not None:
        doc["thesis_id"] = str(doc["thesis_id"])
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
    positions = list(db.positions.find({"status": "open"}))

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
                    history, theses, researches, news_results, lessons, positions,
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
            positions = list(db.positions.find({"status": "open"}))

            # 5. Stage 2: Synthese (streamed)
            yield _sse_event("status", "Stage 2: Synthese...")
            synthesis_user = build_synthesis_prompt(
                market, mech_signals, mech_score, stage1_results,
                history, theses, researches, news_results, lessons, positions,
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


# ── Positions ────────────────────────────────────────────────────────────

@router.get("/positions")
def get_positions(status: str = "open"):
    """Get portfolio positions, optionally filtered by status."""
    db = get_db()
    query = {"status": status} if status != "all" else {}
    cursor = db.positions.find(query).sort("entry_date", -1)
    return [_serialize_doc(doc) for doc in cursor]


@router.post("/positions")
def create_position(req: CreatePositionRequest):
    """Open a new portfolio position."""
    db = get_db()
    doc = {
        "ticker": req.ticker,
        "entry_price": req.entry_price,
        "entry_date": req.entry_date,
        "quantity": req.quantity,
        "thesis_id": ObjectId(req.thesis_id) if req.thesis_id else None,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "notes": req.notes or "",
    }
    result = db.positions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_doc(doc)


@router.put("/positions/{position_id}/close")
def close_position(position_id: str, req: ClosePositionRequest):
    """Close an open position with exit price and date."""
    db = get_db()
    try:
        oid = ObjectId(position_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige Position-ID.")

    doc = db.positions.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    if doc["status"] == "closed":
        raise HTTPException(status_code=400, detail="Position ist bereits geschlossen.")

    update = {
        "status": "closed",
        "exit_price": req.exit_price,
        "exit_date": req.exit_date,
    }
    if req.notes:
        update["notes"] = req.notes

    db.positions.update_one({"_id": oid}, {"$set": update})
    updated = db.positions.find_one({"_id": oid})
    return _serialize_doc(updated)


@router.post("/embeddings/reindex")
def reindex_embeddings():
    """Reindex all existing data into ChromaDB for semantic search."""
    try:
        from backend.embeddings import reindex_all
        db = get_db()
        counts = reindex_all(db)
        return {"status": "ok", "counts": counts}
    except Exception as e:
        log.error("Reindex fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=f"Reindex fehlgeschlagen: {e}")


@router.get("/embeddings/search")
def search_embeddings(q: str, collection: str = "theses", n: int = 5):
    """Semantic search across ChromaDB collections."""
    try:
        from backend.embeddings import (
            find_similar_theses, find_similar_analyses,
            find_relevant_lessons, find_similar_news,
            find_similar_research,
        )
        search_fn = {
            "theses": find_similar_theses,
            "analyses": find_similar_analyses,
            "lessons": find_relevant_lessons,
            "news": find_similar_news,
            "research": find_similar_research,
        }.get(collection)
        if not search_fn:
            raise HTTPException(status_code=400, detail=f"Unbekannte Collection: {collection}")
        return search_fn(q, n=n)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/search-all")
def search_all_embeddings(q: str, n: int = 3):
    """Semantic search across ALL ChromaDB collections at once."""
    try:
        from backend.embeddings import (
            find_similar_theses, find_similar_analyses,
            find_relevant_lessons, find_similar_news,
            find_similar_research,
        )
        results = {}
        for name, fn in [
            ("theses", find_similar_theses),
            ("analyses", find_similar_analyses),
            ("lessons", find_relevant_lessons),
            ("news", find_similar_news),
            ("research", find_similar_research),
        ]:
            try:
                results[name] = fn(q, n=n)
            except Exception:
                results[name] = []
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


KNOWLEDGE_SYSTEM_PROMPT = """\
Du bist der Argus Wissensassistent. Der Benutzer stellt eine Frage zu seinem Investment-Portfolio \
(MSCI World ETF, IWDA). Du beantwortest die Frage basierend auf ALLEN bereitgestellten Daten aus \
dem Argus-System.

## HEUTIGES DATUM
{today}

## REGELN
- Beantworte die Frage DIREKT und KONKRET in 2-4 Absätzen
- Begründe deine Antwort mit konkreten Zahlen und Daten aus dem Kontext
- Beziehe ALLE relevanten Datenquellen ein: Analyse, Research-Studien, News, Thesen, Kursdaten, Positionen
- Nenne die Datenquelle wenn du dich darauf beziehst (z.B. "Laut Research 'Trump-Politik'...", "Die Analyse vom 05.03. zeigt...", "Die News berichten...")
- Verknüpfe Erkenntnisse aus verschiedenen Quellen miteinander — das ist der Hauptwert dieser Funktion
- Sei ehrlich wenn die Daten keine klare Antwort hergeben
- Antworte auf Deutsch
- Du gibst KEINE Anlageberatung, sondern ordnest die Daten ein und erklärst Zusammenhänge

## ALLE VERFÜGBAREN DATEN
{context}"""


class KnowledgeRequest(BaseModel):
    question: str


def _build_knowledge_context(db, question: str) -> tuple[str, dict]:
    """Build FULL context from all data sources + semantic search.

    Returns (context_text, semantic_sources).
    """
    parts = []

    # ── 1. Aktuelle Analyse (Signale, Rating, Empfehlung) ──────────────
    analysis = db.analyses.find_one(sort=[("date", -1)])
    if analysis:
        rat = analysis.get("rating", {})
        rec = analysis.get("recommendation", {})
        sig = analysis.get("signals", {})
        parts.append("## AKTUELLE ANALYSE ({})".format(analysis.get("date", "?")))
        parts.append("Rating: {} (Score {}/4)".format(rat.get("overall", "?"), rat.get("mechanical_score", "?")))
        parts.append("Begründung: {}".format(rat.get("reasoning", "?")))
        parts.append("Empfehlung: {} — {}".format(rec.get("action", "?"), rec.get("detail", "?")))

        for name in ["trend", "volatility", "macro", "sentiment"]:
            s = sig.get(name, {})
            parts.append("- {}: mechanisch={}, kontext={}".format(name, s.get("mechanical"), s.get("context")))
            parts.append("  {}".format(s.get("note", "")))

        if analysis.get("escalation_trigger"):
            parts.append("Escalation Trigger: {}".format(analysis["escalation_trigger"]))
        if analysis.get("historical_comparison"):
            parts.append("\nHistorischer Vergleich: {}".format(analysis["historical_comparison"]))

        # ── Marktdaten aus Analyse ──
        m = analysis.get("market", {})
        if m:
            parts.append("\n## MARKTDATEN")
            parts.append("IWDA Kurs: {:.2f}€ | SMA50: {:.2f}€ | SMA200: {:.2f}€".format(
                m.get("price", 0), m.get("sma50", 0), m.get("sma200", 0)))
            parts.append("Puffer SMA50: {:.1f}% | ATH-Delta: {:.1f}% | Golden Cross: {}".format(
                m.get("puffer_sma50_pct", 0), m.get("delta_ath_pct", 0), m.get("golden_cross", "?")))

            vix = m.get("vix", {})
            if vix:
                parts.append("VIX: {:.1f} ({}) | Vorwoche: {:.1f}".format(
                    vix.get("value", 0), vix.get("direction", "?"), vix.get("prev_week", 0)))

            yields = m.get("yields", {})
            if yields:
                parts.append("US10Y: {:.2f}% | US2Y: {:.2f}% | Spread: {:.2f}% | Real Yield: {:.2f}%".format(
                    yields.get("us10y", 0), yields.get("us2y", 0),
                    yields.get("spread", 0), yields.get("real_yield", 0)))

            cs = m.get("credit_spread", {})
            if cs:
                parts.append("Credit Spread Proxy: {:.2f}pp ({})".format(
                    cs.get("spread_proxy", 0), cs.get("direction", "?")))

            if m.get("put_call"):
                parts.append("Put/Call Ratio: {}".format(m["put_call"]))

            oil = m.get("oil", {})
            if isinstance(oil, dict) and oil.get("price"):
                parts.append("Öl: {:.2f}$ ({}, 1M: {:+.1f}%)".format(
                    oil["price"], oil.get("direction", "?"), oil.get("change_1m_pct", 0)))
            elif isinstance(oil, (int, float)):
                parts.append("Öl: {:.2f}$".format(oil))

            gold = m.get("gold", {})
            if isinstance(gold, dict) and gold.get("price"):
                parts.append("Gold: {:.2f}$ ({}, 1M: {:+.1f}%)".format(
                    gold["price"], gold.get("direction", "?"), gold.get("change_1m_pct", 0)))
            elif isinstance(gold, (int, float)):
                parts.append("Gold: {:.2f}$".format(gold))

            eurusd = m.get("eurusd", {})
            if isinstance(eurusd, dict) and eurusd.get("rate"):
                parts.append("EUR/USD: {:.4f} ({})".format(eurusd["rate"], eurusd.get("direction", "?")))

            dxy = m.get("dxy", {})
            if isinstance(dxy, dict) and dxy.get("value"):
                parts.append("DXY: {:.2f} ({})".format(dxy["value"], dxy.get("direction", "?")))

            regional = m.get("regional", {})
            if isinstance(regional, dict):
                parts.append("Regional: USA 1M {:+.2f}% | Europa 1M {:+.2f}% | USA vs EU: {:+.2f}pp".format(
                    regional.get("spy_perf_1m", 0), regional.get("ezu_perf_1m", 0),
                    regional.get("usa_vs_europe", 0)))

            season = m.get("seasonality", {})
            if isinstance(season, dict) and season.get("seasonal_bias"):
                parts.append("Saisonalität: {} (Ø Monatsrendite: {:.2f}%)".format(
                    season.get("seasonal_bias", "?"), season.get("avg_return_pct", 0)))

            # ── Earnings ──
            earn = m.get("earnings", {})
            if earn:
                parts.append("\n## EARNINGS")
                parts.append("Beat Rate: {} ({:.0f}%) | Ø Surprise: {:.1f}%".format(
                    earn.get("beat_rate", "?"), earn.get("beat_rate_pct", 0),
                    earn.get("avg_surprise_pct", 0)))
                parts.append("Fwd EPS Growth: {:.1f}% | Revisionen 7d: {} | 30d: {} ({})".format(
                    (earn.get("fwd_eps_growth_0y", 0) or 0) * 100,
                    earn.get("net_revisions_7d", "?"), earn.get("net_revisions_30d", "?"),
                    earn.get("revision_direction", "?")))
                by_sector = earn.get("by_sector", {})
                if by_sector:
                    parts.append("Nach Sektor:")
                    for sector, sd in list(by_sector.items())[:6]:
                        parts.append("  {}: Beat {}, Surprise {:.1f}%".format(
                            sector, sd.get("beat_rate", "?"), sd.get("avg_surprise_pct", 0)))

            # ── Top Holdings ──
            th = m.get("top_holdings", {})
            holdings = th.get("holdings", []) if isinstance(th, dict) else []
            if holdings:
                parts.append("\n## TOP HOLDINGS")
                above = sum(1 for h in holdings if h.get("above_sma50"))
                parts.append("{} von {} über SMA50".format(above, len(holdings)))
                for h in holdings[:10]:
                    parts.append("  {} ({}): {:.2f}$ | SMA50-Puffer: {:.1f}% | 1M: {:.1f}%".format(
                        h.get("ticker", "?"), h.get("sector", "?"),
                        h.get("price", 0), h.get("puffer_sma50_pct", 0),
                        h.get("perf_1m_pct", 0)))

            # ── Sektorrotation ──
            sr = m.get("sector_rotation", {})
            if sr:
                parts.append("\n## SEKTORROTATION")
                for sector, perf in sorted(sr.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
                    if isinstance(perf, (int, float)):
                        parts.append("  {}: {:+.2f}pp".format(sector, perf))

        # ── Markt-Kontext Notizen ──
        mctx = analysis.get("market_context", {})
        if mctx:
            ctx_notes = [(k.replace("_note", "").replace("_", " ").title(), v)
                         for k, v in mctx.items() if v]
            if ctx_notes:
                parts.append("\n## MARKT-KONTEXT")
                for label, note in ctx_notes:
                    parts.append("- {}: {}".format(label, note))

        # ── Key Levels ──
        kl = analysis.get("key_levels", {})
        if kl:
            parts.append("\n## KEY LEVELS")
            for k, v in kl.items():
                parts.append("  {}: {}".format(k, v))

        # ── Sentiment Events ──
        se = analysis.get("sentiment_events", [])
        if se:
            parts.append("\n## SENTIMENT EVENTS")
            for ev in se[:8]:
                if isinstance(ev, dict):
                    parts.append("- [{}] {} (Einfluss: {})".format(
                        ev.get("date", "?"), ev.get("event", "?"), ev.get("impact", "?")))
                else:
                    parts.append("- {}".format(ev))

    # ── 2. Research-Ergebnisse (früh im Kontext für hohe Gewichtung) ──
    researches = list(db.researches.find(
        {"status": "completed"},
        {"_id": 0, "title": 1, "relevance_summary": 1, "results": 1},
    ))
    if researches:
        parts.append("\n## RESEARCH-ERGEBNISSE ({} Studien)".format(len(researches)))
        for r in researches:
            parts.append("\n### {}".format(r.get("title", "?")))
            if r.get("relevance_summary"):
                parts.append("Kernaussage: {}".format(r["relevance_summary"]))
            # Include first meaningful chunk of results for detail
            if r.get("results"):
                # Skip markdown headers, get substance
                lines = [l.strip() for l in r["results"].split("\n") if l.strip() and not l.startswith("#")]
                substance = "\n".join(lines[:15])[:800]
                if substance:
                    parts.append("Details: {}".format(substance))

    # ── 3. Offene Positionen ──────────────────────────────────────────
    positions = list(db.positions.find({"status": "open"}, {"_id": 0}))
    if positions:
        parts.append("\n## OFFENE POSITIONEN")
        for p in positions:
            parts.append("  {} | Einstieg: {:.2f}€ am {} | Stück: {}".format(
                p.get("ticker", "?"), p.get("entry_price", 0),
                p.get("entry_date", "?"), p.get("quantity", "?")))
            if p.get("notes"):
                parts.append("  Notiz: {}".format(p["notes"]))

    # ── 3. Offene Thesen ──────────────────────────────────────────────
    theses = list(db.theses.find({"status": "open"}, {"_id": 0}))
    if theses:
        parts.append("\n## OFFENE THESEN")
        for i, t in enumerate(theses, 1):
            parts.append("\n### These {}".format(i))
            parts.append("Statement: {}".format(t.get("statement", "?")))
            if t.get("catalyst"):
                parts.append("Katalysator: {}".format(t["catalyst"]))
            if t.get("catalyst_date"):
                parts.append("Katalysator-Datum: {}".format(t["catalyst_date"]))
            if t.get("expected_if_positive"):
                parts.append("Wenn positiv: {}".format(t["expected_if_positive"]))
            if t.get("expected_if_negative"):
                parts.append("Wenn negativ: {}".format(t["expected_if_negative"]))
            if t.get("entry_level"):
                parts.append("Entry Level: {}".format(t["entry_level"]))
            if t.get("target_level"):
                parts.append("Ziel: {}".format(t["target_level"]))
            if t.get("stop_loss"):
                parts.append("Stop-Loss: {}".format(t["stop_loss"]))
            if t.get("probability"):
                parts.append("Wahrscheinlichkeit: {}%".format(t["probability"]))

    # ── 5. Kursdaten (alle Watchlist-Ticker, kompakt) ───────────────
    tickers = db.prices.distinct("ticker")
    if tickers:
        parts.append("\n## KURSDATEN")
        for ticker in tickers:
            prices = list(db.prices.find(
                {"ticker": ticker},
                {"_id": 0, "date": 1, "close": 1, "sma50": 1, "sma200": 1},
            ).sort("date", -1).limit(5))
            if prices:
                latest = prices[0]
                oldest = prices[-1]
                chg = ((latest.get("close", 0) / oldest.get("close", 1)) - 1) * 100 if oldest.get("close") else 0
                line = "{}: {:.2f}€ ({:+.1f}% 5d)".format(ticker, latest.get("close", 0), chg)
                if latest.get("sma50"):
                    puffer = ((latest["close"] / latest["sma50"]) - 1) * 100
                    line += " | SMA50: {:.2f}€ ({:+.1f}%)".format(latest["sma50"], puffer)
                parts.append(line)

    # ── 6. News ───────────────────────────────────────────────────────
    news_results = list(db.news_results.find(
        {}, {"raw_headlines": 0, "_id": 0},
    ).sort("date", -1).limit(15))
    if news_results:
        parts.append("\n## AKTUELLE NEWS")
        seen = set()
        for nr in news_results:
            topic = nr.get("topic", "")
            if topic in seen:
                continue
            seen.add(topic)
            parts.append("\n### {} ({}) — Trend: {}".format(
                topic, nr.get("date", "?"), nr.get("trend", "?")))
            if nr.get("development"):
                parts.append("Entwicklung: {}".format(nr["development"]))
            if nr.get("recurring"):
                parts.append("Bestätigt: {}".format(nr["recurring"]))
            if nr.get("summary"):
                parts.append("Einordnung: {}".format(nr["summary"]))
            if nr.get("ampel_relevance"):
                parts.append("Ampel-Relevanz: {}".format(nr["ampel_relevance"]))

    # ── 6. Semantische Suche (ergänzend) ──────────────────────────────
    sources = {}
    try:
        from backend.embeddings import (
            find_similar_theses, find_similar_analyses,
            find_relevant_lessons, find_similar_news,
            find_similar_research,
        )
        for label, name, fn, max_n, threshold in [
            ("SEMANTISCH ÄHNLICHE THESEN", "theses", find_similar_theses, 3, 0.85),
            ("SEMANTISCH ÄHNLICHE ANALYSEN", "analyses", find_similar_analyses, 3, 0.85),
            ("RELEVANTE ERKENNTNISSE", "lessons", find_relevant_lessons, 3, 0.85),
            ("SEMANTISCH ÄHNLICHE NEWS", "news", find_similar_news, 3, 0.85),
            ("RELEVANTE RESEARCH-STUDIEN", "research", find_similar_research, 5, 0.95),
        ]:
            try:
                items = fn(question, n=max_n)
                relevant = [i for i in items if i.get("distance", 1) < threshold]
                if relevant:
                    sources[name] = relevant
                    parts.append("\n## {}".format(label))
                    for item in relevant:
                        meta = item.get("metadata", {})
                        meta_str = ", ".join("{}: {}".format(k, v) for k, v in (meta or {}).items() if v)
                        if meta_str:
                            parts.append("[{}]".format(meta_str))
                        parts.append(item.get("document", "")[:400])
            except Exception:
                pass
    except Exception:
        pass

    context = "\n".join(parts) if parts else "Keine Daten verfügbar."
    return context, sources


@router.post("/knowledge/ask")
def knowledge_ask(req: KnowledgeRequest):
    """Answer a question using ALL available data + semantic search, streamed via SSE."""
    db = get_db()
    context, sources = _build_knowledge_context(db, req.question)

    system_prompt = KNOWLEDGE_SYSTEM_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        context=context,
    )
    messages = [{"role": "user", "content": req.question}]

    def generate():
        try:
            sources_event = json.dumps({"type": "sources", "data": sources}, ensure_ascii=False, default=str)
            yield f"data: {sources_event}\n\n"

            for chunk in stream_llm(system_prompt, messages):
                escaped = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {escaped}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            log.error("Knowledge ask failed: %s", e)
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/positions/{position_id}")
def delete_position(position_id: str):
    """Delete a position."""
    db = get_db()
    try:
        oid = ObjectId(position_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige Position-ID.")

    result = db.positions.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    return {"deleted": True}
