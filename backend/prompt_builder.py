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


def build_theses_context(theses: list) -> list[str]:
    """Build open theses lines."""
    if not theses:
        return []

    lines = ["", "## OFFENE THESEN"]
    for t in theses:
        cat_info = ""
        if t.get("catalyst_date"):
            cat_info = f" (Katalysator: {t['catalyst_date']})"
        lines.append(f"- [{t['created_date']}] {t['statement']}{cat_info}")

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
    lines.extend(build_signals_context(market, mech_signals, mech_score))
    lines.extend(build_history_context(history))
    lines.extend(build_theses_context(theses))
    lines.extend(build_research_context(researches or []))
    lines.extend(build_news_context(news_results or []))

    return "\n".join(lines)
