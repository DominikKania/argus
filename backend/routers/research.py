"""Research API routes for deep research topics."""

import json
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


def _extract_relevance_summary(markdown: str) -> Optional[str]:
    """Extract the relevance summary line from research markdown output."""
    # Try: **Relevanz-Zusammenfassung:** ...
    match = re.search(
        r"\*\*Relevanz[- ]?Zusammenfassung[:\s]*\*\*[:\s]*(.+?)(?:\n|$)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Try: Relevanz-Zusammenfassung: ...
    match = re.search(
        r"(?:Relevanz|RELEVANZ)[- ]?(?:Zusammenfassung|ZUSAMMENFASSUNG)[:\s]*(.+?)(?:\n|$)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Fallback: First sentence after "Executive Summary" or "Zusammenfassung" heading
    match = re.search(
        r"(?:Executive Summary|Zusammenfassung)\s*\n+(.+?)(?:\n|$)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        summary = match.group(1).strip()
        # Clean markdown formatting
        summary = re.sub(r"\*\*(.+?)\*\*", r"\1", summary)
        if len(summary) > 200:
            summary = summary[:197] + "..."
        return summary
    return None


def _resolve_topic(db, id_or_slug: str):
    """Resolve a topic by ObjectId or slug."""
    try:
        doc = db.researches.find_one({"_id": ObjectId(id_or_slug)})
        if doc:
            return doc
    except Exception:
        pass
    doc = db.researches.find_one({"topic": id_or_slug})
    if doc:
        return doc
    return None


# ── System Prompts ───────────────────────────────────────────────────────

PROMPT_HELPER_SYSTEM = """\
Du bist ein Research-Prompt-Experte im Argus Investment-System. Der Benutzer gibt dir ein \
Thema und du erstellst einen detaillierten Research-Prompt.

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%
Der Benutzer ist ein Privatanleger mit einem MSCI World ETF.

## DEINE AUFGABE
Erstelle einen detaillierten Research-Prompt der folgende Aspekte abdeckt:
1. Was genau soll recherchiert werden?
2. Welche Auswirkungen hat das Thema auf den MSCI World ETF?
3. Welche Szenarien sind denkbar (positiv/negativ)?
4. Welche Zeiträume sind relevant?
5. Welche Daten/Indikatoren sollten beobachtet werden?

## REGELN
- Schreibe den Prompt auf Deutsch
- Sei spezifisch und detailliert
- Beziehe immer den Portfolio-Kontext ein
- Der Prompt soll so formuliert sein, dass ein LLM damit eine fundierte Analyse erstellen kann
- Antworte NUR mit dem Prompt-Text, kein JSON, kein Markdown-Wrapper"""

RESEARCH_SYSTEM_PROMPT = """\
Du bist ein Deep-Research-Analyst im Argus Investment-System. Du führst tiefgehende Analysen \
zu spezifischen Themen durch, die das Portfolio betreffen.

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## AUSGABE-FORMAT
Erstelle eine strukturierte Analyse im Markdown-Format mit folgenden Abschnitten:

### Zusammenfassung
Kurzer Überblick (2-3 Sätze)

### Analyse
Detaillierte Analyse des Themas

### Portfolio-Auswirkungen
Konkrete Auswirkungen auf den MSCI World ETF

### Szenarien
- **Positives Szenario:** ...
- **Negatives Szenario:** ...
- **Wahrscheinlichstes Szenario:** ...

### Risiken und Chancen
Konkrete Risiken und Chancen für den Anleger

### Beobachtungspunkte
Was sollte der Anleger beobachten? Welche Indikatoren?

### Fazit
Zusammenfassende Bewertung

**Relevanz-Zusammenfassung:** Ein einzelner Satz der die Kernaussage für die Ampel-Analyse zusammenfasst.

## REGELN
- Alle Texte auf Deutsch
- Faktenbasiert und analytisch
- Beziehe immer den Portfolio-Kontext ein
- Sei konkret: Nenne Zahlen, Daten, Zeiträume wenn möglich
- HINWEIS: Du hast keinen Web-Zugang. Analysiere basierend auf deinem aktuellen Wissen."""


# ── Models ───────────────────────────────────────────────────────────────

class CreateResearchRequest(BaseModel):
    title: str
    prompt: Optional[str] = None


class UpdateResearchRequest(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None


class GeneratePromptRequest(BaseModel):
    title: str


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/")
def list_topics():
    """List all research topics."""
    db = get_db()
    docs = list(
        db.researches.find(
            {},
            {"results": 0},  # exclude large results field from list
        ).sort("updated_date", -1)
    )
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.get("/{id_or_slug}")
def get_topic(id_or_slug: str):
    """Get a research topic with full results."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Topic nicht gefunden.")
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/")
def create_topic(req: CreateResearchRequest):
    """Create a new research topic. Auto-generates prompt if not provided."""
    db = get_db()
    topic_slug = slugify(req.title)

    # Check for duplicate
    if db.researches.find_one({"topic": topic_slug}):
        raise HTTPException(status_code=409, detail=f"Topic '{topic_slug}' existiert bereits.")

    now = datetime.now().strftime("%Y-%m-%d")

    # Auto-generate prompt if not provided
    prompt = req.prompt
    status = "ready"
    if not prompt:
        try:
            prompt = call_llm(
                PROMPT_HELPER_SYSTEM,
                [{"role": "user", "content": f"Erstelle einen Research-Prompt zum Thema: {req.title}"}],
            )
            status = "ready"
        except Exception as e:
            log.error("Prompt-Generierung fehlgeschlagen: %s", e)
            prompt = ""
            status = "draft"

    doc = {
        "topic": topic_slug,
        "title": req.title,
        "prompt": prompt,
        "status": status,
        "results": None,
        "relevance_summary": None,
        "error_message": None,
        "created_date": now,
        "updated_date": now,
        "last_run_date": None,
    }

    result = db.researches.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.post("/generate-prompt")
def generate_prompt(req: GeneratePromptRequest):
    """Generate a research prompt without saving (for preview)."""
    try:
        prompt = call_llm(
            PROMPT_HELPER_SYSTEM,
            [{"role": "user", "content": f"Erstelle einen Research-Prompt zum Thema: {req.title}"}],
        )
        return {"prompt": prompt}
    except Exception as e:
        log.error("Prompt-Generierung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Prompt-Generierung fehlgeschlagen.")


@router.put("/{id_or_slug}")
def update_topic(id_or_slug: str, req: UpdateResearchRequest):
    """Update a research topic's title or prompt."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Topic nicht gefunden.")

    update = {"updated_date": datetime.now().strftime("%Y-%m-%d")}
    if req.title is not None:
        update["title"] = req.title
        update["topic"] = slugify(req.title)
    if req.prompt is not None:
        update["prompt"] = req.prompt
        if req.prompt.strip():
            update["status"] = "ready"

    db.researches.update_one({"_id": doc["_id"]}, {"$set": update})

    updated = db.researches.find_one({"_id": doc["_id"]})
    updated["_id"] = str(updated["_id"])
    return updated


@router.post("/{id_or_slug}/run")
def run_research(id_or_slug: str):
    """Execute research for a topic."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Topic nicht gefunden.")

    if not doc.get("prompt", "").strip():
        raise HTTPException(status_code=400, detail="Kein Prompt definiert. Bitte zuerst einen Prompt erstellen.")

    # Mark as running
    db.researches.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "running", "error_message": None}},
    )

    try:
        # Load current analysis as market context
        analysis = db.analyses.find_one(sort=[("date", -1)])
        market_context = ""
        if analysis:
            analysis.pop("_id", None)
            analysis.pop("simplified", None)
            market_context = (
                "\n\n## AKTUELLER MARKTKONTEXT\n"
                + json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
            )

        user_content = doc["prompt"] + market_context

        results = call_llm(
            RESEARCH_SYSTEM_PROMPT,
            [{"role": "user", "content": user_content}],
        )

        relevance = _extract_relevance_summary(results)
        now = datetime.now().strftime("%Y-%m-%d")

        db.researches.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "status": "completed",
                "results": results,
                "relevance_summary": relevance,
                "error_message": None,
                "updated_date": now,
                "last_run_date": now,
            }},
        )

        updated = db.researches.find_one({"_id": doc["_id"]})
        updated["_id"] = str(updated["_id"])
        return updated

    except Exception as e:
        log.error("Research-Ausführung fehlgeschlagen für '%s': %s", doc["topic"], e)
        db.researches.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "status": "error",
                "error_message": str(e),
                "updated_date": datetime.now().strftime("%Y-%m-%d"),
            }},
        )
        raise HTTPException(status_code=500, detail=f"Research fehlgeschlagen: {e}")


@router.delete("/{id_or_slug}")
def delete_topic(id_or_slug: str):
    """Delete a research topic."""
    db = get_db()
    doc = _resolve_topic(db, id_or_slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Topic nicht gefunden.")

    db.researches.delete_one({"_id": doc["_id"]})
    return {"deleted": True, "topic": doc["topic"]}
