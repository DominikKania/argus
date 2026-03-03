"""Prompt builder module for Ampel analysis.

Builds the user prompt from market data, research syntheses, news context,
and analysis history. Used by both ampel_auto.py (CLI) and the /ampel/prompts
API endpoint.
"""

from datetime import datetime
from typing import Optional


def build_research_context(researches: list) -> list[str]:
    """Build research context lines from completed researches.

    Uses the condensed synthesis instead of raw results.
    """
    if not researches:
        return []

    lines = [
        "",
        "## RESEARCH-KONTEXT",
        "Folgende Deep-Research-Ergebnisse liegen vor und sollten in die Analyse einfließen:",
    ]

    for r in researches:
        lines.append(f"\n### {r['title']}")

        summary = r.get("relevance_summary")
        if summary:
            lines.append(f"Relevanz für IWDA: {summary}")

        # Use synthesis (condensed expert summary) instead of raw results
        synthesis = r.get("synthesis") or ""
        if not synthesis:
            # Extract synthesis from results if not stored separately
            results = r.get("results") or ""
            if results:
                idx = results.find("## Synthese & Fazit")
                if idx >= 0:
                    synthesis = results[idx + len("## Synthese & Fazit"):].strip()

        if synthesis:
            lines.append(f"Synthese:\n{synthesis}")

    return lines


def build_news_context(news_results: list) -> list[str]:
    """Build news context lines from latest news analysis results.

    Uses structured summary fields plus deep_research (full analysis
    from web search) — same pattern as research synthesis.
    """
    if not news_results:
        return []

    lines = [
        "",
        "## NEWS-KONTEXT (tagesaktuelle Analysen via RSS + Web-Search)",
        "Folgende News-Analysen liegen vor und sollten in die Analyse einfließen:",
    ]

    for nr in news_results:
        trend = nr.get("trend", "stable")
        topic_title = nr.get("title") or nr.get("topic", "?")
        lines.append(f"\n### {topic_title} — Trend: {trend}")

        # Structured summary fields (always present)
        if nr.get("development"):
            lines.append(f"Neue Entwicklung: {nr['development']}")
        if nr.get("recurring"):
            lines.append(f"Bestätigt sich: {nr['recurring']}")
        if nr.get("summary"):
            lines.append(f"Einordnung: {nr['summary']}")
        triggers = nr.get("triggers_detected", [])
        if triggers:
            lines.append(f"Trigger: {', '.join(triggers)}")
        relevance = nr.get("ampel_relevance", "")
        if relevance:
            lines.append(f"Ampel-Relevanz: {relevance}")

        # Deep research (full web-search analysis) — like research synthesis
        deep = nr.get("deep_research") or ""
        if deep:
            lines.append(f"Deep-Research:\n{deep}")

    return lines


def build_market_context(market: dict) -> list[str]:
    """Build market data lines from yfinance data."""
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
        month_names = {
            1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez",
        }
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

    # EUR/USD
    eur = market.get("eurusd")
    if eur:
        dir_label = (
            "EUR stärker" if eur["direction"] == "rising"
            else "USD stärker" if eur["direction"] == "falling"
            else "stabil"
        )
        lines.append("")
        lines.append("## EUR/USD WECHSELKURS")
        lines.append(f"- Kurs: {eur['rate']:.4f}")
        lines.append(f"- 1-Monats-Veränderung: {eur['change_1m_pct']:+.2f}%")
        lines.append(f"- Richtung: {eur['direction']} ({dir_label})")

    # Öl (Brent)
    oil = market.get("oil")
    if oil:
        lines.append("")
        lines.append("## ÖL (Brent Crude)")
        lines.append(f"- Preis: ${oil['price']}")
        lines.append(f"- 1-Monats-Veränderung: {oil['change_1m_pct']:+.2f}%")
        lines.append(f"- Richtung: {oil['direction']}")

    # Gold
    gold = market.get("gold")
    if gold:
        lines.append("")
        lines.append("## GOLD")
        lines.append(f"- Preis: ${gold['price']}")
        lines.append(f"- 1-Monats-Veränderung: {gold['change_1m_pct']:+.2f}%")
        lines.append(f"- Richtung: {gold['direction']}")

    # US Dollar Index
    dxy = market.get("dxy")
    if dxy:
        lines.append("")
        lines.append("## US DOLLAR INDEX (DXY)")
        lines.append(f"- Wert: {dxy['value']}")
        lines.append(f"- 1-Monats-Veränderung: {dxy['change_1m_pct']:+.2f}%")
        lines.append(f"- Richtung: {dxy['direction']}")

    # Credit Spread
    cs = market.get("credit_spread")
    if cs:
        lines.append("")
        lines.append("## CREDIT SPREAD (HYG vs LQD, 1-Monats-Performance)")
        lines.append(f"- HYG (High Yield): {cs['hyg_price']}$ ({cs['hyg_perf_1m']:+.2f}%)")
        lines.append(f"- LQD (Inv. Grade): {cs['lqd_price']}$ ({cs['lqd_perf_1m']:+.2f}%)")
        lines.append(f"- Spread-Proxy (HYG-LQD Perf.): {cs['spread_proxy']:+.2f}pp ({cs['direction']})")

    # Top Holdings
    th = market.get("top_holdings")
    if th and th.get("holdings"):
        lines.append("")
        lines.append(f"## TOP-HOLDINGS ({th['above_sma50_count']}/{th['total_count']} über SMA50)")
        for h in th["holdings"]:
            sma_status = ""
            if h.get("above_sma50") is True:
                sma_status = " ✓ >SMA50"
            elif h.get("above_sma50") is False:
                sma_status = " ✗ <SMA50"
            lines.append(
                f"- {h['name']} ({h['ticker']}, {h['sector']}, {h['weight_pct']}%): "
                f"${h['price']} | 1M: {h['perf_1m_pct']:+.1f}%{sma_status}"
            )

    return lines


