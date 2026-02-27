"""Chat API routes for the Trading AI Assistant."""

import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..llm import call_llm

log = logging.getLogger("argus")

router = APIRouter()

CHAT_SYSTEM_PROMPT = """\
Du bist ein freundlicher Trading-Tutor im Argus Investment-System. Der Benutzer ist ein \
Privatanleger mit einem MSCI World ETF (IWDA, ~6.700€). Er hat gerade seine Marktanalyse \
angesehen und möchte Dinge verstehen, die ihm unklar sind.

## DEINE ROLLE
- Erkläre Finanz- und Börsenbegriffe einfach und verständlich
- Beziehe dich auf die aktuelle Analyse-Daten wenn relevant
- Sei freundlich, geduldig, ermutigend — wie ein guter Lehrer
- Antworte auf Deutsch
- Halte Antworten kurz und prägnant (2-4 Absätze maximal), außer der Benutzer fragt nach mehr Detail
- Verwende Beispiele und Analogien um komplexe Konzepte zu erklären
- Wenn du etwas nicht weißt, sag es ehrlich

## WICHTIG
- Du gibst KEINE Anlageberatung. Du erklärst Konzepte und die Analyse.
- Wenn der Benutzer nach konkreten Kauf-/Verkaufs-Empfehlungen fragt, verweise auf die Ampel-Empfehlung.
- Du bist kein Finanzberater, sondern ein Erklärer.

## AKTUELLE ANALYSE-DATEN
{analysis_json}
"""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    response: str


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

    system_prompt = CHAT_SYSTEM_PROMPT.format(analysis_json=analysis_json)

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
