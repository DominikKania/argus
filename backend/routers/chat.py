"""Chat API routes for the Trading AI Assistant."""

import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..db import get_db
from ..llm import call_llm, stream_llm

log = logging.getLogger("argus")

router = APIRouter()

CHAT_SYSTEM_PROMPT = """\
Du bist ein freundlicher Trading-Tutor im Argus Investment-System. Der Benutzer ist ein \
Privatanleger mit einem MSCI World ETF (IWDA, ~6.700€).

## HEUTIGES DATUM
{today}

## DEINE ROLLE
- Erkläre Finanz- und Börsenbegriffe einfach und verständlich
- Beziehe dich auf die bereitgestellten Daten wenn relevant
- Sei freundlich, geduldig, ermutigend — wie ein guter Lehrer
- Antworte auf Deutsch
- Halte Antworten kurz und prägnant (2-4 Absätze maximal), außer der Benutzer fragt nach mehr Detail
- Verwende Beispiele und Analogien um komplexe Konzepte zu erklären
- Wenn du etwas nicht weißt, sag es ehrlich

## WICHTIG
- Du gibst KEINE Anlageberatung. Du erklärst Konzepte und die Analyse.
- Wenn der Benutzer nach konkreten Kauf-/Verkaufs-Empfehlungen fragt, verweise auf die Ampel-Empfehlung.
- Du bist kein Finanzberater, sondern ein Erklärer.

## AKTUELLER KONTEXT
Der Benutzer schaut sich gerade den Bereich "{view}" an.

## AKTUELLE ANALYSE-DATEN
{analysis_json}
{extra_context}"""


class ChatContext(BaseModel):
    view: str = "dashboard"
    ticker: Optional[str] = None
    prompt_review: Optional[str] = None
    prompt_topic: Optional[str] = None
    thesis_review: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    context: ChatContext = ChatContext()


class ChatResponse(BaseModel):
    response: str


def _build_semantic_context(user_message: str) -> str:
    """Build context using semantic search for the user's question."""
    parts = []
    try:
        from backend.embeddings import (
            find_similar_theses, find_similar_analyses,
            find_relevant_lessons, find_similar_news,
        )

        # Find relevant lessons
        lessons = find_relevant_lessons(user_message, n=2)
        relevant_lessons = [l for l in lessons if l.get("distance", 1) < 0.6]
        if relevant_lessons:
            parts.append("\n## RELEVANTE ERKENNTNISSE (semantisch)")
            for l in relevant_lessons:
                parts.append(f"- {l['document']}")

        # Find relevant past analyses
        analyses = find_similar_analyses(user_message, n=2)
        relevant_analyses = [a for a in analyses if a.get("distance", 1) < 0.7]
        if relevant_analyses:
            parts.append("\n## ÄHNLICHE VERGANGENE ANALYSEN (semantisch)")
            for a in relevant_analyses:
                meta = a.get("metadata", {})
                doc = a.get("document", "")[:300]
                parts.append(f"\n### {meta.get('date', '?')} — {meta.get('overall', '?')}")
                parts.append(doc)

        # Find relevant news
        news = find_similar_news(user_message, n=3)
        relevant_news = [n for n in news if n.get("distance", 1) < 0.5]
        if relevant_news:
            parts.append("\n## RELEVANTE NEWS (semantisch)")
            for n in relevant_news:
                meta = n.get("metadata", {})
                parts.append(f"- [{meta.get('date', '?')}] {n['document'][:200]}")

    except Exception:
        pass  # Graceful fallback — semantic search is optional

    return "\n".join(parts)


