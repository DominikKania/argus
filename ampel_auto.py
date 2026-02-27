#!/usr/bin/env python3
"""Vollautomatische Ampel-Analyse: Daten holen → Claude API → validieren → speichern."""

import io
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from ampel_data import fetch_all_market_data, calculate_mechanical_signals

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


# ── Prompt-Konstruktion ──────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Du bist der Ampel-Analyst des Argus Investment-Systems. Du erhältst quantitative Marktdaten \
(via yfinance API) und berechnete mechanische Signale.

## PORTFOLIO
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## DEINE AUFGABE
1. Bewerte den Kontext-Layer für jedes Signal (kann vom mechanischen Signal abweichen)
2. Identifiziere die 3 wichtigsten Sentiment-Events basierend auf deinem aktuellen Marktwissen
3. Bestimme das Sentiment-Signal (mechanisch + Kontext)
4. Erstelle die Gesamtbewertung (Overall Rating)
5. Formuliere eine Empfehlung
6. Erstelle optional eine These mit Katalysator
7. Setze Eskalations-Trigger und Crash-Regel

## SIGNAL-REGELN

### Trend (Kontext-Layer)
- Puffer Kurs↔SMA50: <2% = fragil, >5% = solide
- Golden Cross (SMA50 > SMA200) = Aufwärtstrend bestätigt
- Kurs über SMA50 aber unter SMA200 → "Erholung im Abwärtstrend" = gelb

### Volatilität (Kontext-Layer)
- VIX <13 allein ist KEIN automatisches Rot
- Prüfe ob VIX für "underpriced" gehalten wird

### Makro (Kontext-Layer)
- Spread-Richtung: Wird er enger oder weiter? (Trend > Snapshot)
- Real Yield >2.5% = restriktiv für Aktien
- CPI-Trend: steigend/fallend/stagnierend

### Sentiment
- 3 wichtigste Nachrichten der letzten 48h die das Portfolio betreffen
- Kaskadenrisiko bewerten: Kann es über den direkten Effekt hinaus eskalieren?
- HINWEIS: Du hast keinen Web-Zugang. Bewerte basierend auf deinem aktuellen Marktwissen.

## BELLER-CHECK (bei GELB/ROT)
- 🐕 BELLER: Politisch/mechanisch, VIX-Spike, Earnings intakt → Erholung in Tagen/Wochen
- 🦈 BEISSER: Fundamental, VIX dauerhaft erhöht, Earnings revidiert → 6-18 Monate
- ⏳ UNKLAR: Keine klare Zuordnung → Abwarten

## OVERALL RATING
- GREEN: 4/4 oder 3/4 mit stabilem Kontext
- GREEN_FRAGILE: 3/4 mit Risikofaktoren (niedriger Puffer etc.)
- YELLOW: 2/4 oder gemischte Signale
- YELLOW_BEARISH: 1-2/4 mit negativem Trend
- RED: 0-1/4 mit mehreren Warnungen
- RED_CAPITULATION: 0/4 mit Panik-Indikatoren

## ERWEITERTE MARKTDATEN

### Sektor-Rotation
- Risk-On vs. Defensive Spread > 0 = offensiver Markt (Tech, Financials, Industrials führen)
- Risk-On vs. Defensive Spread < 0 = defensiver Markt (Healthcare, Utilities, Consumer Staples führen)
- Extreme Divergenz (>5pp) kann Überhitzung oder Panik signalisieren
- Berücksichtige dies bei der Kontext-Bewertung von Trend und Sentiment

### Regionaler Vergleich (Europa vs USA)
- IWDA hat ~70% US-Gewichtung — US-Schwäche trifft stärker als Europa-Schwäche
- Divergenz USA/Europa kann auf regionsspezifische Risiken hinweisen
- Beide schwach = breite globale Schwäche → ernstes Signal

### Saisonalität
- Historische Muster sind KEIN Signal allein, nur Kontext
- Bekanntester Effekt: "Sell in May", Jahresendrally (Nov-Jan), Oktober-Schwäche
- Wenn saisonaler Bias mit anderen Signalen übereinstimmt → stärkt die These

