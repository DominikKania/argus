#!/usr/bin/env python3
"""News-Modul: RSS-Headlines sammeln + Claude-Analyse pro konfiguriertem Topic."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import feedparser

log = logging.getLogger("ampel")

# ── Default RSS-Feeds ────────────────────────────────────────────────────

DEFAULT_RSS_FEEDS = [
    # International — Englisch
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "FT Markets", "url": "https://www.ft.com/markets?format=rss"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/marketpulse"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    # Deutschland
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen"},
    {"name": "FAZ Finanzen", "url": "https://www.faz.net/rss/aktuell/finanzen/"},
    {"name": "Tagesschau Wirtschaft", "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml"},
    {"name": "Spiegel Wirtschaft", "url": "https://www.spiegel.de/wirtschaft/index.rss"},
    {"name": "NTV Wirtschaft", "url": "https://www.n-tv.de/wirtschaft/rss"},
]

# ── RSS-Fetching ─────────────────────────────────────────────────────────


def _fetch_single_feed(feed, max_entries=10):
    """Holt Headlines aus einem einzelnen RSS-Feed."""
    try:
        parsed = feedparser.parse(feed["url"])
        headlines = []
        for entry in parsed.entries[:max_entries]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            headlines.append({
                "title": title,
                "source": feed["name"],
                "link": entry.get("link", ""),
                "date": entry.get("published", ""),
            })
        log.info("RSS %s: %d Headlines", feed["name"], len(headlines))
        return headlines
    except Exception as e:
        log.warning("RSS %s fehlgeschlagen: %s", feed["name"], e)
        return []


def fetch_rss_headlines(feeds=None, max_per_feed=20):
    """Holt Headlines aus allen konfigurierten RSS-Feeds parallel.

    Args:
        feeds: Liste von Feed-Dicts (name, url). Default: DEFAULT_RSS_FEEDS
        max_per_feed: Maximale Anzahl Einträge pro Feed

    Returns:
        Liste von {"title", "source", "date", "link"} Dicts
    """
    if feeds is None:
        feeds = DEFAULT_RSS_FEEDS

    all_headlines = []
    with ThreadPoolExecutor(max_workers=len(feeds)) as executor:
        futures = {
            executor.submit(_fetch_single_feed, feed, max_per_feed): feed["name"]
            for feed in feeds
        }
        for future in as_completed(futures):
            try:
                all_headlines.extend(future.result())
            except Exception as e:
                name = futures[future]
                log.warning("Feed %s Exception: %s", name, e)

    # Deduplizieren (gleiche Title ignorieren)
    seen = set()
    unique = []
    for h in all_headlines:
        key = h["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(h)

    log.info("RSS gesamt: %d Headlines (%d unique)", len(all_headlines), len(unique))
    return unique


# ── Prompt-Assistent ─────────────────────────────────────────────────────

PROMPT_HELPER_SYSTEM = """\
Du erstellst fokussierte News-Analyse-Prompts für das Argus Investment-System.

Der Prompt wird täglich verwendet um RSS-Headlines zu einem bestimmten Thema zu analysieren.
Er soll Claude anweisen:
- Welche Art von Headlines relevant sind
- Worauf genau geachtet werden soll (Eskalation/De-Eskalation, Tonwechsel, Zeitplan etc.)
- Welche Trigger-Events wichtig wären
- Wie das Thema das IWDA-Portfolio (100% MSCI World ETF) betrifft

Schreibe den Prompt auf Deutsch, klar und spezifisch. Maximal 10-15 Zeilen.
Gib NUR den Prompt-Text zurück, keine Erklärung.\
"""


def generate_news_prompt(title):
    """Generiert einen News-Analyse-Prompt via LLM."""
    from backend.llm import call_llm
    return call_llm(
        PROMPT_HELPER_SYSTEM,
        [{"role": "user", "content": f"Erstelle einen News-Analyse-Prompt zum Thema: {title}"}],
    )


# ── Claude-Analyse pro Topic ────────────────────────────────────────────

NEWS_ANALYSIS_SYSTEM = """\
Du bist ein Markt-Analyst der aktuelle Nachrichten für ein spezifisches Thema auswertet.

Du erhältst:
1. Aktuelle Headlines aus RSS-Feeds (heute gesammelt)
2. Einen konfigurierten Analyse-Fokus (was genau beobachtet werden soll)
3. Optional: Marktkontext aus der letzten Ampel-Analyse
4. Optional: Bisherige Analysen zu diesem Thema (Verlauf der letzten Tage)