def _build_extra_context(db, view: str, ticker: Optional[str], user_message: str = "") -> str:
    """Build full context from all data sources, regardless of current view."""
    parts = []

    # ── Semantic context based on user question ───────────────────────
    if user_message:
        semantic = _build_semantic_context(user_message)
        if semantic:
            parts.append(semantic)

    # ── Offene Thesen (immer) ────────────────────────────────────────
    theses = list(db.theses.find({"status": "open"}, {"_id": 0}))
    if theses:
        parts.append("\n## OFFENE THESEN")
        for i, t in enumerate(theses, 1):
            parts.append(f"\n### These {i}")
            parts.append(f"Statement: {t.get('statement', '?')}")
            if t.get("catalyst"):
                parts.append(f"Katalysator: {t['catalyst']}")
            if t.get("catalyst_date"):
                parts.append(f"Katalysator-Datum: {t['catalyst_date']}")
            if t.get("expected_if_positive"):
                parts.append(f"Wenn positiv: {t['expected_if_positive']}")
            if t.get("expected_if_negative"):
                parts.append(f"Wenn negativ: {t['expected_if_negative']}")

    # ── Research-Ergebnisse (immer) ──────────────────────────────────
    researches = list(db.researches.find(
        {"status": "completed"},
        {"_id": 0, "title": 1, "relevance_summary": 1, "results": 1, "last_run_date": 1},
    ))
    if researches:
        parts.append("\n## RESEARCH-ERGEBNISSE")
        for r in researches:
            parts.append(f"\n### {r.get('title', '?')}")
            if r.get("relevance_summary"):
                parts.append(f"Relevanz: {r['relevance_summary']}")
            if r.get("results"):
                preview = r["results"][:500]
                if len(r["results"]) > 500:
                    preview += "..."
                parts.append(f"Ergebnis-Auszug: {preview}")

    # ── Kursdaten (wenn Ticker ausgewählt) ───────────────────────────
    if ticker:
        prices = list(
            db.prices.find(
                {"ticker": ticker},
                {"_id": 0, "date": 1, "close": 1, "volume": 1, "sma50": 1, "sma200": 1},
            )
            .sort("date", -1)
            .limit(30)
        )
        if prices:
            latest = prices[0]
            parts.append(f"\n## KURSDATEN: {ticker}")
            parts.append(f"Aktueller Kurs: {latest.get('close', '?')}€")
            if latest.get("sma50"):
                parts.append(f"SMA 50: {latest['sma50']:.2f}€")
            if latest.get("sma200"):
                parts.append(f"SMA 200: {latest['sma200']:.2f}€")
            parts.append(f"\nLetzte 30 Tage (Datum → Schlusskurs):")
            for p in prices[:30]:
                line = f"  {p.get('date', '?')}: {p.get('close', '?')}€"
                if p.get("sma50"):
                    line += f" (SMA50: {p['sma50']:.2f})"
                parts.append(line)

    # ── News-Daten (immer) ───────────────────────────────────────────
    news_results = list(
        db.news_results.find(
            {},
            {"raw_headlines": 0, "_id": 0},
        ).sort("date", -1).limit(10)
    )
    if news_results:
        parts.append("\n## AKTUELLE NEWS-LAGE")
        seen_topics = set()
        for nr in news_results:
            topic = nr.get("topic", "")
            if topic in seen_topics:
                continue
            seen_topics.add(topic)

            parts.append(f"\n### {topic} ({nr.get('date', '?')}) — Trend: {nr.get('trend', '?')}")
            if nr.get("development"):
                parts.append(f"Neue Entwicklung: {nr['development']}")
            if nr.get("recurring"):
                parts.append(f"Bestätigt sich: {nr['recurring']}")
            if nr.get("summary"):
                parts.append(f"Einordnung: {nr['summary']}")
            if nr.get("triggers_detected"):
                parts.append(f"Trigger: {', '.join(nr['triggers_detected'])}")
            if nr.get("ampel_relevance"):
                parts.append(f"Ampel-Relevanz: {nr['ampel_relevance']}")

    # ── Markt-Kontext aus letzter Analyse (immer) ────────────────────
    analysis = db.analyses.find_one(sort=[("date", -1)])
    if analysis:
        mctx = analysis.get("market_context")
        if mctx:
            notes = [(k.replace("_note", "").replace("_", " ").title(), v)
                     for k, v in mctx.items() if v]
            if notes:
                parts.append("\n## MARKT-KONTEXT (aus letzter Analyse)")
                for label, note in notes:
                    parts.append(f"- **{label}:** {note}")

        # ── Analyse-Ergebnisse (Signale, Rating, Empfehlung) ──────────
        sig = analysis.get("signals", {})
        rat = analysis.get("rating", {})
        rec = analysis.get("recommendation", {})
        parts.append(f"\n## AKTUELLE ANALYSE ({analysis.get('date', '?')})")
        parts.append(f"Rating: {rat.get('overall', '?')} (Score {rat.get('mechanical_score', '?')}/4)")
        parts.append(f"Begründung: {rat.get('reasoning', '?')}")
        parts.append(f"Empfehlung: {rec.get('action', '?')} — {rec.get('detail', '?')}")
        for name in ["trend", "volatility", "macro", "sentiment"]:
            s = sig.get(name, {})
            parts.append(f"- {name}: mechanical={s.get('mechanical')}, context={s.get('context')}")
            parts.append(f"  {s.get('note', '')}")
        if analysis.get("escalation_trigger"):
            parts.append(f"Escalation Trigger: {analysis['escalation_trigger']}")

    return "\n".join(parts)


