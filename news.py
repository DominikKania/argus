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
    # International — Finanzen
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "FT Markets", "url": "https://www.ft.com/markets?format=rss"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/marketpulse"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    # International — Politik & Welt
    {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=political-general"},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    # Deutschland — Finanzen
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen"},
    {"name": "FAZ Finanzen", "url": "https://www.faz.net/rss/aktuell/finanzen/"},
    # Deutschland — Wirtschaft & Politik
    {"name": "Tagesschau Wirtschaft", "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml"},
    {"name": "Tagesschau Inland", "url": "https://www.tagesschau.de/inland/index~rss2.xml"},
    {"name": "Tagesschau Ausland", "url": "https://www.tagesschau.de/ausland/index~rss2.xml"},
    {"name": "Spiegel Wirtschaft", "url": "https://www.spiegel.de/wirtschaft/index.rss"},
    {"name": "Spiegel Politik", "url": "https://www.spiegel.de/politik/index.rss"},
    {"name": "NTV Wirtschaft", "url": "https://www.n-tv.de/wirtschaft/rss"},
    {"name": "NTV Politik", "url": "https://www.n-tv.de/politik/rss"},
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
- Wie das Thema die zugeordneten Assets betrifft (bei mehreren Assets: Auswirkungen vergleichen)

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
- Trenne klar: Was ist NEU (development) vs. was bestätigt sich (recurring)?
- Identifiziere konkrete Trigger-Events (nur wenn explizit in Headlines erwähnt)
- Gib eine kurze Einordnung (summary: 2-3 Sätze), die Details stecken in development/recurring

## TREND-BESTIMMUNG (strenge Regeln)
Zähle die relevanten Headlines nach Sentiment:
- "improving": Mehr positive als negative Headlines UND mindestens eine konkrete positive Entwicklung (Verhandlung, Einigung, Rücknahme)
- "deteriorating": Mehr negative als positive Headlines UND mindestens eine konkrete Verschlechterung (Eskalation, neue Sanktionen, Abbruch)
- "stable": Gemischte Headlines ODER keine klare Richtung ODER keine relevanten Headlines

WICHTIG: Im Zweifel IMMER "stable" wählen. Nur bei klarer Evidenz in den Headlines von stable abweichen.
Wenn bisherige Analysen vorliegen: Ein Trendwechsel (z.B. von deteriorating zu improving) braucht STARKE Evidenz — mindestens 2-3 eindeutige Headlines die die neue Richtung belegen.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{
  "summary": "2-3 Sätze Einordnung: Wo steht das Thema heute? Keine Wiederholung der Gesamtlage — die steckt in development/recurring.",
  "development": "Was ist NEU seit der letzten Analyse? Nur Fakten die vorher NICHT bekannt waren: neue Ereignisse, Eskalationen, Wendepunkte, neue Akteure. Wenn erste Analyse (keine bisherigen): Ausgangslage beschreiben.",
  "recurring": "Was bestätigt sich weiterhin? Welche Themen, Risiken oder Trends tauchen wiederholt auf? Wenn erste Analyse (keine bisherigen): leerer String.",
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
- development: STRIKT nur neue Informationen. Vergleiche mit den bisherigen Analysen — was dort schon stand, gehört NICHT in development sondern in recurring. Bei erster Analyse: beschreibe die Ausgangslage.
- recurring: Nur befüllen wenn bisherige Analysen vorliegen. Fasse zusammen was sich über mehrere Tage bestätigt (z.B. "Ölpreise bleiben erhöht", "Handelsrouten weiter gestört").
- summary: Kurze Einordnung (2-3 Sätze). KEINE Wiederholung von development/recurring. Fokus auf: Was bedeutet das insgesamt?
- relevant_headlines: title IMMER auf Deutsch übersetzen (auch wenn Original englisch ist). source und link aus den Input-Headlines übernehmen.
- relevant_headlines: nur Headlines die wirklich zum Thema passen (max 5)
- sentiment_count: Zählung MUSS mit den sentiment-Werten in relevant_headlines übereinstimmen
- trend MUSS mit sentiment_count konsistent sein (nicht mehr negative als positive und trotzdem "improving")
- triggers_detected: leere Liste wenn keine Trigger erkannt. NUR Trigger die EXPLIZIT in Headlines stehen.
- Wenn keine relevanten Headlines gefunden: summary = "Keine relevanten Nachrichten heute", trend = "stable"
"""


NEWS_DEEP_RESEARCH_SYSTEM = """\
Du bist ein Deep-Research-Analyst im Argus Investment-System. Du führst eine tiefgehende \
Analyse zu einem spezifischen News-Thema durch.

Du erhältst:
1. Das Thema und den Analyse-Fokus
2. Die heutige Headline-Analyse (Zusammenfassung, Trend, relevante Headlines)
3. Optional: Bisherige Analysen (Verlauf)
4. Optional: Marktkontext

## HEUTIGES DATUM
{today}

## PORTFOLIO-KONTEXT
Position: iShares Core MSCI World UCITS ETF USD (Acc) — ISIN: IE00B4L5Y983, ~6.700€, 100%

## DEINE AUFGABE
1. Nutze die Web-Suche um aktuelle Nachrichten und Entwicklungen zum Thema zu finden
2. Suche nach konkreten, aktuellen Artikeln — nicht nur Überschriften
3. Erstelle eine tiefgehende Analyse im Markdown-Format basierend auf den gefundenen Quellen

### Hintergrund & Einordnung
Was passiert gerade? Historischer Kontext, beteiligte Akteure, bisheriger Verlauf.

### Aktuelle Entwicklung
Was ist neu? Basierend auf den Suchergebnissen UND den Headlines.

### Szenarien (nächste 4-6 Wochen)
- **Positiv:** Was könnte sich verbessern?
- **Negativ:** Was könnte eskalieren?
- **Wahrscheinlichstes:** Was ist am realistischsten?

### Portfolio-Auswirkungen
Konkrete Auswirkungen auf den MSCI World ETF. Welche Sektoren/Regionen sind betroffen?

### Beobachtungspunkte
Was sollte der Anleger in den nächsten Tagen/Wochen beobachten?

### Quellen
Liste die wichtigsten Quellen auf die du gefunden hast (Titel + URL).

**Relevanz-Zusammenfassung:** Ein Satz der die Kernaussage für die Ampel-Analyse zusammenfasst.

## REGELN
- Alle Texte auf Deutsch
- Einfache, verständliche Sprache — keine Fachkürzel oder Paragraphen-Nummern
- Faktenbasiert — beziehe dich auf konkrete Quellen aus der Web-Suche
- Konkret: Nenne Zahlen, Daten, Zeiträume wenn möglich
- Max. 4-6 Wochen Zeithorizont für Szenarien
- Suche nach aktuellen Nachrichten, Analysen und Experteneinschätzungen zum Thema
- Suche auf Deutsch UND Englisch für bessere Abdeckung\
"""


def deep_research_news_topic(topic_doc, headline_result, market_context=None, previous_results=None):
    """Führt eine tiefgehende Analyse zu einem News-Topic durch mit Web-Suche.

    Nutzt die Anthropic Web Search API um aktuelle Nachrichten und Analysen
    zum Thema zu finden und daraus eine fundierte Deep Research zu erstellen.

    Args:
        topic_doc: MongoDB-Dokument des Topics (mit prompt, title)
        headline_result: Ergebnis der Headline-Analyse (summary, trend, etc.)
        market_context: Optional, letzte Analyse als String
        previous_results: Optional, Liste bisheriger Analysen (neueste zuerst)

    Returns:
        Markdown-String mit der Deep-Research-Analyse, oder None bei Fehler
    """
    import os
    from datetime import datetime as _dt

    parts = [
        f"## THEMA: {topic_doc['title']}",
        "",
        "## ANALYSE-FOKUS",
        topic_doc.get("prompt", "Allgemeine Analyse"),
        "",
        f"Suche nach aktuellen Nachrichten zum Thema '{topic_doc['title']}' und erstelle eine tiefgehende Analyse.",
        "",
        "## HEUTIGE HEADLINE-ANALYSE (aus RSS-Feeds)",
        f"Trend: {headline_result.get('trend', 'stable')}",
        f"Zusammenfassung: {headline_result.get('summary', 'Keine')}",
    ]

    if headline_result.get("relevant_headlines"):
        parts.append("\nRelevante Headlines:")
        for h in headline_result["relevant_headlines"]:
            sentiment = h.get("sentiment", "neutral")
            parts.append(f"  - [{sentiment}] {h.get('title', '?')}")

    if headline_result.get("triggers_detected"):
        parts.append(f"\nErkannte Trigger: {', '.join(headline_result['triggers_detected'])}")

    if previous_results:
        parts.extend(["", f"## BISHERIGE ANALYSEN (letzte {len(previous_results)} Tage)"])
        for prev in previous_results:
            parts.append(f"- {prev['date']}: {prev.get('trend', '?')} — {prev.get('summary', '')}")

    if market_context:
        parts.extend(["", "## MARKTKONTEXT", market_context])

    system = NEWS_DEEP_RESEARCH_SYSTEM.format(today=_dt.now().strftime("%Y-%m-%d"))
    user_prompt = "\n".join(parts)

    # Try Anthropic Web Search first, fall back to regular LLM call
    provider = os.environ.get("ARGUS_LLM_PROVIDER", "anthropic")
    api_key = os.environ.get("ARGUS_LLM_API_KEY")
    model = os.environ.get("ARGUS_LLM_MODEL", "claude-sonnet-4-5-20250929")

    if provider == "anthropic" and api_key:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            log.info("Deep-Research mit Web-Suche für: %s", topic_doc["title"])

            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }],
            )

            # Extract text and source URLs from response content blocks
            text_parts = []
            source_urls = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                # Collect URLs from web search results
                if block.type == "web_search_tool_result":
                    for item in getattr(block, "content", []):
                        if hasattr(item, "url") and hasattr(item, "title"):
                            source_urls.append({"title": item.title, "url": item.url})

            result_text = "".join(text_parts).strip()

            # Append sources section if URLs were found and not already in text
            if result_text and source_urls and "Quellen" not in result_text:
                seen = set()
                unique_sources = []
                for s in source_urls:
                    if s["url"] not in seen:
                        seen.add(s["url"])
                        unique_sources.append(s)
                if unique_sources:
                    result_text += "\n\n### Quellen\n"
                    for s in unique_sources[:10]:
                        result_text += f"- [{s['title']}]({s['url']})\n"

            if result_text:
                log.info("Deep-Research mit Web-Suche abgeschlossen: %d Zeichen, %d Blöcke, %d Quellen",
                         len(result_text), len(text_parts), len(source_urls))
                return result_text
            return None

        except Exception as e:
            log.warning("Web-Search Deep-Research fehlgeschlagen, Fallback auf regulären LLM-Call: %s", e)

    # Fallback: regulärer LLM-Call ohne Web-Suche
    try:
        from ampel_auto import call_llm
        return call_llm(system, user_prompt, temperature=0.3)
    except Exception as e:
        log.error("Deep-Research fehlgeschlagen für %s: %s", topic_doc.get("topic", "?"), e)
        return None


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
            entry = (
                f"### {prev['date']} — Trend: {prev.get('trend', '?')}\n"
                f"Zusammenfassung: {prev.get('summary', '')}\n"
                f"Trigger: {triggers}"
            )
            if prev.get("development"):
                entry += f"\nNeue Entwicklung: {prev['development']}"
            if prev.get("recurring"):
                entry += f"\nBestätigt sich: {prev['recurring']}"
            parts.append(entry)

    if market_context:
        parts.extend(["", "## MARKTKONTEXT", market_context])

    user_prompt = "\n".join(parts)
    llm_text = call_llm(NEWS_ANALYSIS_SYSTEM, user_prompt, temperature=0)

    try:
        result = extract_json(llm_text)
        result["_raw_text"] = llm_text
        return result
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

    # Headline-Analyse durchführen
    log.info("News-Analyse starten: %s (%d bisherige Ergebnisse)", topic["title"], len(previous_results))
    result = analyze_news_topic(topic, headlines, market_context, previous_results)

    # Deep Research durchführen
    log.info("Deep-Research starten: %s", topic["title"])
    deep_research = deep_research_news_topic(topic, result, market_context, previous_results)
    if deep_research:
        log.info("Deep-Research abgeschlossen: %s (%d Zeichen)", topic["title"], len(deep_research))

    # Ergebnis speichern
    today = datetime.now().strftime("%Y-%m-%d")
    doc = {
        "topic": topic_slug,
        "date": today,
        "headlines_fetched": len(headlines),
        "relevant_headlines": result.get("relevant_headlines", []),
        "sentiment_count": result.get("sentiment_count", {}),
        "summary": result.get("summary", ""),
        "development": result.get("development", ""),
        "recurring": result.get("recurring", ""),
        "trend": result.get("trend", "stable"),
        "trend_reasoning": result.get("trend_reasoning", ""),
        "triggers_detected": result.get("triggers_detected", []),
        "ampel_relevance": result.get("ampel_relevance", ""),
        "deep_research": deep_research,
        "raw_headlines": headlines,
        "created_date": datetime.now().isoformat(),
    }

    # Upsert: wenn für heute schon ein Ergebnis existiert, überschreiben
    db.news_results.update_one(
        {"topic": topic_slug, "date": today},
        {"$set": doc},
        upsert=True,
    )

    log.info("News-Ergebnis gespeichert: %s - %s", topic["title"], result.get("trend", "?"))
    return doc


def run_all_news_topics(db):
    """Führt die News-Analyse für alle aktiven Topics durch.

    Default-Headlines werden einmal geholt und für Topics ohne eigene Feeds geteilt.
    Topics mit eigenen Feeds holen ihre Headlines separat.

    Returns:
        Anzahl der erfolgreich analysierten Topics
    """
    topics = list(db.news_topics.find({"active": True}))
    if not topics:
        log.info("Keine aktiven News-Topics")
        return 0

    # Topics aufteilen: mit eigenen Feeds vs. Default-Feeds
    default_topics = [t for t in topics if not t.get("rss_feeds")]
    custom_topics = [t for t in topics if t.get("rss_feeds")]

    # Default-Headlines einmal für alle Topics ohne eigene Feeds holen
    default_headlines = None
    if default_topics:
        default_headlines = fetch_rss_headlines()
        log.info("%d Default-Headlines für %d Topics geholt", len(default_headlines), len(default_topics))

    count = 0
    for topic in topics:
        try:
            # Topics mit eigenen Feeds: headlines=None → run_news_topic holt sie selbst
            headlines = default_headlines if not topic.get("rss_feeds") else None
            result = run_news_topic(db, topic["topic"], headlines=headlines)
            if result:
                count += 1
                print(f"  News: {topic['title']} → {result.get('trend', '?')}")
        except Exception as e:
            log.error("News-Topic %s fehlgeschlagen: %s", topic["topic"], e)

    return count