Deine Aufgabe:
- Filtere die relevanten Headlines für dieses Thema
- Bewerte FAKTENBASIERT: Zähle positive vs. negative Headlines. Bewerte NUR was in den Headlines steht, nicht was du vermutest.
- Beziehe dich auf den bisherigen Verlauf: Bestätigt sich ein Trend? Gibt es eine Trendwende?
- Identifiziere konkrete Trigger-Events (nur wenn explizit in Headlines erwähnt)
- Gib eine kurze Zusammenfassung (3-5 Sätze) die auf den bisherigen Analysen aufbaut

## TREND-BESTIMMUNG (strenge Regeln)
Zähle die relevanten Headlines nach Sentiment:
- "improving": Mehr positive als negative Headlines UND mindestens eine konkrete positive Entwicklung (Verhandlung, Einigung, Rücknahme)
- "deteriorating": Mehr negative als positive Headlines UND mindestens eine konkrete Verschlechterung (Eskalation, neue Sanktionen, Abbruch)
- "stable": Gemischte Headlines ODER keine klare Richtung ODER keine relevanten Headlines

WICHTIG: Im Zweifel IMMER "stable" wählen. Nur bei klarer Evidenz in den Headlines von stable abweichen.
Wenn bisherige Analysen vorliegen: Ein Trendwechsel (z.B. von deteriorating zu improving) braucht STARKE Evidenz — mindestens 2-3 eindeutige Headlines die die neue Richtung belegen.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{
  "summary": "3-5 Sätze Zusammenfassung der aktuellen Lage zu diesem Thema, aufbauend auf bisherigem Verlauf",
  "relevant_headlines": [
    {"title": "Deutsche Übersetzung der Headline", "source": "Quellenname", "link": "https://...", "relevance": "high|medium|low", "sentiment": "positive|negative|neutral"}
  ],
  "sentiment_count": {"positive": 0, "negative": 0, "neutral": 0},
  "trend": "improving|stable|deteriorating",
  "trend_reasoning": "Kurze Begründung: X positive, Y negative Headlines. Deshalb trend=...",
  "triggers_detected": ["Konkrete Trigger-Events die eingetreten sind oder bevorstehen"],
  "ampel_relevance": "Ein Satz: Wie beeinflusst das die Ampel-Analyse?"
}