### Put/Call Ratio
- >1.2 = hohe Angst (konträr: kann Kaufsignal sein wenn andere Signale grün)
- <0.7 = hohe Gier/Euphorie (Warnsignal für mögliche Korrektur)
- 0.7-1.2 = neutral
- Konträr-Indikator: Extreme deuten oft auf Wendepunkt hin

### Marktbreite (aus deinem Wissen)
- Bewerte A/D-Line, New Highs/Lows basierend auf aktuellen Berichten
- Divergenz (Index steigt, Marktbreite sinkt) ist klassisches Warnsignal
- ETF-Flows und Margin Debt: Erwähne wenn bedeutsam, ignoriere wenn unklar

## CRASH-REGEL
Bei VIX >35 UND Kurs >10% unter SMA200 → kein aktiver Re-Entry

## AUSGABE
Antworte AUSSCHLIESSLICH mit einem JSON-Objekt. Kein Text davor oder danach. Kein Markdown.
Verwende exakt dieses Schema:

{
  "signals": {
    "trend":      { "mechanical": "green|red",        "context": "green|yellow|red", "note": "..." },
    "volatility": { "mechanical": "green|yellow|red",  "context": "green|yellow|red", "note": "..." },
    "macro":      { "mechanical": "green|red",         "context": "green|yellow|red", "note": "..." },
    "sentiment":  { "mechanical": "green|yellow|red",  "context": "green|yellow|red", "note": "..." }
  },
  "rating": {
    "mechanical_score": 0,
    "overall": "GREEN|GREEN_FRAGILE|YELLOW|YELLOW_BEARISH|RED|RED_CAPITULATION",
    "reasoning": "..."
  },
  "beller_check": {
    "triggered": false,
    "classification": "beller|beisser|unclear|null",
    "trigger_type": "political|mechanical|fundamental|null",
    "vix_pattern": "spike|sustained|null",
    "earnings_status": "intact|revised|null",
    "breadth": "sector|broad|null",
    "reasoning": ""
  },
  "sentiment_events": [
    { "headline": "...", "summary": "...", "affects_portfolio": "direct|sector_only|indirect", "cascade_risk": "low|medium|high", "is_primary": true },
    { "headline": "...", "summary": "...", "affects_portfolio": "...", "cascade_risk": "...", "is_primary": false },
    { "headline": "...", "summary": "...", "affects_portfolio": "...", "cascade_risk": "...", "is_primary": false }
  ],
  "recommendation": {
    "action": "hold|buy|partial_sell|hedge|wait",
    "detail": "..."
  },
  "thesis": {
    "statement": "...",
    "catalyst": "...",
    "catalyst_date": "YYYY-MM-DD",
    "expected_if_positive": "...",
    "expected_if_negative": "..."
  },
  "escalation_trigger": "...",
  "crash_rule_active": false,
  "market_context": {
    "sector_rotation_note": "...",
    "regional_note": "...",
    "seasonality_note": "...",
    "breadth_note": "...",
    "put_call_note": "..."
  }
}

