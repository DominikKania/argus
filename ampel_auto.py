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

## HOLDINGS-DIVERGENZ REGELN
- Wenn ETF nahe SMA50 (Puffer < 2%) aber Holdings \u00d8 Puffer < -3%:
  \u2192 "Kompensierte Schw\u00e4che" = gelb, auch wenn mechanisch gr\u00fcn
  \u2192 Der ETF h\u00e4lt sich nur durch Sektorrotation, nicht durch St\u00e4rke der Kernpositionen
- Wenn Divergenz (ETF minus Holdings Puffer) > 5pp:
  \u2192 Warnung: Kompensation durch defensive Sektoren ist aktiv aber nicht nachhaltig
- Wenn Tech-Holdings \u00d8 Puffer < -5%:
  \u2192 "Kein Rally-Treibstoff" \u2014 f\u00fcr ein neues ATH m\u00fcssen die Tech-Schwergewichte \u00fcber SMA50 zur\u00fcckkehren
  \u2192 Ein ETF-Kurs nahe SMA50 ist in diesem Fall KEIN Kaufsignal
- IWDA ist breit genug um Sektor-Crashs zu absorbieren, aber nicht breit genug um ohne Tech ein neues Hoch zu erreichen (Tech = 22%+ Gewicht)

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "context": "green|yellow|red",
  "note": "1-2 S\u00e4tze Begr\u00fcndung in einfachem Deutsch, keine Fachk\u00fcrzel"
}
"""

VOLATILITY_ANALYST_PROMPT = """\
Du bist der Volatilitäts-Analyst des Argus Investment-Systems.

## DEINE AUFGABE
Bewerte den Kontext-Layer des Volatilitäts-Signals anhand ALLER bereitgestellten Daten.

## DATENBASIS (was du erhältst)
- VIX: Angst-Index (aktuell, Vorwoche, Richtung)
- Put/Call Ratio: Absicherungsstimmung am Optionsmarkt (SPY+QQQ+IWM aggregiert)
  - >1.5 = hohe Angst/Absicherung, <0.8 = hohe Sorglosigkeit
  - Aufschlüsselung nach ETF zeigt wo die Angst sitzt (Tech vs Small Caps)
- Technische Levels: Kurs vs SMA50/SMA200, ATH-Abstand
- Credit Spread: Stress-Indikator (Widening = Risikoaversion)
- Risikoappetit: Risk-On vs Risk-Off Sektoren

