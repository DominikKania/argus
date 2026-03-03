#!/usr/bin/env python3
"""Vollautomatische Ampel-Analyse: Mehrstufige Pipeline mit parallelen Signal-Analysten."""

import io
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from ampel_data import fetch_all_market_data, calculate_mechanical_signals
from backend.prompt_builder import (
    build_trend_analyst_prompt,
    build_volatility_analyst_prompt,
    build_macro_analyst_prompt,
    build_sentiment_analyst_prompt,
    build_synthesis_prompt,
)

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

log = logging.getLogger("ampel")

# ── LLM-Client ───────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def get_llm_client():
    """Erstellt LLM-Client basierend auf ARGUS_LLM_* Env-Variablen."""
    provider = os.environ.get("ARGUS_LLM_PROVIDER", "anthropic")
    api_key = os.environ.get("ARGUS_LLM_API_KEY")
    base_url = os.environ.get("ARGUS_LLM_BASE_URL")
    model = os.environ.get("ARGUS_LLM_MODEL", DEFAULT_MODEL)

    if not api_key:
        raise RuntimeError(
            "ARGUS_LLM_API_KEY nicht gesetzt. Bitte als Umgebungsvariable konfigurieren."
        )

    if provider == "anthropic":
        from anthropic import Anthropic
        return "anthropic", Anthropic(api_key=api_key), model

    elif provider == "azure":
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=os.environ.get("ARGUS_LLM_API_VERSION", "2024-12-01-preview"),
        )
        return "openai", client, model

    else:  # openai, ollama, oder jeder OpenAI-kompatible Provider
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return "openai", OpenAI(**kwargs), model


# ── Stage 1: Signal-Analyst Prompts ──────────────────────────────────────

TREND_ANALYST_PROMPT = """\
Du bist der Trend-Analyst des Argus Investment-Systems.

## PORTFOLIO
iShares Core MSCI World UCITS ETF USD (Acc) — ~6.700\u20ac, 100% Allokation

## DEINE AUFGABE
Bewerte den Kontext-Layer des Trend-Signals. Das mechanische Signal basiert nur auf \
Kurs vs. SMA50. Du bewertest den breiteren Kontext.

## REGELN
- Puffer Kurs\u2194SMA50: <2% = fragil, >5% = solide
- Golden Cross (SMA50 > SMA200) = Aufw\u00e4rtstrend best\u00e4tigt
- Kurs \u00fcber SMA50 aber unter SMA200 \u2192 "Erholung im Abw\u00e4rtstrend" = gelb
- Sektor-Rotation und regionale Daten als Zusatzkontext
- Saisonalit\u00e4t ist kein Signal allein, nur Kontext

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "context": "green|yellow|red",
  "note": "1-2 S\u00e4tze Begr\u00fcndung in einfachem Deutsch, keine Fachk\u00fcrzel"
}
"""

VOLATILITY_ANALYST_PROMPT = """\
Du bist der Volatilit\u00e4ts-Analyst des Argus Investment-Systems.

## PORTFOLIO
iShares Core MSCI World UCITS ETF USD (Acc) — ~6.700\u20ac, 100% Allokation

## DEINE AUFGABE
Bewerte den Kontext-Layer des Volatilit\u00e4ts-Signals.

## REGELN
- VIX <13 allein ist KEIN automatisches Rot
- Pr\u00fcfe ob VIX f\u00fcr "underpriced" gehalten wird (versteckte Risiken bei niedrigem VIX)
- VIX-Richtung beachten: steigend von niedrigem Niveau = fr\u00fche Warnung
- Put/Call Ratio als Kontr\u00e4r-Indikator: >1.2 = hohe Angst, <0.7 = hohe Gier

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "context": "green|yellow|red",
  "note": "1-2 S\u00e4tze in einfachem Deutsch, keine Fachk\u00fcrzel"
}
"""