REGELN:
- Alle Texte auf Deutsch, kurz und prägnant
- Enum-Werte exakt wie angegeben (lowercase)
- Zahlen ohne Einheiten
- sentiment_events enthält genau 3 Einträge
- beller_check.triggered=false und Felder auf null wenn Ampel GRÜN
- thesis darf null sein wenn keine neue These sinnvoll ist
- market_context: Kurze Notizen zu erweiterten Marktdaten, nur ausfüllen wenn relevant
"""


def build_user_prompt(market, mech_signals, mech_score, history, theses, researches=None):
    """Baut den User-Prompt mit aktuellen Daten zusammen."""
    vix = market["vix"]
    yld = market["yields"]

    lines = [
        f"Erstelle die Ampel-Analyse für {datetime.now().strftime('%Y-%m-%d')}.",
        "",
        "## MARKTDATEN (via yfinance API, aktuell)",
        f"- IWDA Kurs: {market['price']}€ | SMA50: {market['sma50']}€ | SMA200: {market['sma200']}€",
        f"- ATH: {market['ath']}€ | Delta ATH: {market['delta_ath_pct']}%",
        f"- Puffer SMA50: {market['puffer_sma50_pct']}%",
        f"- Golden Cross: {'Ja' if market['golden_cross'] else 'Nein'}",
        f"- VIX: {vix['value']} (Vorwoche: {vix['prev_week']}, Richtung: {vix['direction']})",
        f"- US 10Y: {yld['us10y']}% | US 2Y: {yld['us2y']}% | Spread: {yld['spread']}% ({yld['spread_direction']})",
        f"- CPI: {yld['cpi']}% | Real Yield: {yld['real_yield']}%",
    ]

    # Sektor-Rotation
    sr = market.get("sector_rotation")
    if sr and sr.get("sectors"):
        lines.append("")
        lines.append("## SEKTOR-ROTATION (1-Monats-Performance, Sektor-ETFs)")
        for name, data in sr["sectors"].items():
            lines.append(f"- {name.replace('_', ' ').title()}: {data['perf_1m']:+.2f}% ({data['ticker']})")
        if sr.get("risk_on_vs_off") is not None:
            lines.append(f"- Risk-On vs. Defensive Spread: {sr['risk_on_vs_off']:+.2f}pp")

    # Regionaler Vergleich
    reg = market.get("regional")
    if reg:
        lines.append("")
        lines.append("## REGIONALER VERGLEICH (1 Monat)")
        if reg.get("spy_perf_1m") is not None:
            lines.append(f"- USA (SPY): {reg['spy_perf_1m']:+.2f}%")
        if reg.get("ezu_perf_1m") is not None:
            lines.append(f"- Europa (EZU): {reg['ezu_perf_1m']:+.2f}%")
        if reg.get("usa_vs_europe") is not None:
            lines.append(f"- USA vs. Europa Differenz: {reg['usa_vs_europe']:+.2f}pp")

    # Saisonalität
    seas = market.get("seasonality")
    if seas:
        month_names = {1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun",
                       7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez"}
        m = seas["current_month"]
        lines.append("")
        lines.append("## SAISONALITÄT (IWDA historisch)")
        lines.append(f"- Aktueller Monat ({month_names.get(m, m)}): avg. {seas['avg_return_pct']:+.2f}%")
        lines.append(f"- Saisonaler Bias: {seas['seasonal_bias']}")

    # Put/Call Ratio
    pc = market.get("put_call")
    if pc:
        lines.append("")
        lines.append("## PUT/CALL RATIO (SPY, nächster Verfall)")
        lines.append(f"- Put OI: {pc['put_oi']:,} | Call OI: {pc['call_oi']:,}")
        lines.append(f"- Ratio: {pc['ratio']:.2f} ({pc['signal']})")

    # Zusätzlicher Kontext (LLM-Wissen)
    lines.append("")
    lines.append("## ZUSÄTZLICHER KONTEXT (aus deinem Marktwissen)")
    lines.append("Bewerte folgende Punkte basierend auf deinem aktuellen Wissen:")
    lines.append("- Advance/Decline-Line: Ist die Marktbreite gesund oder divergiert sie vom Index?")
    lines.append("- New Highs vs. New Lows: Gibt es Anzeichen für breite Schwäche?")
    lines.append("- ETF-Flows (MSCI World / IWDA): Gibt es Anzeichen für Zu- oder Abflüsse?")
    lines.append("- Margin Debt: Gibt es Berichte über erhöhte oder fallende Margin-Schulden?")

    lines.extend([
        "",
        "## MECHANISCHE SIGNALE (berechnet)",
        f"- Trend: {mech_signals['trend']} (Kurs {'über' if market['price'] > market['sma50'] else 'unter'} SMA50)",
        f"- Volatilität: {mech_signals['volatility']} (VIX {vix['value']})",
        f"- Makro: {mech_signals['macro']} (Spread {yld['spread']}%)",
        f"- Sentiment: noch zu bewerten",
        f"- Mechanischer Score: {mech_score}/4 (ohne Sentiment)",
    ])

    # Verlauf
    if history:
        lines.append("")
        lines.append("## LETZTE ANALYSEN")
        for doc in history:
            sig = doc.get("signals", {})
            rat = doc.get("rating", {})
            rec = doc.get("recommendation", {})
            lines.append(
                f"- {doc['date']}: {rat.get('overall', '?')} (Score {rat.get('mechanical_score', '?')}/4) | "
                f"T={sig.get('trend', {}).get('context', '?')} V={sig.get('volatility', {}).get('context', '?')} "
                f"M={sig.get('macro', {}).get('context', '?')} S={sig.get('sentiment', {}).get('context', '?')} | "
                f"Empfehlung: {rec.get('action', '?')}"
            )

            # These der letzten Analyse
            thesis = doc.get("thesis")
            if thesis and thesis.get("statement"):
                lines.append(f"  These: {thesis['statement']}")

            trigger = doc.get("escalation_trigger")
            if trigger:
                lines.append(f"  Trigger: {trigger}")

    # Offene Thesen
    if theses:
        lines.append("")
        lines.append("## OFFENE THESEN")
        for t in theses:
            cat_info = ""
            if t.get("catalyst_date"):
                cat_info = f" (Katalysator: {t['catalyst_date']})"
            lines.append(f"- [{t['created_date']}] {t['statement']}{cat_info}")

    # Research-Kontext
    if researches:
        lines.append("")
        lines.append("## RESEARCH-KONTEXT")
        lines.append("Folgende Deep-Research-Ergebnisse liegen vor und sollten in die Analyse einfließen:")
        for r in researches:
            summary = r.get("relevance_summary") or "Keine Zusammenfassung verfügbar"
            lines.append(f"- **{r['title']}**: {summary}")

    return "\n".join(lines)


# ── Claude API Aufruf ────────────────────────────────────────────────────

def call_llm(system_prompt, user_prompt):
    """Ruft das konfigurierte LLM auf und gibt die Textantwort zurück."""
    provider_type, client, model = get_llm_client()

    log.info("LLM-Aufruf: provider=%s, model=%s", provider_type, model)

    if provider_type == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
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
        )
        return response.choices[0].message.content


def extract_json(text):
    """Extrahiert JSON aus LLM-Antwort (mit oder ohne Markdown-Fences)."""
    # Versuche Markdown-Code-Block zu finden
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    # Versuche das erste { ... } Objekt zu finden
    start = text.find("{")
    if start == -1:
        raise ValueError("Kein JSON-Objekt in LLM-Antwort gefunden")

    # Finde das passende schließende }
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError("Unvollständiges JSON-Objekt in LLM-Antwort")


# ── Einsteiger-Modus (Vereinfachung) ────────────────────────────────────

SIMPLIFY_SYSTEM_PROMPT = """\
Du bist ein freundlicher Erklärer für Börsen-Anfänger. Du bekommst Analyse-Texte \
eines Investment-Systems und sollst sie in einfaches, verständliches Deutsch umschreiben.