def build_earnings_context(market: dict) -> list[str]:
    """Build earnings season context from aggregated top-15 holdings data."""
    earn = market.get("earnings")
    if not earn:
        return []

    lines = [
        "",
        "## EARNINGS SEASON (Top-15 MSCI World Holdings, aggregiert)",
        f"- Beat Rate: {earn['beat_rate']} ({earn['beat_rate_pct']:.0f}%)",
        f"- Ø Earnings Surprise: {earn['avg_surprise_pct']:+.1f}%",
    ]

    if earn.get("fwd_eps_growth_0y") is not None:
        lines.append(f"- Forward EPS Growth (lfd. Jahr): {earn['fwd_eps_growth_0y']*100:+.1f}%")

    lines.extend([
        f"- Revisions-Momentum (30d): {earn['revision_direction']} (netto {earn['net_revisions_30d']:+d})",
        f"- Revisions-Momentum (7d): netto {earn['net_revisions_7d']:+d}",
        f"- Earnings Health: {earn['earnings_health']}",
    ])

    # Sektor-Aufschlüsselung
    by_sector = earn.get("by_sector", {})
    if by_sector:
        lines.append("")
        lines.append("### Sektor-Aufschlüsselung")
        for sector, data in by_sector.items():
            fwd = f"FWD Growth {data['fwd_eps_growth']*100:+.1f}%" if data.get("fwd_eps_growth") is not None else "FWD Growth n/a"
            lines.append(
                f"- {sector}: Beat {data['beat_rate']} ({data['beat_rate_pct']:.0f}%) | "
                f"Surprise {data['avg_surprise_pct']:+.1f}% | "
                f"{fwd} | Revisions: {data['revision_direction']}"
            )

    # Anstehende Earnings (Event-Risiko)
    upcoming = earn.get("upcoming", [])
    if upcoming:
        lines.append("")
        lines.append("### Anstehende Earnings (Event-Risiko)")
        for u in upcoming[:5]:
            lines.append(f"- {u['ticker']} ({u['sector']}): {u['date']}")

    # Kürzlich gemeldet
    recently = earn.get("recently_reported", [])
    if recently:
        lines.append("")
        lines.append("### Kürzlich gemeldet")
        for r in recently[:5]:
            lines.append(f"- {r['ticker']} ({r['sector']}): Surprise {r['surprise_pct']:+.1f}%")

    return lines


def build_signals_context(market: dict, mech_signals: dict, mech_score: int) -> list[str]:
    """Build mechanical signals summary lines."""
    vix = market["vix"]
    yld = market["yields"]

    return [
        "",
        "## ZUSÄTZLICHER KONTEXT (aus deinem Marktwissen)",
        "Bewerte folgende Punkte basierend auf deinem aktuellen Wissen:",
        "- Advance/Decline-Line: Ist die Marktbreite gesund oder divergiert sie vom Index?",
        "- New Highs vs. New Lows: Gibt es Anzeichen für breite Schwäche?",
        "- ETF-Flows (MSCI World / IWDA): Gibt es Anzeichen für Zu- oder Abflüsse?",
        "- Margin Debt: Gibt es Berichte über erhöhte oder fallende Margin-Schulden?",
        "",
        "## MECHANISCHE SIGNALE (berechnet)",
        f"- Trend: {mech_signals['trend']} (Kurs {'über' if market['price'] > market['sma50'] else 'unter'} SMA50)",
        f"- Volatilität: {mech_signals['volatility']} (VIX {vix['value']})",
        f"- Makro: {mech_signals['macro']} (Spread {yld['spread']}%)",
        f"- Sentiment: noch zu bewerten",
        f"- Mechanischer Score: {mech_score}/4 (ohne Sentiment)",
    ]