MACRO_ANALYST_PROMPT = """\
Du bist der Makro-Analyst des Argus Investment-Systems.

## PORTFOLIO
iShares Core MSCI World UCITS ETF USD (Acc) — ~6.700\u20ac, 100% Allokation

## DEINE AUFGABE
Bewerte den Kontext-Layer des Makro-Signals.

## REGELN
- Spread-Richtung wichtiger als Snapshot: Wird er enger oder weiter?
- Real Yield >2.5% = restriktiv f\u00fcr Aktien
- CPI-Trend: steigend/fallend/stagnierend
- Credit Spread Widening >2pp = fr\u00fches Warnsignal f\u00fcr Marktschw\u00e4che
- Credit Spreads sind Fr\u00fchindikator \u2014 sie weiten sich VOR Aktienmarktkorrekturen
- Earnings Health st\u00fctzt oder schw\u00e4cht die Makro-Einsch\u00e4tzung
- EUR/USD: USD-St\u00e4rke = oft Risk-Off; starke Aufwertung >3% in 1M belastet EM und Multis
- \u00d6l und Gold als Inflations-/Risiko-Indikatoren

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "context": "green|yellow|red",
  "note": "1-2 S\u00e4tze in einfachem Deutsch, keine Fachk\u00fcrzel"
}
"""

SENTIMENT_ANALYST_PROMPT = """\
Du bist der Sentiment-Analyst des Argus Investment-Systems.

## PORTFOLIO
iShares Core MSCI World UCITS ETF USD (Acc) — ~6.700\u20ac, 100% Allokation
IWDA hat ~70% US-Gewichtung \u2014 US-Schw\u00e4che trifft st\u00e4rker als Europa-Schw\u00e4che.

## DEINE AUFGABE
1. Bestimme das mechanische Sentiment-Signal (green/yellow/red)
2. Bewerte den Kontext-Layer
3. Identifiziere die 3 wichtigsten Events der letzten 48h die das Portfolio betreffen

## REGELN
- Kaskadenrisiko bewerten: Kann ein Event \u00fcber den direkten Effekt hinaus eskalieren?
- Put/Call Ratio als Kontr\u00e4r-Indikator einbeziehen
- Sektor-Rotation: Risk-On vs Defensive Spread beachten
- Anstehende Mega-Cap Earnings = Event-Risiko (Unsicherheit vor Zahlen)
- HINWEIS: Du hast keinen Web-Zugang. Bewerte basierend auf deinem aktuellen Marktwissen \
und den bereitgestellten News-Daten.

## VERST\u00c4NDLICHKEIT
Alle Texte in einfachem Deutsch. KEINE Fachk\u00fcrzel, Paragraphen-Nummern oder \
Gesetzesbezeichnungen. Stattdessen in einfachen Worten erkl\u00e4ren.

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "mechanical": "green|yellow|red",
  "context": "green|yellow|red",
  "note": "1-2 S\u00e4tze",
  "events": [
    { "headline": "...", "summary": "...", "affects_portfolio": "direct|sector_only|indirect", "cascade_risk": "low|medium|high", "is_primary": true },
    { "headline": "...", "summary": "...", "affects_portfolio": "...", "cascade_risk": "...", "is_primary": false },
    { "headline": "...", "summary": "...", "affects_portfolio": "...", "cascade_risk": "...", "is_primary": false }
  ]
}
"""

# ── Stage 2: Synthesis Prompt ────────────────────────────────────────────

