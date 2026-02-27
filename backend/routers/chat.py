"""Chat API routes for the Trading AI Assistant."""

import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..llm import call_llm

log = logging.getLogger("argus")

router = APIRouter()

CHAT_SYSTEM_PROMPT = """\
Du bist ein freundlicher Trading-Tutor im Argus Investment-System. Der Benutzer ist ein \
Privatanleger mit einem MSCI World ETF (IWDA, ~6.700€).

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


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    context: ChatContext = ChatContext()


class ChatResponse(BaseModel):
    response: str


def _build_extra_context(db, view: str, ticker: Optional[str]) -> str:
    """Build additional context data based on the current view."""
    parts = []

    if view == "kurse" and ticker:
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

    if view == "thesen":
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

    if view == "research":
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
                    # Include first 500 chars of results for context
                    preview = r["results"][:500]
                    if len(r["results"]) > 500:
                        preview += "..."
                    parts.append(f"Ergebnis-Auszug: {preview}")

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
    extra_context = _build_extra_context(db, view, req.context.ticker)

    system_prompt = CHAT_SYSTEM_PROMPT.format(
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