def build_history_context(history: list) -> list[str]:
    """Build analysis history lines."""
    if not history:
        return []

    lines = ["", "## LETZTE ANALYSEN"]

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

        thesis = doc.get("thesis")
        if thesis and thesis.get("statement"):
            lines.append(f"  These: {thesis['statement']}")

        trigger = doc.get("escalation_trigger")
        if trigger:
            lines.append(f"  Trigger: {trigger}")

    return lines


def build_lessons_context(lessons: list) -> list[str]:
    """Build lessons learned from resolved theses for the synthesis prompt."""
    if not lessons:
        return []

    lines = [
        "",
        "## ERKENNTNISSE AUS FRÜHEREN THESEN",
        "Diese Regeln stammen aus aufgelösten Thesen. Berücksichtige sie in deiner Analyse:",
    ]
    for lesson in lessons:
        statement = lesson.get("statement", "")
        learned = lesson.get("lessons_learned", "")
        if learned:
            lines.append(f"\n- **{statement[:80]}:** {learned}")
    return lines


def build_theses_context(theses: list) -> list[str]:
    """Build open theses lines with IDs and full detail for duplicate avoidance and resolution."""
    if not theses:
        return []

    lines = [
        "",
        "## OFFENE THESEN",
        "Prüfe jede These: Ist sie durch die aktuellen Marktdaten bestätigt/widerlegt?",
        "Falls ja → in thesis_resolutions aufnehmen. Keine Duplikate als neue These erstellen!",
    ]
    for t in theses:
        tid = str(t.get("_id", ""))
        lines.append(f"\n### These [{tid}] — erstellt {t['created_date']}")
        lines.append(f"Statement: {t['statement']}")
        if t.get("catalyst"):
            lines.append(f"Katalysator: {t['catalyst']}")
        if t.get("catalyst_date"):
            lines.append(f"Katalysator-Datum: {t['catalyst_date']}")
        if t.get("expected_if_positive"):
            lines.append(f"Wenn positiv: {t['expected_if_positive']}")
        if t.get("expected_if_negative"):
            lines.append(f"Wenn negativ: {t['expected_if_negative']}")
        prob = t.get("probability_positive_pct")
        if prob is not None:
            lines.append(f"Aktuelle Wahrscheinlichkeit positiv: {prob}%")
            reasoning = t.get("probability_reasoning", "")
            if reasoning:
                lines.append(f"Begründung: {reasoning}")

    return lines


def build_user_prompt(
    market: dict,
    mech_signals: dict,
    mech_score: int,
    history: list,
    theses: list,
    researches: Optional[list] = None,
    news_results: Optional[list] = None,
) -> str:
    """Build the complete user prompt for Ampel analysis.

    Assembles market data, mechanical signals, history, theses,
    research syntheses, and news context into a single prompt string.
    """
    lines = build_market_context(market)
    lines.extend(build_earnings_context(market))
    lines.extend(build_signals_context(market, mech_signals, mech_score))
    lines.extend(build_history_context(history))
    lines.extend(build_theses_context(theses))
    lines.extend(build_research_context(researches or []))
    lines.extend(build_news_context(news_results or []))

    return "\n".join(lines)


# ── Per-Stage Prompt Builders (Multi-Stage Architecture) ─────────────────


def _filter_researches_for(researches: list, target: str) -> list:
    """Filter researches that are assigned to a specific ampel target."""
    if not researches:
        return []
    return [r for r in researches if target in (r.get("ampel_targets") or [])]