SYNTHESIS_PROMPT = """\
Du bist der Chef-Analyst des Argus Investment-Systems. Du erh\u00e4ltst die Bewertungen \
von 4 spezialisierten Signal-Analysten und erstellst eine umfassende Gesamtbewertung.

## PORTFOLIO
iShares Core MSCI World UCITS ETF USD (Acc) — ~6.700\u20ac, 100% Allokation

## DEINE AUFGABE
1. Erstelle das Overall Rating basierend auf den 4 Signal-Bewertungen
2. Formuliere eine ausf\u00fchrliche Empfehlung mit konkreten n\u00e4chsten Schritten
3. Bestimme Schl\u00fcsselmarken (Unterst\u00fctzung/Widerstand) und Risikoeinsch\u00e4tzung
4. Definiere konkrete Kauf-/Verkaufs-Trigger und Beobachtungspunkte
5. Vergleiche mit \u00e4hnlichen historischen Marktphasen
6. Erstelle optional eine These (max. 4-6 Wochen Zeithorizont!)
7. Setze Eskalations-Trigger und Crash-Regel
8. Erg\u00e4nze Markt-Kontext-Notizen

## OVERALL RATING
- GREEN: 4/4 oder 3/4 mit stabilem Kontext
- GREEN_FRAGILE: 3/4 mit Risikofaktoren (niedriger Puffer etc.)
- YELLOW: 2/4 oder gemischte Signale
- YELLOW_BEARISH: 1-2/4 mit negativem Trend
- RED: 0-1/4 mit mehreren Warnungen
- RED_CAPITULATION: 0/4 mit Panik-Indikatoren

## CRASH-REGEL
Bei VIX >35 UND Kurs >10% unter SMA200 \u2192 kein aktiver Re-Entry

## ZUS\u00c4TZLICHER KONTEXT (aus deinem Marktwissen)
Bewerte folgende Punkte f\u00fcr die market_context Notizen:
- Marktbreite (A/D-Line, New Highs/Lows): Gesund oder divergiert sie vom Index?
- ETF-Flows und Margin Debt: Erw\u00e4hne wenn bedeutsam

## VERST\u00c4NDLICHKEIT
Alle Texte in einfachem Deutsch. KEINE Fachk\u00fcrzel, Paragraphen-Nummern oder \
Gesetzesbezeichnungen. Stattdessen in einfachen Worten erkl\u00e4ren.

## TEXTTIEFE
- reasoning: 3-5 S\u00e4tze, erkl\u00e4re das Zusammenspiel der Signale
- recommendation.detail: 3-5 S\u00e4tze, konkret und handlungsorientiert
- market_context Notizen: 2-3 S\u00e4tze pro Feld, nicht nur Stichworte
- historical_comparison: Nenne eine konkrete Vergleichsphase mit Datum und was damals passierte

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "rating": {
    "overall": "GREEN|GREEN_FRAGILE|YELLOW|YELLOW_BEARISH|RED|RED_CAPITULATION",
    "reasoning": "3-5 S\u00e4tze: Zusammenspiel der Signale, warum dieses Rating"
  },
  "recommendation": {
    "action": "hold|buy|partial_sell|hedge|wait",
    "detail": "3-5 S\u00e4tze: Was genau tun, worauf achten, wann handeln"
  },
  "key_levels": {
    "support": "Wichtigste Unterst\u00fctzung mit Kurs und Begr\u00fcndung (z.B. SMA50 bei 112.65\u20ac)",
    "resistance": "Wichtigster Widerstand mit Kurs und Begr\u00fcndung",
    "pivot_note": "Was passiert bei Bruch der Unterst\u00fctzung oder des Widerstands?"
  },
  "risk_assessment": {
    "level": "low|moderate|elevated|high|extreme",
    "primary_risks": ["Risiko 1", "Risiko 2", "Risiko 3"],
    "mitigating_factors": ["Positiver Faktor 1", "Positiver Faktor 2"]
  },
  "action_triggers": {
    "buy_trigger": "Bei welchem Kurs/Bedingung nachkaufen?",
    "sell_trigger": "Bei welchem Kurs/Bedingung reduzieren?",
    "watch_items": ["Was in den n\u00e4chsten 1-2 Wochen beobachten?", "..."]
  },
  "historical_comparison": "2-3 S\u00e4tze: Vergleich mit \u00e4hnlicher Marktphase, was damals passierte, was wir daraus lernen",
  "thesis_resolutions": [
    {"id": "these-id-aus-kontext", "resolution": "EINDEUTIG eingetreten/widerlegt: Was genau ist passiert?"}
  ],
  "thesis": {
    "statement": "Klarer Satz ohne Fachk\u00fcrzel",
    "catalyst": "Was genau muss passieren?",
    "catalyst_date": "YYYY-MM-DD (max 4-6 Wochen in der Zukunft!)",
    "expected_if_positive": "Was passiert f\u00fcr mein ETF wenn die These eintritt?",
    "expected_if_negative": "Was passiert f\u00fcr mein ETF wenn die These nicht eintritt?",
    "probability_positive_pct": 60,
    "probability_reasoning": "1-2 S\u00e4tze: Warum diese Wahrscheinlichkeit? Welche Basisrate/Evidenz?"
  },
  "thesis_probability_updates": [
    {"id": "these-id-aus-kontext", "probability_positive_pct": 55, "probability_reasoning": "Kurze Begr\u00fcndung basierend auf neuen Daten"}
  ],
  "escalation_trigger": "...",
  "crash_rule_active": false,
  "market_context": {
    "sector_rotation_note": "2-3 S\u00e4tze...",
    "regional_note": "2-3 S\u00e4tze...",
    "seasonality_note": "2-3 S\u00e4tze...",
    "breadth_note": "2-3 S\u00e4tze...",
    "put_call_note": "2-3 S\u00e4tze...",
    "currency_note": "2-3 S\u00e4tze...",
    "credit_spread_note": "2-3 S\u00e4tze...",
    "earnings_note": "2-3 S\u00e4tze..."
  }
}

REGELN:
- Alle Texte auf Deutsch, verst\u00e4ndlich und ausf\u00fchrlich (nicht nur Stichworte!)
- Enum-Werte exakt wie angegeben (lowercase f\u00fcr action/level, UPPERCASE f\u00fcr overall)
- thesis darf null sein wenn keine neue These sinnvoll ist
- thesis: MAXIMALER Zeithorizont 4-6 Wochen! catalyst_date muss 2-6 Wochen in der Zukunft liegen.
- thesis: Statement, Katalysator und Szenarien m\u00fcssen ohne Vorwissen verst\u00e4ndlich sein
- thesis: Pr\u00fcfe die OFFENEN THESEN im Kontext. Erstelle NUR eine neue These wenn sie ein KOMPLETT NEUES Thema abdeckt das in KEINER bestehenden These vorkommt. Auch Kombinationen oder Zusammenfassungen bestehender Thesen sind DUPLIKATE! Wenn Nahost UND Z\u00f6lle schon als separate Thesen existieren, ist "Nahost und Z\u00f6lle entscheiden..." ein Duplikat. thesis: null ist der NORMALFALL wenn bereits offene Thesen existieren.
- thesis_resolutions: NUR auflösen wenn die These EINDEUTIG eingetreten oder widerlegt ist! Eine These die "noch läuft", "weiter gilt" oder "noch nicht entschieden" ist, wird NICHT aufgelöst. Konkreter Test: Kannst du klar sagen "Die These ist eingetreten weil X" oder "Die These ist widerlegt weil Y"? Wenn nein → NICHT auflösen. Leeres Array [] ist der Normalfall. Im Zweifel: nicht auflösen.
- thesis_probability_updates: Aktualisiere die Wahrscheinlichkeit JEDER offenen These basierend auf den aktuellen Marktdaten und Research-Erkenntnissen. Nutze historische Basisraten aus dem Research-Kontext wenn vorhanden. probability_positive_pct = Wahrscheinlichkeit dass das POSITIVE Szenario eintritt (0-100). Leeres Array [] nur wenn keine offenen Thesen existieren.
- probability_positive_pct bei neuen Thesen: IMMER setzen, basierend auf Evidenz. Nicht raten — nutze Basisraten aus Research, Marktdaten, historische Muster.
- key_levels, risk_assessment, action_triggers: IMMER ausf\u00fcllen, nie null
- historical_comparison: Nenne immer eine konkrete Vergleichsphase (Monat/Jahr)
- market_context: Jedes Feld 2-3 S\u00e4tze, nur leer lassen wenn wirklich nicht relevant
"""