REGELN:
- Alle Texte auf Deutsch
- relevant_headlines: title IMMER auf Deutsch übersetzen (auch wenn Original englisch ist). source und link aus den Input-Headlines übernehmen.
- relevant_headlines: nur Headlines die wirklich zum Thema passen (max 5)
- sentiment_count: Zählung MUSS mit den sentiment-Werten in relevant_headlines übereinstimmen
- trend MUSS mit sentiment_count konsistent sein (nicht mehr negative als positive und trotzdem "improving")
- triggers_detected: leere Liste wenn keine Trigger erkannt. NUR Trigger die EXPLIZIT in Headlines stehen.
- Wenn keine relevanten Headlines gefunden: summary = "Keine relevanten Nachrichten heute", trend = "stable"
- Wenn bisherige Analysen vorliegen: Beziehe dich explizit auf Veränderungen ("Gestern noch deteriorating, heute Anzeichen für Stabilisierung" etc.)
"""


def analyze_news_topic(topic_doc, headlines, market_context=None, previous_results=None):
    """Analysiert gesammelte Headlines für ein bestimmtes Topic via Claude.

    Args:
        topic_doc: MongoDB-Dokument des Topics (mit prompt, title)
        headlines: Liste von RSS-Headlines
        market_context: Optional, letzte Analyse als String
        previous_results: Optional, Liste bisheriger Analysen (neueste zuerst)

    Returns:
        Dict mit summary, relevant_headlines, trend, triggers_detected, ampel_relevance
    """
    from ampel_auto import call_llm, extract_json

    # User-Prompt zusammenbauen
    headlines_text = "\n".join(
        f"- [{h['source']}] {h['title']} | link: {h.get('link', '')}" for h in headlines
    )

    parts = [
        f"## THEMA: {topic_doc['title']}",
        "",
        f"## ANALYSE-FOKUS",
        topic_doc.get("prompt", "Allgemeine Analyse"),
        "",
        f"## AKTUELLE HEADLINES ({len(headlines)} Stück)",
        headlines_text,
    ]

    if previous_results:
        parts.extend(["", f"## BISHERIGE ANALYSEN (letzte {len(previous_results)} Tage)"])
        for prev in previous_results:
            triggers = ", ".join(prev.get("triggers_detected", [])) or "keine"
            parts.append(
                f"- {prev['date']}: {prev.get('trend', '?')} — {prev.get('summary', '')}\n"
                f"  Trigger: {triggers} | Ampel: {prev.get('ampel_relevance', '-')}"
            )

    if market_context:
        parts.extend(["", "## MARKTKONTEXT", market_context])

    user_prompt = "\n".join(parts)
    llm_text = call_llm(NEWS_ANALYSIS_SYSTEM, user_prompt, temperature=0)

    try:
        return extract_json(llm_text)
    except (json.JSONDecodeError, ValueError) as e:
        log.error("News-Analyse JSON-Parsing fehlgeschlagen für %s: %s", topic_doc["topic"], e)
        return {
            "summary": f"Analyse-Fehler: {e}",
            "relevant_headlines": [],
            "trend": "stable",
            "triggers_detected": [],
            "ampel_relevance": "Keine Aussage möglich (Parsing-Fehler)",
        }


# ── Orchestrator ─────────────────────────────────────────────────────────

def run_news_topic(db, topic_slug, headlines=None):
    """Führt die News-Analyse für ein einzelnes Topic durch.

    Args:
        db: MongoDB-Datenbankinstanz
        topic_slug: Slug des Topics
        headlines: Optional, bereits geholte Headlines (sonst werden sie geholt)

    Returns:
        Das gespeicherte Result-Dict, oder None bei Fehler
    """
    topic = db.news_topics.find_one({"topic": topic_slug})
    if not topic:
        log.error("News-Topic '%s' nicht gefunden", topic_slug)
        return None

    # Headlines holen wenn nicht mitgegeben
    if headlines is None:
        feeds = topic.get("rss_feeds") or DEFAULT_RSS_FEEDS
        headlines = fetch_rss_headlines(feeds)

    # Marktkontext laden
    analysis = db.analyses.find_one(sort=[("date", -1)])
    market_context = None
    if analysis:
        market_context = (
            f"Letzte Analyse ({analysis['date']}): "
            f"{analysis['rating']['overall']} (Score {analysis['rating']['mechanical_score']}/4) — "
            f"{analysis['recommendation']['action']}"
        )

    # Bisherige Ergebnisse für dieses Topic laden (letzte 5, ohne heute)
    today = datetime.now().strftime("%Y-%m-%d")
    previous_results = list(
        db.news_results.find(
            {"topic": topic_slug, "date": {"$ne": today}},
            {"raw_headlines": 0},
        ).sort("date", -1).limit(5)
    )

    # Analyse durchführen
    log.info("News-Analyse starten: %s (%d bisherige Ergebnisse)", topic["title"], len(previous_results))
    result = analyze_news_topic(topic, headlines, market_context, previous_results)

    # Ergebnis speichern
    today = datetime.now().strftime("%Y-%m-%d")
    doc = {
        "topic": topic_slug,
        "date": today,
        "headlines_fetched": len(headlines),
        "relevant_headlines": result.get("relevant_headlines", []),
        "sentiment_count": result.get("sentiment_count", {}),
        "summary": result.get("summary", ""),
        "trend": result.get("trend", "stable"),
        "trend_reasoning": result.get("trend_reasoning", ""),
        "triggers_detected": result.get("triggers_detected", []),
        "ampel_relevance": result.get("ampel_relevance", ""),
        "raw_headlines": headlines,
        "created_date": datetime.now().isoformat(),
    }

    # Upsert: wenn für heute schon ein Ergebnis existiert, überschreiben
    db.news_results.update_one(
        {"topic": topic_slug, "date": today},
        {"$set": doc},
        upsert=True,
    )

    log.info("News-Ergebnis gespeichert: %s → %s", topic["title"], result.get("trend", "?"))
    return doc


def run_all_news_topics(db):
    """Führt die News-Analyse für alle aktiven Topics durch.

    Headlines werden einmal geholt und für alle Topics wiederverwendet.

    Returns:
        Anzahl der erfolgreich analysierten Topics
    """
    topics = list(db.news_topics.find({"active": True}))
    if not topics:
        log.info("Keine aktiven News-Topics")
        return 0

    # Headlines einmal für alle Topics holen
    headlines = fetch_rss_headlines()
    log.info("%d Headlines für %d aktive Topics geholt", len(headlines), len(topics))

    count = 0
    for topic in topics:
        try:
            result = run_news_topic(db, topic["topic"], headlines=headlines)
            if result:
                count += 1
                print(f"  News: {topic['title']} → {result.get('trend', '?')}")
        except Exception as e:
            log.error("News-Topic %s fehlgeschlagen: %s", topic["topic"], e)

    return count