def build_trend_analyst_prompt(market: dict, mech_signals: dict, researches: Optional[list] = None) -> str:
    """Build user prompt for the Trend signal analyst."""
    lines = [
        f"Bewerte das Trend-Signal für {datetime.now().strftime('%Y-%m-%d')}.",
        "",
        "## MARKTDATEN",
        f"- IWDA Kurs: {market['price']}€ | SMA50: {market['sma50']}€ | SMA200: {market['sma200']}€",
        f"- ATH: {market['ath']}€ | Delta ATH: {market['delta_ath_pct']}%",
        f"- Puffer SMA50: {market['puffer_sma50_pct']}%",
        f"- Golden Cross: {'Ja' if market['golden_cross'] else 'Nein'}",
        "",
        "## MECHANISCHES SIGNAL",
        f"- Trend: {mech_signals['trend']} (Kurs {'über' if market['price'] > market['sma50'] else 'unter'} SMA50)",
    ]

    sr = market.get("sector_rotation")
    if sr and sr.get("risk_on_vs_off") is not None:
        lines.append(f"- Risk-On vs. Defensive Spread: {sr['risk_on_vs_off']:+.2f}pp")

    reg = market.get("regional")
    if reg:
        if reg.get("spy_perf_1m") is not None:
            lines.append(f"- USA (SPY) 1M: {reg['spy_perf_1m']:+.2f}%")
        if reg.get("ezu_perf_1m") is not None:
            lines.append(f"- Europa (EZU) 1M: {reg['ezu_perf_1m']:+.2f}%")

    seas = market.get("seasonality")
    if seas:
        lines.append(f"- Saisonaler Bias: {seas['seasonal_bias']} (avg {seas['avg_return_pct']:+.2f}%)")

    targeted = _filter_researches_for(researches or [], "trend")
    lines.extend(build_research_context(targeted))

    return "\n".join(lines)


def build_volatility_analyst_prompt(market: dict, mech_signals: dict, researches: Optional[list] = None) -> str:
    """Build user prompt for the Volatility signal analyst."""
    vix = market["vix"]
    lines = [
        f"Bewerte das Volatilitäts-Signal für {datetime.now().strftime('%Y-%m-%d')}.",
        "",
        "## MARKTDATEN",
        f"- VIX: {vix['value']} (Vorwoche: {vix['prev_week']}, Richtung: {vix['direction']})",
        "",
        "## MECHANISCHES SIGNAL",
        f"- Volatilität: {mech_signals['volatility']} (VIX {vix['value']})",
    ]

    pc = market.get("put_call")
    if pc:
        lines.append(f"- Put/Call Ratio: {pc['ratio']:.2f} ({pc['signal']})")

    targeted = _filter_researches_for(researches or [], "volatility")
    lines.extend(build_research_context(targeted))

    return "\n".join(lines)


def build_macro_analyst_prompt(market: dict, mech_signals: dict, researches: Optional[list] = None) -> str:
    """Build user prompt for the Macro signal analyst."""
    yld = market["yields"]
    lines = [
        f"Bewerte das Makro-Signal für {datetime.now().strftime('%Y-%m-%d')}.",
        "",
        "## MARKTDATEN",
        f"- US 10Y: {yld['us10y']}% | US 2Y: {yld['us2y']}% | Spread: {yld['spread']}% ({yld['spread_direction']})",
        f"- CPI: {yld['cpi']}% | Real Yield: {yld['real_yield']}%",
    ]

    cs = market.get("credit_spread")
    if cs:
        lines.append(f"- Credit Spread Proxy: {cs['spread_proxy']:+.2f}pp ({cs['direction']})")

    oil = market.get("oil")
    if oil:
        lines.append(f"- Öl (Brent): ${oil['price']} ({oil['change_1m_pct']:+.2f}%, {oil['direction']})")

    gold = market.get("gold")
    if gold:
        lines.append(f"- Gold: ${gold['price']} ({gold['change_1m_pct']:+.2f}%, {gold['direction']})")

    dxy = market.get("dxy")
    if dxy:
        lines.append(f"- DXY: {dxy['value']} ({dxy['change_1m_pct']:+.2f}%, {dxy['direction']})")

    eur = market.get("eurusd")
    if eur:
        lines.append(f"- EUR/USD: {eur['rate']:.4f} ({eur['change_1m_pct']:+.2f}%, {eur['direction']})")

    lines.extend([
        "",
        "## MECHANISCHES SIGNAL",
        f"- Makro: {mech_signals['macro']} (Spread {yld['spread']}%)",
    ])

    earn = market.get("earnings")
    if earn:
        lines.extend([
            "",
            "## EARNINGS-KONTEXT",
            f"- Earnings Health: {earn['earnings_health']}",
            f"- Beat Rate: {earn['beat_rate']} ({earn['beat_rate_pct']:.0f}%)",
            f"- Revisions: {earn['revision_direction']}",
        ])

    targeted = _filter_researches_for(researches or [], "macro")
    lines.extend(build_research_context(targeted))

    return "\n".join(lines)