# ── LLM Aufruf ──────────────────────────────────────────────────────────

def call_llm(system_prompt, user_prompt, temperature=None):
    """Ruft das konfigurierte LLM auf und gibt die Textantwort zur\u00fcck."""
    provider_type, client, model = get_llm_client()

    log.info("LLM-Aufruf: provider=%s, model=%s, temperature=%s", provider_type, model, temperature)

    extra = {}
    if temperature is not None:
        extra["temperature"] = temperature

    if provider_type == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            **extra,
        )
        return response.content[0].text

    else:  # openai-kompatibel
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **extra,
        )
        return response.choices[0].message.content


def extract_json(text):
    """Extrahiert JSON aus LLM-Antwort (mit oder ohne Markdown-Fences)."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    start = text.find("{")
    if start == -1:
        raise ValueError("Kein JSON-Objekt in LLM-Antwort gefunden")

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError("Unvollst\u00e4ndiges JSON-Objekt in LLM-Antwort")


# ── Stage 1: Signal-Analysten (parallel) ─────────────────────────────────

def call_signal_analyst(signal_name, system_prompt, user_prompt, max_retries=1):
    """Ruft einen Signal-Analysten auf mit Retry-Logik.

    Returns:
        dict mit context, note (und f\u00fcr sentiment: mechanical, events)
        None bei Fehler nach allen Retries
    """
    for attempt in range(max_retries + 1):
        try:
            llm_text = call_llm(system_prompt, user_prompt)
            result = extract_json(llm_text)
            log.info("Stage 1 %s: context=%s", signal_name, result.get("context"))
            return result
        except Exception as e:
            if attempt < max_retries:
                log.warning("Stage 1 %s Versuch %d fehlgeschlagen: %s — Retry...",
                            signal_name, attempt + 1, e)
                continue
            log.error("Stage 1 %s endg\u00fcltig fehlgeschlagen: %s — Fallback auf mechanisches Signal",
                      signal_name, e)
            return None


def run_stage1(market, mech_signals, news_results, researches=None):
    """F\u00fchrt 4 Signal-Analysten parallel aus.

    Args:
        researches: Completed researches from DB. Each analyst receives only
                    researches where its name is in ampel_targets.

    Returns:
        dict: { "trend": {...}, "volatility": {...}, "macro": {...}, "sentiment": {...} }
        Werte k\u00f6nnen None sein bei Fehlern (Fallback auf mechanisches Signal).
    """
    tasks = {
        "trend": (TREND_ANALYST_PROMPT, build_trend_analyst_prompt(market, mech_signals, researches)),
        "volatility": (VOLATILITY_ANALYST_PROMPT, build_volatility_analyst_prompt(market, mech_signals, researches)),
        "macro": (MACRO_ANALYST_PROMPT, build_macro_analyst_prompt(market, mech_signals, researches)),
        "sentiment": (SENTIMENT_ANALYST_PROMPT, build_sentiment_analyst_prompt(market, mech_signals, news_results, researches)),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(call_signal_analyst, name, sys_p, usr_p): name
            for name, (sys_p, usr_p) in tasks.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                log.error("Stage 1 %s Exception: %s", name, e)
                results[name] = None

    return results


# ── Stage 2: Synthese ────────────────────────────────────────────────────

def run_stage2(market, mech_signals, mech_score, stage1_results,
               history, theses, researches, news_results, lessons=None, max_retries=1):
    """F\u00fchrt die Synthese-Stufe aus.

    Returns:
        tuple: (result_dict, raw_llm_text)
    """
    user_prompt = build_synthesis_prompt(
        market, mech_signals, mech_score, stage1_results,
        history, theses, researches, news_results, lessons,
    )

    for attempt in range(max_retries + 1):
        try:
            llm_text = call_llm(SYNTHESIS_PROMPT, user_prompt)
            result = extract_json(llm_text)
            log.info("Stage 2 Synthese: overall=%s", result.get("rating", {}).get("overall"))
            return result, llm_text
        except Exception as e:
            if attempt < max_retries:
                log.warning("Stage 2 Synthese Versuch %d fehlgeschlagen: %s — Retry...",
                            attempt + 1, e)
                continue
            raise


# ── Hybrid-Merge (mehrstufig) ────────────────────────────────────────────

def merge_multistage_analysis(date_str, market, mech_signals, mech_score,
                               stage1_results, stage2_result):
    """Merged Stage 1 + Stage 2 Ergebnisse in das finale Analyse-Schema.

    Output-Schema ist identisch zum bisherigen merge_analysis() Output.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Signale: mechanical aus unserer Berechnung, context+note von Stage 1
    signals = {}
    for name in ["trend", "volatility", "macro", "sentiment"]:
        s1 = stage1_results.get(name) or {}
        signals[name] = {
            "mechanical": mech_signals[name] if name != "sentiment" else s1.get("mechanical", "green"),
            "context": s1.get("context", mech_signals.get(name, "green")),
            "note": s1.get("note", ""),
        }

    # Sentiment-Events von Stage 1
    sentiment_s1 = stage1_results.get("sentiment") or {}
    sentiment_events = sentiment_s1.get("events", [])

    # Rating: mechanical_score aus unserer Berechnung
    sent_mech = signals["sentiment"]["mechanical"]
    actual_score = sum(1 for n in ["trend", "volatility", "macro"] if mech_signals[n] == "green")
    if sent_mech == "green":
        actual_score += 1

    s2 = stage2_result or {}
    s2_rating = s2.get("rating", {})

    analysis = {
        "date": date_str,
        "weekday": weekdays[dt.weekday()],
        "market": market,
        "signals": signals,
        "rating": {
            "mechanical_score": actual_score,
            "overall": s2_rating.get("overall", "YELLOW").upper(),
            "reasoning": s2_rating.get("reasoning", ""),
        },
        "sentiment_events": sentiment_events,
        "recommendation": s2.get("recommendation", {"action": "hold", "detail": ""}),
        "thesis_resolutions": s2.get("thesis_resolutions", []),
        "thesis_probability_updates": s2.get("thesis_probability_updates", []),
        "thesis": s2.get("thesis"),
        "escalation_trigger": s2.get("escalation_trigger"),
        "crash_rule_active": s2.get("crash_rule_active", False),
        "market_context": s2.get("market_context"),
        "key_levels": s2.get("key_levels"),
        "risk_assessment": s2.get("risk_assessment"),
        "action_triggers": s2.get("action_triggers"),
        "historical_comparison": s2.get("historical_comparison"),
    }

    return analysis


