"""Opportunity Scanner — Findet Aktien aus Konsolidierung mit starkem Analysten-Konsens."""

import json
import logging
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..llm import call_llm, stream_llm

log = logging.getLogger("argus")

router = APIRouter()

# ── Stock Universe ───────────────────────────────────────────────────────

# Breites Universum: S&P 500 Top-Werte + Growth + Value + Recovery-Kandidaten
SCAN_UNIVERSE = [
    # Tech Mega-Caps
    "AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "CRM",
    "AMD", "INTC", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "MRVL", "MU", "SNPS",
    "ADBE", "NOW", "INTU", "PANW", "CRWD", "FTNT", "DDOG", "ZS", "NET", "SNOW",
    # Finanz
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V", "MA", "PYPL",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "AMGN", "GILD",
    "ISRG", "VRTX", "REGN", "BMY", "MDT",
    # Industrie & Konsum
    "CAT", "DE", "HON", "GE", "RTX", "BA", "LMT", "UPS", "FDX",
    "COST", "WMT", "TGT", "HD", "LOW", "NKE", "SBUX", "MCD", "DIS",
    # Energie & Rohstoffe
    "XOM", "CVX", "COP", "SLB", "EOG", "FCX", "NEM",
    # Kommunikation
    "NFLX", "SPOT", "UBER", "ABNB", "BKNG", "APP",
    # Versorger & REITs
    "NEE", "SO", "DUK", "AMT", "PLD", "SPG",
    # Recovery / Turnaround Kandidaten
    "COIN", "RIVN", "LCID", "SOFI", "PLTR", "RBLX", "U", "SNAP", "PINS",
    "SQ", "SHOP", "SE", "MELI", "GRAB", "CPNG",
]


# ── Screening Logic ─────────────────────────────────────────────────────

def _screen_single_stock(ticker: str):
    """Screen a single stock for consolidation breakout potential.

    Returns dict with scores or None if data unavailable.
    """
    import yfinance as yf
    import math

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y")
        if hist.empty or len(hist) < 50:
            return None

        close = hist["Close"]
        current = float(close.iloc[-1])

        # SMAs
        sma50 = close.rolling(50).mean()
        sma50_val = float(sma50.iloc[-1])
        sma200_val = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

        # Consolidation metrics
        recent_20 = close.iloc[-20:]
        range_20d = float((recent_20.max() - recent_20.min()) / recent_20.mean() * 100)

        # ATH distance
        ath = float(close.max())
        pct_from_ath = float((current / ath - 1) * 100)

        # SMA distances
        pct_vs_sma50 = float((current / sma50_val - 1) * 100)
        pct_vs_sma200 = float((current / sma200_val - 1) * 100) if sma200_val else None

        # Volume trend (last 5 days vs 20-day avg)
        vol = hist["Volume"]
        vol_5d = float(vol.iloc[-5:].mean())
        vol_20d = float(vol.iloc[-20:].mean())
        vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0

        # Analyst recommendations
        recs = t.recommendations
        analyst = {"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}
        if recs is not None and not recs.empty:
            current_row = recs[recs["period"] == "0m"]
            if not current_row.empty:
                r = current_row.iloc[0]
                analyst = {k: int(r.get(k, 0)) for k in analyst}

        total_analysts = sum(analyst.values())
        buy_pct = (analyst["strongBuy"] + analyst["buy"]) / total_analysts * 100 if total_analysts > 0 else 0

        # ── Scoring ──────────────────────────────────────────────────
        score = 0

        # 1. Konsolidierung: Kurs deutlich unter ATH (10-40% = sweet spot)
        if -40 <= pct_from_ath <= -10:
            score += 25  # Große Konsolidierung
        elif -50 <= pct_from_ath < -40:
            score += 15  # Sehr stark gefallen
        elif -10 < pct_from_ath <= -5:
            score += 10  # Leichte Korrektur

        # 2. Niedrige Volatilität (enge Range = Konsolidierung)
        if range_20d < 8:
            score += 15  # Enge Konsolidierung
        elif range_20d < 12:
            score += 10

        # 3. Analysten bullish
        if buy_pct >= 80:
            score += 25
        elif buy_pct >= 60:
            score += 15
        elif buy_pct >= 40:
            score += 5

        # 4. Kurs nahe/über SMA50 (Stabilisierung)
        if -3 <= pct_vs_sma50 <= 5:
            score += 15  # Nahe SMA50 = potentieller Breakout
        elif pct_vs_sma50 > 5:
            score += 5   # Schon darüber

        # 5. SMA50 über SMA200 (Golden Cross)
        if sma200_val and sma50_val > sma200_val:
            score += 10

        # 6. Volume pickup (Interesse steigt)
        if vol_ratio > 1.2:
            score += 10

        info = t.info or {}

        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector", ""),
            "price": round(current, 2),
            "pct_from_ath": round(pct_from_ath, 1),
            "range_20d": round(range_20d, 1),
            "pct_vs_sma50": round(pct_vs_sma50, 1),
            "pct_vs_sma200": round(pct_vs_sma200, 1) if pct_vs_sma200 is not None else None,
            "vol_ratio": round(vol_ratio, 2),
            "analyst": analyst,
            "total_analysts": total_analysts,
            "buy_pct": round(buy_pct, 1),
            "score": score,
            "market_cap": info.get("marketCap"),
        }
    except Exception as e:
        log.debug("Screening %s fehlgeschlagen: %s", ticker, e)
        return None