@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Process a chat message with the trading tutor AI."""
    db = get_db()
    analysis = db.analyses.find_one(sort=[("date", -1)])

    if analysis:
        analysis.pop("_id", None)
        analysis.pop("simplified", None)
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
    else:
        analysis_json = "Keine Analyse vorhanden."

    view = req.context.view
    extra_context = _build_extra_context(db, view, req.context.ticker, req.message)

    # Add thesis review context if present
    if req.context.thesis_review:
        extra_context += (
            f"\n\n## THESEN-REVIEW MODUS"
            f"\nDer Benutzer bespricht gerade eine Investment-These und möchte sie verbessern."
            f"\n**These:** {req.context.thesis_review}"
            f"\n\nHilf dem Benutzer die These zu verbessern. Achte besonders auf:"
            f"\n- **Verständlichkeit:** Keine Fachkürzel (Section 122, IEEPA etc.) — alles in einfachem Deutsch"
            f"\n- **Testbarkeit:** Ist klar wann die These eingetreten oder widerlegt ist?"
            f"\n- **Konkretheit:** Sind die Szenarien greifbar?"
            f"\n- **Zeitrahmen:** Liegt das Katalysator-Datum in der Zukunft?"
        )

    # Add prompt review context if present
    if req.context.prompt_review:
        topic_name = req.context.prompt_topic or "Unbekannt"
        extra_context += (
            f"\n\n## PROMPT-REVIEW MODUS"
            f"\nDer Benutzer bespricht gerade einen Research-Prompt und möchte ihn verbessern."
            f"\n**Thema:** {topic_name}"
            f"\n**Aktueller Prompt:**\n{req.context.prompt_review}"
            f"\n\nHilf dem Benutzer den Prompt zu verbessern. Gib konkretes Feedback: "
            f"Was fehlt? Was ist zu vage? Was könnte schärfer formuliert sein? "
            f"Schlage Verbesserungen vor."
        )

    system_prompt = CHAT_SYSTEM_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        view=view,
        analysis_json=analysis_json,
        extra_context=extra_context,
    )

    messages = []
    for msg in req.history:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": req.message})

    try:
        response_text = call_llm(system_prompt, messages)
        return ChatResponse(response=response_text)
    except Exception as e:
        log.error("Chat LLM call failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="LLM-Aufruf fehlgeschlagen. Bitte versuche es erneut.",
        )


@router.post("/stream")
def chat_stream(req: ChatRequest):
    """Stream a chat response via Server-Sent Events."""
    db = get_db()
    analysis = db.analyses.find_one(sort=[("date", -1)])

    if analysis:
        analysis.pop("_id", None)
        analysis.pop("simplified", None)
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
    else:
        analysis_json = "Keine Analyse vorhanden."

    view = req.context.view
    extra_context = _build_extra_context(db, view, req.context.ticker, req.message)

    if req.context.thesis_review:
        extra_context += (
            f"\n\n## THESEN-REVIEW MODUS"
            f"\nDer Benutzer bespricht gerade eine Investment-These und möchte sie verbessern."
            f"\n**These:** {req.context.thesis_review}"
            f"\n\nHilf dem Benutzer die These zu verbessern. Achte besonders auf:"
            f"\n- **Verständlichkeit:** Keine Fachkürzel (Section 122, IEEPA etc.) — alles in einfachem Deutsch"
            f"\n- **Testbarkeit:** Ist klar wann die These eingetreten oder widerlegt ist?"
            f"\n- **Konkretheit:** Sind die Szenarien greifbar?"
            f"\n- **Zeitrahmen:** Liegt das Katalysator-Datum in der Zukunft?"
        )

    if req.context.prompt_review:
        topic_name = req.context.prompt_topic or "Unbekannt"
        extra_context += (
            f"\n\n## PROMPT-REVIEW MODUS"
            f"\nDer Benutzer bespricht gerade einen Research-Prompt und möchte ihn verbessern."
            f"\n**Thema:** {topic_name}"
            f"\n**Aktueller Prompt:**\n{req.context.prompt_review}"
            f"\n\nHilf dem Benutzer den Prompt zu verbessern. Gib konkretes Feedback: "
            f"Was fehlt? Was ist zu vage? Was könnte schärfer formuliert sein? "
            f"Schlage Verbesserungen vor."
        )

    system_prompt = CHAT_SYSTEM_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        view=view,
        analysis_json=analysis_json,
        extra_context=extra_context,
    )

    llm_messages = []
    for msg in req.history:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            llm_messages.append({"role": msg["role"], "content": msg["content"]})
    llm_messages.append({"role": "user", "content": req.message})

    def generate():
        try:
            for chunk in stream_llm(system_prompt, llm_messages):
                escaped = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {escaped}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            import traceback
            log.error("Chat stream failed: %s\n%s", e, traceback.format_exc())
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