# ── Orchestrator ─────────────────────────────────────────────────────────

def run_auto_ampel(db, date_override=None, cpi_override=None, dry_run=False):
    """F\u00fchrt die vollautomatische Ampel-Analyse durch (mehrstufige Pipeline).

    Returns:
        dict: Die gespeicherte Analyse, oder None bei Fehler/Skip.
    """
    date_str = date_override or datetime.now().strftime("%Y-%m-%d")

    # Bestehende Analyse f\u00fcr diesen Tag l\u00f6schen
    if not dry_run:
        existing = db.analyses.find_one({"date": date_str})
        if existing:
            db.analyses.delete_one({"date": date_str})
            db.theses.delete_many({"analysis_id": existing["_id"]})
            log.info("Bestehende Analyse f\u00fcr %s gel\u00f6scht.", date_str)
            print(f"Bestehende Analyse f\u00fcr {date_str} gel\u00f6scht \u2014 wird neu erstellt.")

    # 1. Marktdaten holen
    log.info("=== Auto-Ampel Start f\u00fcr %s ===", date_str)
    print(f"Hole Marktdaten f\u00fcr {date_str}...")

    market = fetch_all_market_data(db, cpi_override=cpi_override)

    # 2. Mechanische Signale berechnen
    mech_signals, mech_score = calculate_mechanical_signals(market)

    # 3. News automatisch sammeln wenn aktive Topics existieren
    active_news = db.news_topics.count_documents({"active": True})
    if active_news > 0:
        print(f"Sammle News f\u00fcr {active_news} aktive Topics...")
        try:
            from news import run_all_news_topics
            news_count = run_all_news_topics(db)
            if news_count:
                log.info("%d News-Topics aktualisiert", news_count)
        except Exception as e:
            log.warning("News-Sammlung fehlgeschlagen: %s", e)

    # 4. Kontext aus DB laden
    history = list(db.analyses.find(sort=[("date", -1)]).limit(5))
    theses = list(db.theses.find({"status": "open"}).sort("created_date", -1))
    researches = list(db.researches.find(
        {"status": "completed", "relevance_summary": {"$ne": None}},
    ))
    news_results = list(db.news_results.find(
        {"date": date_str},
        {"raw_headlines": 0},
    ))
    lessons = list(db.theses.find(
        {"status": "resolved", "lessons_learned": {"$ne": None}},
        {"statement": 1, "lessons_learned": 1},
    ))

    # 5. Stage 1: Signal-Analysten (4 parallel)
    print("Stage 1: Bewerte Signale (4 Analysten parallel)...")
    stage1_results = run_stage1(market, mech_signals, news_results, researches)

    for name in ["trend", "volatility", "macro", "sentiment"]:
        r = stage1_results.get(name)
        if r:
            print(f"  {name.capitalize()}: {r.get('context', '?')}")
        else:
            print(f"  {name.capitalize()}: Fallback auf mechanisches Signal")

    # 6. Stage 2: Synthese
    print("Stage 2: Synthese...")
    try:
        stage2_result, synthesis_text = run_stage2(
            market, mech_signals, mech_score, stage1_results,
            history, theses, researches, news_results, lessons,
        )
    except Exception as e:
        log.error("Synthese fehlgeschlagen: %s", e)
        print(f"Fehler: Synthese fehlgeschlagen. Abbruch.", file=sys.stderr)
        return None

    # 7. Merge
    analysis = merge_multistage_analysis(
        date_str, market, mech_signals, mech_score, stage1_results, stage2_result,
    )

    # 8. Validieren
    from argus import validate_analysis
    errors = validate_analysis(analysis)
    if errors:
        log.error("Validierungsfehler: %s", errors)
        print("Validierungsfehler, wiederhole Synthese...")

        # Retry: nur Stage 2 wiederholen mit Fehler-Kontext
        retry_user = build_synthesis_prompt(
            market, mech_signals, mech_score, stage1_results,
            history, theses, researches, news_results, lessons,
        )
        retry_user += (
            "\n\nWICHTIG: Die letzte Analyse hatte Validierungsfehler:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nBitte korrigiere diese Fehler im JSON."
        )
        try:
            llm_text = call_llm(SYNTHESIS_PROMPT, retry_user)
            stage2_result = extract_json(llm_text)
            analysis = merge_multistage_analysis(
                date_str, market, mech_signals, mech_score, stage1_results, stage2_result,
            )
            errors = validate_analysis(analysis)
            if errors:
                log.error("Retry-Validierung fehlgeschlagen: %s", errors)
                print("Validierungsfehler nach Retry:", file=sys.stderr)
                for e in errors:
                    print(f"  - {e}", file=sys.stderr)
                return None
        except (json.JSONDecodeError, ValueError) as e:
            log.error("Retry fehlgeschlagen: %s", e)
            print(f"Fehler: Retry fehlgeschlagen. Abbruch.", file=sys.stderr)
            return None

    # Rohe LLM-Outputs persistieren
    analysis["llm_output"] = synthesis_text
    analysis["stage1_outputs"] = {
        name: json.dumps(r, ensure_ascii=False) if r else None
        for name, r in stage1_results.items()
    }

    # 9. Speichern oder Dry-Run
    if dry_run:
        print("\n--- DRY RUN (nicht gespeichert) ---")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return analysis

    from argus import save_analysis
    save_analysis(db, analysis)

    log.info("=== Auto-Ampel abgeschlossen: %s \u2192 %s ===", date_str, analysis["rating"]["overall"])
    return analysis


# ── Logging Setup ────────────────────────────────────────────────────────

def setup_logging():
    """Konfiguriert Logging f\u00fcr den Auto-Ampel-Lauf."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ampel_auto.log")

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    root_logger = logging.getLogger("ampel")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root_logger.addHandler(console)