def run_stock_screen(max_workers: int = 10):
    """Screen all stocks in universe, return sorted by score."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_screen_single_stock, t): t for t in SCAN_UNIVERSE}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result and result["score"] > 0:
                    results.append(result)
            except Exception as e:
                log.debug("Screen %s error: %s", ticker, e)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ── LLM Research ─────────────────────────────────────────────────────────

SCANNER_RESEARCH_SYSTEM = """\
Du bist der Opportunity-Analyst des Argus Investment-Systems.

## HEUTIGES DATUM
{today}

## DEINE AUFGABE
Du erhältst die Top-10 Aktien aus einem quantitativen Screening nach:
- Große Konsolidierung (deutlich unter ATH)
- Starker Analysten-Konsens (hoher Buy-Anteil)
- Stabilisierung am SMA50 (potentieller Breakout)
- Steigende Volumen-Aktivität

Erstelle für JEDE der 10 Aktien eine kurze Research-Analyse.

## AUSGABE
Antworte AUSSCHLIESSLICH mit JSON:
{{
  "scan_date": "{today}",
  "market_summary": "2-3 Sätze: Aktuelles Marktumfeld für Recovery-Plays",
  "opportunities": [
    {{
      "ticker": "SYMBOL",
      "rank": 1,
      "thesis": "1-2 Sätze: Warum ist diese Aktie ein guter Recovery-Kandidat?",
      "catalyst": "Was könnte den Breakout auslösen?",
      "risk": "Größtes Risiko",
      "target_upside_pct": 15,
      "timeframe": "3-6 Monate",
      "conviction": "high|medium|low"
    }}
  ]
}}

## REGELN
- Alle Texte auf Deutsch
- Sei realistisch bei target_upside_pct — basierend auf ATH-Abstand und Fundamentaldaten
- conviction: high = starke Fundamentaldaten + technischer Setup, medium = gute Chance aber Risiken, low = spekulativ
- Ordne die 10 Aktien nach deiner Einschätzung (beste zuerst), nicht nach dem quantitativen Score
- Berücksichtige dein Wissen über aktuelle Quartalszahlen, Geschäftsmodell, Marktposition\
"""


def research_top_opportunities(top10: list) -> dict:
    """LLM research on top 10 screened stocks."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Build context for LLM
    lines = []
    for i, s in enumerate(top10, 1):
        analyst_str = (
            f"Strong Buy: {s['analyst']['strongBuy']}, Buy: {s['analyst']['buy']}, "
            f"Hold: {s['analyst']['hold']}, Sell: {s['analyst']['sell']}"
        )
        lines.append(
            f"{i}. {s['ticker']} ({s['name']}) — {s['sector']}\n"
            f"   Kurs: ${s['price']} | ATH-Abstand: {s['pct_from_ath']}% | "
            f"SMA50: {s['pct_vs_sma50']}% | Range 20d: {s['range_20d']}%\n"
            f"   Analysten ({s['total_analysts']}): {analyst_str} → {s['buy_pct']}% Buy\n"
            f"   Volumen-Ratio: {s['vol_ratio']}x | Score: {s['score']}"
        )

    user_prompt = "## TOP-10 SCREENING-ERGEBNISSE\n\n" + "\n\n".join(lines)

    system = SCANNER_RESEARCH_SYSTEM.format(today=today)
    from ampel_auto import extract_json

    llm_text = call_llm(system, [{"role": "user", "content": user_prompt}], max_tokens=4096)
    return extract_json(llm_text)


# ── Orchestrator ─────────────────────────────────────────────────────────