def build_sentiment_analyst_prompt(
    market: dict,
    mech_signals: dict,
    news_results: Optional[list] = None,
    researches: Optional[list] = None,
) -> str:
    """Build user prompt for the Sentiment signal analyst."""
    lines = [
        f"Bewerte das Sentiment-Signal für {datetime.now().strftime('%Y-%m-%d')}.",
    ]

    # News context
    lines.extend(build_news_context(news_results or []))

    # Sector rotation
    sr = market.get("sector_rotation")
    if sr and sr.get("sectors"):
        lines.append("")
        lines.append("## SEKTOR-ROTATION")
        for name, data in sr["sectors"].items():
            lines.append(f"- {name.replace('_', ' ').title()}: {data['perf_1m']:+.2f}%")
        if sr.get("risk_on_vs_off") is not None:
            lines.append(f"- Risk-On vs. Defensive: {sr['risk_on_vs_off']:+.2f}pp")

    # Regional
    reg = market.get("regional")
    if reg and reg.get("usa_vs_europe") is not None:
        lines.append(f"- USA vs Europa: {reg['usa_vs_europe']:+.2f}pp")

    # Put/Call
    pc = market.get("put_call")
    if pc:
        lines.append(f"- Put/Call Ratio: {pc['ratio']:.2f} ({pc['signal']})")

    # Earnings (upcoming + recently reported for event risk)
    lines.extend(build_earnings_context(market))

    targeted = _filter_researches_for(researches or [], "sentiment")
    lines.extend(build_research_context(targeted))

    return "\n".join(lines)


def build_synthesis_prompt(
    market: dict,
    mech_signals: dict,
    mech_score: int,
    stage1_results: dict,
    history: list,
    theses: list,
    researches: Optional[list] = None,
    news_results: Optional[list] = None,
    lessons: Optional[list] = None,
) -> str:
    """Build user prompt for the Synthesis stage.

    Receives all 4 signal assessments from Stage 1 plus broader context
    (history, theses, research, news, lessons) to produce the overall rating.
    """
    lines = [
        f"Erstelle die Gesamt-Synthese für {datetime.now().strftime('%Y-%m-%d')}.",
        "",
        "## SIGNAL-BEWERTUNGEN (von spezialisierten Analysten)",
    ]

    for name in ["trend", "volatility", "macro", "sentiment"]:
        result = stage1_results.get(name) or {}
        ctx = result.get("context", "?")
        note = result.get("note", "-")
        mech = mech_signals[name] if name != "sentiment" else result.get("mechanical", "green")
        lines.append(f"- {name.capitalize()}: mechanical={mech}, context={ctx}")
        lines.append(f"  Begründung: {note}")

        if name == "sentiment":
            events = result.get("events", [])
            for evt in events:
                lines.append(
                    f"  Event: {evt.get('headline', '?')} "
                    f"(Auswirkung: {evt.get('affects_portfolio', '?')}, "
                    f"Kaskadenrisiko: {evt.get('cascade_risk', '?')})"
                )

    # Mechanical score
    sent_mech = (stage1_results.get("sentiment") or {}).get("mechanical", "green")
    actual_score = sum(1 for n in ["trend", "volatility", "macro"] if mech_signals[n] == "green")
    if sent_mech == "green":
        actual_score += 1
    lines.append(f"\n## MECHANISCHER SCORE: {actual_score}/4")

    # Condensed market summary
    vix = market["vix"]
    yld = market["yields"]
    lines.extend([
        "",
        "## MARKT-ZUSAMMENFASSUNG",
        f"- IWDA: {market['price']}€ (ATH-Delta: {market['delta_ath_pct']}%, Puffer SMA50: {market['puffer_sma50_pct']}%)",
        f"- VIX: {vix['value']} ({vix['direction']})",
        f"- Spread: {yld['spread']}% ({yld['spread_direction']}) | Real Yield: {yld['real_yield']}%",
    ])
    cs = market.get("credit_spread")
    if cs:
        lines.append(f"- Credit Spread: {cs['direction']} ({cs['spread_proxy']:+.2f}pp)")

    # Research, News, History, Theses, Lessons
    lines.extend(build_research_context(researches or []))
    lines.extend(build_news_context(news_results or []))
    lines.extend(build_history_context(history))
    lines.extend(build_theses_context(theses))
    lines.extend(build_lessons_context(lessons or []))

    return "\n".join(lines)