REGELN:
- Erkläre JEDEN Fachbegriff in Klammern beim ersten Vorkommen:
  - ATH = Allzeithoch (der höchste Kurs, den es je gab)
  - SMA50/SMA200 = Durchschnittskurs der letzten 50/200 Tage
  - Golden Cross = wenn der 50-Tage-Schnitt über den 200-Tage-Schnitt steigt (gutes Zeichen)
  - Puffer = Abstand zwischen aktuellem Kurs und einem wichtigen Niveau
  - VIX = Angstbarometer der Börse (niedrig = ruhig, hoch = nervös)
  - Spread = Differenz zwischen zwei Zinssätzen
  - Stop-Loss = Kurs bei dem man verkauft um Verluste zu begrenzen
  - Beller = kurzfristiger Schreck an der Börse, erholt sich schnell
  - Beisser = ernstes Problem, dauert länger
  - Hedge = Absicherung gegen Verluste
  - CPI = Verbraucherpreisindex (misst die Inflation)
  - Real Yield = Realzins (Zins minus Inflation)
- Zahlen, Prozentwerte und Daten NICHT verändern — exakt übernehmen
- Kurze, klare Sätze verwenden
- Freundlicher, ermutigender Ton — kein Fachchinesisch
- Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, kein Text davor oder danach
- Verwende exakt dieselben JSON-Schlüssel wie im Input
"""


def simplify_analysis(analysis):
    """Vereinfacht alle Textfelder einer Analyse für den Einsteiger-Modus."""

    # Textfelder extrahieren
    texts = {
        "rating_reasoning": analysis.get("rating", {}).get("reasoning", ""),
        "recommendation_detail": analysis.get("recommendation", {}).get("detail", ""),
        "escalation_trigger": analysis.get("escalation_trigger", "") or "",
        "signal_notes": {
            name: sig.get("note", "")
            for name, sig in analysis.get("signals", {}).items()
        },
        "sentiment_events": [
            {"headline": e.get("headline", ""), "summary": e.get("summary", "")}
            for e in analysis.get("sentiment_events", [])
        ],
        "beller_check_reasoning": (analysis.get("beller_check") or {}).get("reasoning", "") or "",
    }

    thesis = analysis.get("thesis")
    if thesis:
        texts["thesis"] = {
            "statement": thesis.get("statement", ""),
            "catalyst": thesis.get("catalyst", ""),
            "expected_if_positive": thesis.get("expected_if_positive", ""),
            "expected_if_negative": thesis.get("expected_if_negative", ""),
        }

    user_prompt = (
        "Vereinfache diese Analyse-Texte für einen Börsen-Anfänger.\n"
        "Gib die vereinfachten Texte als JSON mit exakt denselben Schlüsseln zurück.\n\n"
        + json.dumps(texts, ensure_ascii=False, indent=2)
    )

    try:
        llm_text = call_llm(SIMPLIFY_SYSTEM_PROMPT, user_prompt)
        return extract_json(llm_text)
    except Exception as e:
        log.warning("Vereinfachung fehlgeschlagen: %s", e)
        return None


# ── Hybrid-Merge ─────────────────────────────────────────────────────────

def merge_analysis(date_str, market, mech_signals, mech_score, llm_data):
    """Merged deterministische Daten mit LLM-Output zu vollständiger Analyse.

    Marktdaten und mechanische Signale kommen aus unserer Berechnung (vertrauenswürdig).
    Context, Rating, Sentiment, Thesis kommen vom LLM.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Signale: mechanical aus unserer Berechnung, context+note vom LLM
    signals = {}
    for name in ["trend", "volatility", "macro", "sentiment"]:
        llm_sig = llm_data.get("signals", {}).get(name, {})
        signals[name] = {
            "mechanical": mech_signals[name] if name != "sentiment" else llm_sig.get("mechanical", "green"),
            "context": llm_sig.get("context", mech_signals.get(name, "green")),
            "note": llm_sig.get("note", ""),
        }

    # Rating: mechanical_score aus unserer Berechnung (Sentiment vom LLM einrechnen)
    sent_mech = signals["sentiment"]["mechanical"]
    actual_score = sum(1 for n in ["trend", "volatility", "macro"] if mech_signals[n] == "green")
    if sent_mech == "green":
        actual_score += 1

    llm_rating = llm_data.get("rating", {})

    analysis = {
        "date": date_str,
        "weekday": weekdays[dt.weekday()],
        "market": market,
        "signals": signals,
        "rating": {
            "mechanical_score": actual_score,
            "overall": llm_rating.get("overall", "YELLOW"),
            "reasoning": llm_rating.get("reasoning", ""),
        },
        "beller_check": llm_data.get("beller_check", {
            "triggered": False,
            "classification": None,
            "trigger_type": None,
            "vix_pattern": None,
            "earnings_status": None,
            "breadth": None,
            "reasoning": "",
        }),
        "sentiment_events": llm_data.get("sentiment_events", []),
        "recommendation": llm_data.get("recommendation", {"action": "hold", "detail": ""}),
        "thesis": llm_data.get("thesis"),
        "escalation_trigger": llm_data.get("escalation_trigger"),
        "crash_rule_active": llm_data.get("crash_rule_active", False),
        "market_context": llm_data.get("market_context"),
    }

    return analysis


# ── Orchestrator ─────────────────────────────────────────────────────────

def run_auto_ampel(db, date_override=None, cpi_override=None, dry_run=False):
    """Führt die vollautomatische Ampel-Analyse durch.

    Returns:
        dict: Die gespeicherte Analyse, oder None bei Fehler/Skip.
    """
    date_str = date_override or datetime.now().strftime("%Y-%m-%d")

    # Bestehende Analyse für diesen Tag löschen (ermöglicht wiederholtes Testen)
    if not dry_run:
        existing = db.analyses.find_one({"date": date_str})
        if existing:
            db.analyses.delete_one({"date": date_str})
            # Zugehörige These auch löschen
            db.theses.delete_many({"analysis_id": existing["_id"]})
            log.info("Bestehende Analyse für %s gelöscht.", date_str)
            print(f"Bestehende Analyse für {date_str} gelöscht — wird neu erstellt.")

    # 1. Marktdaten holen
    log.info("=== Auto-Ampel Start für %s ===", date_str)
    print(f"Hole Marktdaten für {date_str}...")

    market = fetch_all_market_data(db, cpi_override=cpi_override)

    # 2. Mechanische Signale berechnen
    mech_signals, mech_score = calculate_mechanical_signals(market)

    # 3. Verlauf + Thesen + Researches aus DB laden
    history = list(db.analyses.find(sort=[("date", -1)]).limit(5))
    theses = list(db.theses.find({"status": "open"}).sort("created_date", -1))
    researches = list(db.researches.find(
        {"status": "completed", "relevance_summary": {"$ne": None}},
        {"results": 0},
    ))

    # 4. Claude API aufrufen
    print("Rufe LLM für Kontextanalyse auf...")
    user_prompt = build_user_prompt(market, mech_signals, mech_score, history, theses, researches)
    llm_text = call_llm(SYSTEM_PROMPT, user_prompt)

    # 5. JSON parsen
    try:
        llm_data = extract_json(llm_text)
    except (json.JSONDecodeError, ValueError) as e:
        log.error("JSON-Parsing fehlgeschlagen: %s", e)
        log.debug("LLM-Antwort: %s", llm_text[:500])

        # Retry mit Fehlermeldung
        print("JSON-Parsing fehlgeschlagen, versuche erneut...")
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"WICHTIG: Dein vorheriger Versuch war kein gültiges JSON. "
            f"Fehler: {e}\n"
            f"Antworte NUR mit dem JSON-Objekt. Kein Text, kein Markdown."
        )
        llm_text = call_llm(SYSTEM_PROMPT, retry_prompt)
        try:
            llm_data = extract_json(llm_text)
        except (json.JSONDecodeError, ValueError) as e2:
            log.error("Retry fehlgeschlagen: %s", e2)
            print(f"Fehler: LLM-Antwort ist kein gültiges JSON. Abbruch.", file=sys.stderr)
            return None

    # 6. Hybrid-Merge
    analysis = merge_analysis(date_str, market, mech_signals, mech_score, llm_data)

    # 7. Validieren
    from argus import validate_analysis
    errors = validate_analysis(analysis)
    if errors:
        log.error("Validierungsfehler: %s", errors)

        # Retry mit Validierungsfehlern
        print("Validierungsfehler, versuche erneut...")
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"WICHTIG: Die letzte Analyse hatte Validierungsfehler:\n"
            + "\n".join(f"- {e}" for e in errors) +
            "\nBitte korrigiere diese Fehler im JSON."
        )
        llm_text = call_llm(SYSTEM_PROMPT, retry_prompt)
        try:
            llm_data = extract_json(llm_text)
            analysis = merge_analysis(date_str, market, mech_signals, mech_score, llm_data)
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

    # 8. Einsteiger-Modus: Textfelder vereinfachen
    print("Erstelle Einsteiger-Version...")
    simplified = simplify_analysis(analysis)
    if simplified:
        analysis["simplified"] = simplified
        log.info("Einsteiger-Version erstellt.")
    else:
        log.warning("Einsteiger-Version konnte nicht erstellt werden — fahre ohne fort.")

    # 9. Speichern oder Dry-Run
    if dry_run:
        print("\n--- DRY RUN (nicht gespeichert) ---")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return analysis

    from argus import save_analysis
    save_analysis(db, analysis)

    log.info("=== Auto-Ampel abgeschlossen: %s → %s ===", date_str, analysis["rating"]["overall"])
    return analysis


# ── Logging Setup ────────────────────────────────────────────────────────

def setup_logging():
    """Konfiguriert Logging für den Auto-Ampel-Lauf."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ampel_auto.log")

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    root_logger = logging.getLogger("ampel")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # Auch auf stdout loggen
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root_logger.addHandler(console)