def run_opportunity_scan(db=None):
    """Full scan: screen universe → research top 10 → save to DB."""
    if db is None:
        db = get_db()

    date_str = datetime.now().strftime("%Y-%m-%d")
    log.info("Opportunity-Scan gestartet für %s", date_str)

    # 1. Screen
    all_results = run_stock_screen()
    log.info("Screening abgeschlossen: %d Aktien bewertet", len(all_results))

    if len(all_results) < 10:
        log.warning("Nur %d Aktien gescreent, zu wenig für Top-10", len(all_results))

    top10 = all_results[:10]

    # 2. LLM Research
    try:
        research = research_top_opportunities(top10)
    except Exception as e:
        log.error("Opportunity-Research fehlgeschlagen: %s", e)
        research = {"scan_date": date_str, "market_summary": f"Research fehlgeschlagen: {e}", "opportunities": []}

    # 3. Merge screen data with research
    research_map = {}
    for opp in research.get("opportunities", []):
        research_map[opp.get("ticker", "")] = opp

    opportunities = []
    for s in top10:
        r = research_map.get(s["ticker"], {})
        opportunities.append({
            **s,
            "thesis": r.get("thesis", ""),
            "catalyst": r.get("catalyst", ""),
            "risk": r.get("risk", ""),
            "target_upside_pct": r.get("target_upside_pct"),
            "timeframe": r.get("timeframe", ""),
            "conviction": r.get("conviction", "medium"),
            "rank": r.get("rank", 0),
        })

    # Sort by LLM rank if available
    opportunities.sort(key=lambda x: x.get("rank") or 99)

    doc = {
        "date": date_str,
        "market_summary": research.get("market_summary", ""),
        "total_screened": len(all_results),
        "opportunities": opportunities,
        "all_scores": [{"ticker": s["ticker"], "score": s["score"], "buy_pct": s["buy_pct"],
                        "pct_from_ath": s["pct_from_ath"]} for s in all_results[:30]],
        "updated_at": datetime.now().isoformat(),
    }

    db.opportunity_scans.update_one(
        {"date": date_str},
        {"$set": doc},
        upsert=True,
    )

    # Index for search
    try:
        from ..embeddings import get_collection
        col = get_collection("opportunity_scans")
        text_parts = [f"Opportunity Scan {date_str}", research.get("market_summary", "")]
        for o in opportunities:
            text_parts.append(f"{o['ticker']} ({o.get('name','')}): {o.get('thesis','')}")
        col.upsert(
            ids=[date_str],
            documents=["\n".join(text_parts)[:2000]],
            metadatas=[{"date": date_str, "count": str(len(opportunities))}],
        )
    except Exception as e:
        log.warning("Scan-Indizierung fehlgeschlagen: %s", e)

    log.info("Opportunity-Scan gespeichert: %d Chancen", len(opportunities))
    return doc


# ── API Endpoints ────────────────────────────────────────────────────────

def _sse_event(event: str, data):
    """Format a Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/run")
def run_scan():
    """Run opportunity scan with SSE streaming."""
    def generate():
        try:
            db = get_db()
            date_str = datetime.now().strftime("%Y-%m-%d")

            yield _sse_event("status", f"Starte Opportunity-Scan für {date_str}...")

            # 1. Screen
            yield _sse_event("status", f"Screene {len(SCAN_UNIVERSE)} Aktien...")
            all_results = run_stock_screen()
            yield _sse_event("status", f"{len(all_results)} Aktien bewertet. Top-10 werden analysiert...")

            top10 = all_results[:10]

            # Emit screening results
            yield _sse_event("screening", {
                "total": len(all_results),
                "top10": [{
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "score": s["score"],
                    "price": s["price"],
                    "pct_from_ath": s["pct_from_ath"],
                    "buy_pct": s["buy_pct"],
                } for s in top10],
            })

            # 2. LLM Research
            yield _sse_event("status", "LLM-Research für Top-10...")
            try:
                research = research_top_opportunities(top10)
            except Exception as e:
                yield _sse_event("status", f"Research fehlgeschlagen: {e}")
                research = {"market_summary": str(e), "opportunities": []}

            # 3. Merge & save
            research_map = {o.get("ticker", ""): o for o in research.get("opportunities", [])}
            opportunities = []
            for s in top10:
                r = research_map.get(s["ticker"], {})
                opportunities.append({
                    **s,
                    "thesis": r.get("thesis", ""),
                    "catalyst": r.get("catalyst", ""),
                    "risk": r.get("risk", ""),
                    "target_upside_pct": r.get("target_upside_pct"),
                    "timeframe": r.get("timeframe", ""),
                    "conviction": r.get("conviction", "medium"),
                    "rank": r.get("rank", 0),
                })
            opportunities.sort(key=lambda x: x.get("rank") or 99)

            doc = {
                "date": date_str,
                "market_summary": research.get("market_summary", ""),
                "total_screened": len(all_results),
                "opportunities": opportunities,
                "all_scores": [{"ticker": s["ticker"], "score": s["score"], "buy_pct": s["buy_pct"],
                                "pct_from_ath": s["pct_from_ath"]} for s in all_results[:30]],
                "updated_at": datetime.now().isoformat(),
            }

            db.opportunity_scans.update_one({"date": date_str}, {"$set": doc}, upsert=True)
            yield _sse_event("status", "Scan gespeichert.")

            yield _sse_event("done", {
                "date": date_str,
                "total_screened": len(all_results),
                "market_summary": research.get("market_summary", ""),
                "opportunities": opportunities,
            })

        except Exception as e:
            log.error("Opportunity-Scan fehlgeschlagen: %s", e, exc_info=True)
            yield _sse_event("error", str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/latest")
def get_latest_scan():
    """Get the latest opportunity scan."""
    db = get_db()
    doc = db.opportunity_scans.find_one(sort=[("date", -1)])
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/history")
def get_scan_history(limit: int = 10):
    """Get scan history (without full opportunity details)."""
    db = get_db()
    docs = list(
        db.opportunity_scans.find(
            {},
            {"opportunities": {"$slice": 3}, "all_scores": 0},
        ).sort("date", -1).limit(limit)
    )
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs
