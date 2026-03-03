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
    """Extract the relevance summary from research markdown output.

    Captures all text after the label until the next heading or end of document.
    """
    # Try: **Relevanz-Zusammenfassung:** ... (capture until next heading or EOF)
    match = re.search(
        r"\*\*Relevanz[- ]?Zusammenfassung[:\s]*\*\*[:\s]*([\s\S]+?)(?=\n#{1,4}\s|\Z)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Try: Relevanz-Zusammenfassung: ... (without bold)
    match = re.search(
        r"(?:Relevanz|RELEVANZ)[- ]?(?:Zusammenfassung|ZUSAMMENFASSUNG)[:\s]*([\s\S]+?)(?=\n#{1,4}\s|\Z)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Fallback: First paragraph after "Executive Summary" or "Zusammenfassung" heading
    match = re.search(
        r"(?:Executive Summary|Zusammenfassung)\s*\n+([\s\S]+?)(?=\n#{1,4}\s|\n\n|\Z)",
        markdown,
        re.IGNORECASE,
    )
    if match:
        summary = match.group(1).strip()
        # Clean markdown formatting
        summary = re.sub(r"\*\*(.+?)\*\*", r"\1", summary)
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

REFINE_PROMPT_SYSTEM = """\
Du bist ein Research-Prompt-Experte im Argus Investment-System. Der Benutzer hat einen \
Research-Prompt mit einem Tutor besprochen. Basierend auf dem Gesprächsverlauf sollst du \
den Prompt optimieren.

## HEUTIGES DATUM
{today}

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## DEINE AUFGABE
- Lies den Original-Prompt und den Gesprächsverlauf
- Integriere alle Verbesserungsvorschläge, Wünsche und Feedback des Benutzers
- Erstelle eine verbesserte Version des Research-Prompts
- Behalte gute Aspekte des Originals bei, verbessere schwache Stellen
- Stelle sicher, dass der Prompt spezifisch, detailliert und gut strukturiert ist

## REGELN
- Antworte NUR mit dem verbesserten Prompt-Text
- Kein JSON, kein Markdown-Wrapper, keine Erklärungen
- Der Prompt soll auf Deutsch sein
- Beziehe immer den Portfolio-Kontext ein
- Der Prompt soll so formuliert sein, dass ein LLM damit eine fundierte Analyse erstellen kann"""

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
    direction: Optional[str] = None


class UpdateResearchRequest(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    ampel_targets: Optional[list[str]] = None


class GeneratePromptRequest(BaseModel):
    title: str
    direction: Optional[str] = None


class RefinePromptRequest(BaseModel):
    topic_title: str
    original_prompt: str
    chat_history: list[dict]


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
            user_msg = f"Erstelle einen Research-Prompt zum Thema: {req.title}"
            if req.direction:
                user_msg += f"\n\nFokus/Richtung des Users: {req.direction}"
            prompt = call_llm(
                PROMPT_HELPER_SYSTEM,
                [{"role": "user", "content": user_msg}],
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
        user_msg = f"Erstelle einen Research-Prompt zum Thema: {req.title}"
        if req.direction:
            user_msg += f"\n\nFokus/Richtung des Users: {req.direction}"
        prompt = call_llm(
            PROMPT_HELPER_SYSTEM,
            [{"role": "user", "content": user_msg}],
        )
        return {"prompt": prompt}
    except Exception as e:
        log.error("Prompt-Generierung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Prompt-Generierung fehlgeschlagen.")


@router.post("/refine-prompt")
def refine_prompt(req: RefinePromptRequest):
    """Refine a research prompt based on chat conversation."""
    try:
        # Build user message with original prompt + chat history
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
        log.error("Prompt-Verfeinerung fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail="Prompt-Verfeinerung fehlgeschlagen.")


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
    if req.ampel_targets is not None:
        valid = {"trend", "volatility", "macro", "sentiment"}
        update["ampel_targets"] = [t for t in req.ampel_targets if t in valid]

    db.researches.update_one({"_id": doc["_id"]}, {"$set": update})

    updated = db.researches.find_one({"_id": doc["_id"]})
    updated["_id"] = str(updated["_id"])
    return updated


# ── Orchestrated Research ────────────────────────────────────────────────

PLANNER_SYSTEM = """\
Du bist ein Research-Planner. Deine Aufgabe: Zerlege den Research-Prompt in einzelne, \
unabhängig analysierbare Sektionen.

## REGELN
- Antworte NUR mit einem JSON-Array von Objekten
- Jedes Objekt hat: {"title": "Sektionsname", "instruction": "Was genau analysiert werden soll"}
- Maximal 8 Sektionen, mindestens 2
- Die letzte Sektion MUSS immer "Synthese & Fazit" sein
- Kein Markdown, kein erklärenden Text — NUR das JSON-Array
- Behalte alle spezifischen Details und Fragestellungen des Original-Prompts bei

Beispiel:
[
  {"title": "Tech-Sektor Analyse", "instruction": "Analysiere die Auswirkungen auf..."},
  {"title": "Synthese & Fazit", "instruction": "Fasse alle Erkenntnisse zusammen..."}
]"""

SECTION_SYSTEM = """\
Du bist ein Deep-Research-Analyst im Argus Investment-System. Du analysierst EINEN \
spezifischen Teilaspekt einer größeren Research.

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%
Der MSCI World umfasst ~1.400 Aktien aus 23 Industrieländern, gewichtet: USA ~70%, \
Tech ~23%, Financials ~15%, Healthcare ~12%. Jede Analyse muss auf dieses spezifische \
ETF bezogen sein.

## REGELN
- Schreibe NUR über den zugewiesenen Teilaspekt
- Alle Texte auf Deutsch
- Faktenbasiert, konkret: Nenne Zahlen, Daten, Zeiträume
- JEDER Absatz muss den konkreten Impact auf den MSCI World ETF herausarbeiten
- Keine allgemeinen Abhandlungen — immer fragen: "Was bedeutet das für IWDA?"
- Quantifiziere wo möglich: Welche Sektoren (% im IWDA), welche Länder, welche Größenordnung
- Strukturiere mit Markdown (### für Unterabschnitte)
- KEIN Fazit, KEINE Zusammenfassung — das kommt separat
- HINWEIS: Du hast keinen Web-Zugang. Analysiere basierend auf deinem aktuellen Wissen."""

SYNTHESIS_SYSTEM = """\
Du bist ein Senior-Analyst im Argus Investment-System. Du erhältst die Ergebnisse \
mehrerer Teilanalysen und erstellst daraus eine Gesamtsynthese.

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%
Der MSCI World umfasst ~1.400 Aktien aus 23 Industrieländern, gewichtet: USA ~70%, \
Tech ~23%, Financials ~15%, Healthcare ~12%.

## AUSGABE-FORMAT
Erstelle die finale Synthese im Markdown-Format:

### Gesamtbewertung
Übergreifende Einschätzung für den MSCI World ETF (3-5 Sätze). Was ist der Netto-Effekt?

### IWDA-Impact nach Kanal
Für jeden relevanten Wirkungskanal (z.B. Sektoren, Regionen, Währung, Zinsen, Sentiment):
- Welcher Anteil im IWDA ist betroffen (% Gewichtung)?
- Richtung und geschätzte Größenordnung des Effekts
- Zeithorizont

### Szenarien
- **Positives Szenario:** Konkreter IWDA-Effekt (z.B. "+2-3% durch...")
- **Negatives Szenario:** Konkreter IWDA-Effekt (z.B. "-5% falls...")
- **Wahrscheinlichstes Szenario:** ...

### Beobachtungspunkte
Top 5-7 Indikatoren die der Anleger beobachten sollte — jeweils mit konkretem Schwellwert

### Fazit
Handlungsempfehlung für den IWDA-Anleger

**Relevanz-Zusammenfassung:** Ein einzelner Satz der die Kernaussage für die Ampel-Analyse \
zusammenfasst. Muss den IWDA-Impact quantifizieren.

## REGELN
- Alle Texte auf Deutsch
- Vermeide Wiederholungen aus den Teilanalysen
- Fokus auf Querverbindungen und Netto-Effekte AUF DEN IWDA
- Sei konkret mit Zahlen und Zeiträumen
- Keine allgemeinen Wirtschaftsanalysen — immer die Brücke zum IWDA schlagen"""


def _parse_sections(raw: str) -> list[dict]:
    """Parse the planner output into a list of section dicts."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        sections = json.loads(cleaned)
        if isinstance(sections, list) and all(
            isinstance(s, dict) and "title" in s and "instruction" in s
            for s in sections
        ):
            return sections
    except json.JSONDecodeError:
        pass
    # Fallback: could not parse, return empty to trigger single-call mode
    return []


def _run_orchestrated(prompt: str, market_context: str) -> str:
    """Run research by splitting into sections, analyzing each, then synthesizing."""
    # Step 1: Plan sections
    log.info("Orchestrated Research: Starte Planung...")
    plan_raw = call_llm(
        PLANNER_SYSTEM,
        [{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    sections = _parse_sections(plan_raw)

    if len(sections) < 2:
        # Fallback: single call if planner failed
        log.warning("Planner konnte Prompt nicht zerlegen — Fallback auf Single-Call.")
        result = call_llm(
            RESEARCH_SYSTEM_PROMPT,
            [{"role": "user", "content": prompt + market_context}],
            max_tokens=16384,
        )
        return result, None  # no separate synthesis in single-call mode

    log.info("Orchestrated Research: %d Sektionen geplant.", len(sections))

    # Step 2: Analyze each section (except last = synthesis)
    analysis_sections = sections[:-1]
    section_results = []

    for i, section in enumerate(analysis_sections, 1):
        log.info("Orchestrated Research: Sektion %d/%d — %s", i, len(analysis_sections), section["title"])
        user_msg = (
            f"## Gesamtthema\n{prompt}\n\n"
            f"## Deine Aufgabe: {section['title']}\n{section['instruction']}"
            f"{market_context}"
        )
        result = call_llm(
            SECTION_SYSTEM,
            [{"role": "user", "content": user_msg}],
            max_tokens=8192,
        )
        section_results.append(f"## {section['title']}\n\n{result}")

    # Step 3: Synthesize
    log.info("Orchestrated Research: Starte Synthese...")
    combined = "\n\n---\n\n".join(section_results)
    synthesis = call_llm(
        SYNTHESIS_SYSTEM,
        [{"role": "user", "content": f"## Teilanalysen\n\n{combined}\n\n{market_context}"}],
        max_tokens=4096,
    )

    # Combine all into final document
    final = f"# {sections[0].get('title', 'Research')}\n\n"
    final += combined
    final += f"\n\n---\n\n## Synthese & Fazit\n\n{synthesis}"

    return final, synthesis


@router.post("/{id_or_slug}/run")
def run_research(id_or_slug: str):
    """Execute research for a topic using orchestrated multi-step analysis."""
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

        results, synthesis = _run_orchestrated(doc["prompt"], market_context)

        relevance = _extract_relevance_summary(results)
        now = datetime.now().strftime("%Y-%m-%d")

        update_fields = {
            "status": "completed",
            "results": results,
            "synthesis": synthesis,
            "relevance_summary": relevance,
            "error_message": None,
            "updated_date": now,
            "last_run_date": now,
        }
        db.researches.update_one(
            {"_id": doc["_id"]},
            {"$set": update_fields},
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