## REGELN
- VIX <13 allein ist KEIN automatisches Rot
- Prüfe ob VIX für "underpriced" gehalten wird (versteckte Risiken bei niedrigem VIX)
- VIX-Richtung beachten: steigend von niedrigem Niveau = frühe Warnung
- Mehrere Warnsignale gleichzeitig (VIX steigend + PCR hoch + Credit Spread widening) = stärker gewichten
- Widersprüche beachten: z.B. VIX niedrig aber PCR hoch = mögliche Fehlbewertung

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON. Kein Text davor oder danach.
{
  "context": "green|yellow|red",
  "note": "1-2 Sätze in einfachem Deutsch, keine Fachkürzel"
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
    "title": "3-5 Wörter: Knackige Überschrift (z.B. 'Tech-Earnings als Wendepunkt', 'Zollpause stützt Rally')",
    "statement": "Kernaussage: Was genau wird passieren? Klarer Satz ohne Fachkürzel",
    "conditions": "Welche Rahmenbedingungen müssen GELTEN damit die These relevant ist? (z.B. 'VIX bleibt unter 22 (= normale Volatilität, oberes Quartil wäre >26)', 'Keine neue Nahost-Eskalation'). Das sind PASSIVE Zustände, keine Trigger!",
    "catalyst": "Der EINE auslösende Trigger — ein konkretes EREIGNIS das eintritt und Kursbewegung erzeugt (z.B. 'Starke NVIDIA-Earnings am 28. Mai', 'Fed signalisiert Zinspause am 18. Juni'). MUSS ein aktives Ereignis sein, KEIN Nicht-Ereignis!",
    "catalyst_date": "YYYY-MM-DD (max 4-6 Wochen in der Zukunft!)",
    "expected_if_positive": "+X% weil... (konkretes Kursziel, z.B. 'IWDA auf 118€ (+5%) weil Tech-Sektor 40% Gewicht hat und Earnings-Beats historisch +3-5% bringen')",
    "expected_if_negative": "-X% weil... (konkretes Abwärtsrisiko, z.B. 'IWDA auf 108€ (-4%) weil Earnings-Miss bei NVIDIA Gesamtmarkt-Sell-Off auslöst')",
    "probability_positive_pct": 60,
    "probability_reasoning": "Basisrate + Evidenz + KORREKTE EV-Rechnung. SCHRITT FÜR SCHRITT: 1) Upside = +X%, Downside = -Y% (Y ist POSITIV, das Minus kommt in der Formel!). 2) EV = Prob × X + (1-Prob) × (-Y). Beispiel: Prob=55%, Up=+4%, Down=-6% → EV = 0.55×4 + 0.45×(-6) = 2.2 - 2.7 = -0.5%. PRÜFE DEINE RECHNUNG! Bei negativem EV: Begründe warum der Trade trotzdem sinnvoll ist oder setze thesis auf null.",
    "entry_level": "Konkretes Einstiegsniveau in EUR (z.B. 'Bei IWDA unter 112€'). WICHTIG: Upside ab Einstieg muss > Downside ab Einstieg sein, sonst ist das CRV ungünstig!",
    "target_level": "Konkretes Kursziel in EUR (z.B. 'IWDA 118€ = +5% in 4 Wochen')",
    "stop_loss": "Konkretes Ausstiegsniveau bei Verlust in EUR (z.B. 'Wochenschluss unter 111€'). IMMER definieren!"
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
- thesis: Wenn KEINE offenen Thesen existieren, MUSS eine neue These erstellt werden (thesis darf dann NICHT null sein!). Wenn bereits offene Thesen existieren, ist null der Normalfall — erstelle nur dann eine neue These wenn sie ein KOMPLETT NEUES Thema abdeckt.
- thesis: MAXIMALER Zeithorizont 4-6 Wochen! catalyst_date muss 2-6 Wochen in der Zukunft liegen.
- thesis: Statement, Katalysator und Szenarien müssen ohne Vorwissen verständlich sein
- thesis: DUPLIKAT-PRÜFUNG — STRENG! Vor dem Erstellen einer neuen These: Vergleiche mit JEDER offenen These. Wenn eine bestehende These das GLEICHE Kursziel (±2€), den GLEICHEN Stop-Loss (±2€) oder den GLEICHEN Katalysator-Typ hat → DUPLIKAT → thesis = null. Auch Umformulierungen sind Duplikate! "Defensive Stabilität trotz Geopolitik" = "Geopolitik und SMA50-Krieg" wenn beide auf 118€ Ziel und 111,5€ Stop setzen. Erstelle NUR eine neue These wenn sie einen KOMPLETT ANDEREN Trade beschreibt (anderes Kursziel, anderer Zeithorizont, anderer Sektor).
- thesis: BEDINGUNGEN ≠ KATALYSATOREN! `conditions` = passive Rahmenbedingungen die gelten müssen (VIX-Level, geopolitische Lage, Marktstimmung). `catalyst` = ein aktives EREIGNIS das eintritt (Earnings-Report, Fed-Meeting, Handelsabkommen). Ein Nicht-Ereignis ("keine neuen Zölle", "keine Eskalation") ist IMMER eine Bedingung, NIE ein Katalysator!
- thesis: VIX-SCHWELLEN BEGRÜNDEN! Bei jeder VIX-Referenz erklären warum dieser Wert: z.B. "VIX < 20 = historisch normale Volatilität", "VIX > 26 = oberes Quartil der letzten 2 Jahre", "VIX > 35 = Panik-Niveau".
- thesis: EXPECTED VALUE — KORREKT BERECHNEN! Schritt für Schritt: Upside = +X%, Downside = -Y%. EV = Prob × X + (1-Prob) × (-Y). ACHTUNG: Downside ist NEGATIV in der Formel! Beispiel: 55% Prob, +4% Up, -6% Down → 0.55×4 + 0.45×(-6) = 2.2 - 2.7 = -0.5%. PRÜFE DEINE RECHNUNG NOCHMAL! Bei negativem EV: explizit begründen warum der Trade trotzdem sinnvoll ist (Absicherung, Optionalität) oder thesis null setzen.
- thesis: KONKRETE EUR-KURSE für IWDA bei entry_level, target_level UND stop_loss. Nicht "bei einem Rücksetzer" sondern "bei IWDA unter 112€". stop_loss IMMER definieren!
- thesis: CRV PRÜFEN! Die Upside ab entry_level zum target_level muss GRÖSSER sein als die Downside ab entry_level zum stop_loss. Wenn der Einstieg nahe am Ziel liegt aber weit vom Stop entfernt, ist das CRV ungünstig → entry_level anpassen oder These verwerfen.
- thesis: ENTRY_LEVEL IST DIE BERECHNUNGSBASIS! Alle Prozentangaben (Upside, Downside, EV) werden AB ENTRY_LEVEL gerechnet. target_level und stop_loss sind Abstände vom Einstieg. Wenn entry=113,50€, target=118€, stop=111,50€ → Upside = +3,96%, Downside = −1,76%. Bei einem ANDEREN Kaufkurs (z.B. 115€) verschiebt sich alles: Stop wäre −3,0%, Ziel nur +2,6% — die ganze Rechnung wird ungültig. Deshalb: entry_level ist KEINE Nebensache, sondern die Grundlage der These.
- thesis: STOP-LOSS vs. NEGATIVES SZENARIO! Der stop_loss BEGRENZT den maximalen Verlust. Deshalb MUSS expected_if_negative den Stop-Loss als Untergrenze verwenden, NICHT ein tieferes Kursziel. Wenn der Stop bei 111,5€ liegt, ist der maximale Verlust ~−1,76% ab Einstieg 113,50€ — NICHT −3,3% bis 110€. Die EV-Berechnung MUSS die Downside ab Stop-Loss verwenden. Falsch: "Stop 111,5€ aber negatives Szenario 110€". Richtig: "Stop 111,5€, max. Verlust −1,76% ab Entry, EV rechnet mit −1,76%". Wenn du glaubst dass 110€ realistisch ist, muss der Stop dort liegen — nicht darüber.
- thesis: ZEITHORIZONT KONSISTENT — RECHNE NACH! catalyst_date muss 2-6 Wochen (14-42 Tage) ab heute liegen. RECHNE die Tage explizit aus: Von [heutiges Datum] bis [catalyst_date] = X Tage. Wenn X < 14 oder X > 42, passe catalyst_date ODER den Textzeithorizont an. Wenn du "4-6 Wochen" im Text schreibst, muss catalyst_date 28-42 Tage in der Zukunft liegen — NICHT 21 Tage. Prüfe: Heutiges Datum steht im Kontext.
- thesis: KEINE UNBEGRÜNDETEN BEHAUPTUNGEN! Begriffe wie "saisonale Unterstützung", "historisches Muster", "Basisrate" MÜSSEN konkret spezifiziert werden (z.B. "April-Effekt: S&P 500 war in 70% der Jahre seit 2000 im April positiv"). Wenn du keine konkrete Quelle/Statistik nennen kannst, lass den Punkt weg.
- thesis_resolutions: NUR auflösen wenn die These EINDEUTIG eingetreten oder widerlegt ist! Eine These die "noch läuft", "weiter gilt" oder "noch nicht entschieden" ist, wird NICHT aufgelöst. Konkreter Test: Kannst du klar sagen "Die These ist eingetreten weil X" oder "Die These ist widerlegt weil Y"? Wenn nein → NICHT auflösen. Leeres Array [] ist der Normalfall. Im Zweifel: nicht auflösen.
- thesis_probability_updates: Aktualisiere die Wahrscheinlichkeit einer These NUR wenn es einen KONKRETEN NEUEN DATENPUNKT gibt der die Einschätzung verändert. Folgewirkungen bereits bekannter Ereignisse (z.B. Markt-Crash als Reaktion auf gestrige Krise) sind KEIN neuer Datenpunkt. Konkreter Test: "Welche NEUE Information rechtfertigt die Änderung?" Wenn die Antwort nur Folgewirkungen beschreibt → Wahrscheinlichkeit NICHT ändern. Beispiel: Iran-Krieg war gestern bekannt → Dow-Crash heute ist Folgewirkung → KEINE Änderung. Neue Iran-Eskalationsstufe (z.B. Nukleardrohung) → JA, das ist ein neuer Datenpunkt. probability_positive_pct = Wahrscheinlichkeit dass das POSITIVE Szenario eintritt (0-100). Leeres Array [] wenn keine offenen Thesen existieren ODER keine neuen Datenpunkte vorliegen. WICHTIG: Wenn die vorherige Wahrscheinlichkeit z.B. 55% war und du auf 60% erhöhst, MUSS ein konkreter neuer Grund benannt werden ("Neu: Fed-Signal vom 3.3. stützt..."). "Die Daten bestätigen..." oder Umformulierungen des gleichen Arguments reichen NICHT — dann bleibt die Wahrscheinlichkeit gleich.
- probability_positive_pct bei neuen Thesen: IMMER setzen, basierend auf Evidenz. Nicht raten — nutze Basisraten aus Research, Marktdaten, historische Muster.
- key_levels, risk_assessment, action_triggers: IMMER ausf\u00fcllen, nie null
- historical_comparison: Nenne immer eine konkrete Vergleichsphase (Monat/Jahr). PRÜFE ob die Analogie tatsächlich passt! Frage dich: "Was passierte damals TATSÄCHLICH?" Beispiel: Frühjahr 2018 = Beginn US-China-Handelskrieg mit steigender Volatilität — das ist KEIN Beispiel für Marktstabilisierung. Wenn du die Phase nicht genau einordnen kannst, wähle eine andere oder schreibe "kein direkt vergleichbarer Zeitraum".
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
            result["_raw_text"] = llm_text
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
               history, theses, researches, news_results, lessons=None,
               positions=None, max_retries=1):
    """F\u00fchrt die Synthese-Stufe aus.

    Returns:
        tuple: (result_dict, raw_llm_text)
    """
    user_prompt = build_synthesis_prompt(
        market, mech_signals, mech_score, stage1_results,
        history, theses, researches, news_results, lessons, positions,
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

    # 0. Analyst Ratings & News synchronisieren
    log.info("=== Auto-Ampel Start für %s ===", date_str)
    print("Synchronisiere Analystenmeinungen...")
    try:
        from backend.routers.prices import sync_analyst_ratings
        ar_results = sync_analyst_ratings(db)
        ar_ok = len([r for r in ar_results if r["status"] == "ok"])
        print(f"  {ar_ok} Assets aktualisiert")
    except Exception as e:
        log.warning("Analysten-Sync fehlgeschlagen: %s", e)

    print("Sammle Analysten-News aus RSS-Feeds...")
    try:
        from backend.routers.prices import sync_all_analyst_news
        an_results = sync_all_analyst_news(db)
        an_ok = len([r for r in an_results if r["status"] == "ok"])
        print(f"  {an_ok} Assets News analysiert")
    except Exception as e:
        log.warning("Analysten-News fehlgeschlagen: %s", e)

    # 1. Marktdaten holen
    print(f"Hole Marktdaten für {date_str}...")

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
    positions = list(db.positions.find({"status": "open"}))

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
            history, theses, researches, news_results, lessons, positions,
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
            history, theses, researches, news_results, lessons, positions,
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

    # 10. Opportunity Scanner
    print("Starte Opportunity-Scan...")
    try:
        from backend.routers.scanner import run_opportunity_scan
        scan_result = run_opportunity_scan(db)
        opp_count = len(scan_result.get("opportunities", []))
        print(f"  {opp_count} Opportunities gefunden")
    except Exception as e:
        log.warning("Opportunity-Scan fehlgeschlagen: %s", e)

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
