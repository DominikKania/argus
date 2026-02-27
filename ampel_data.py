#!/usr/bin/env python3
"""Ampel-Datensammlung via yfinance + mechanische Signalberechnung."""

import logging
from datetime import datetime, timedelta

import yfinance as yf

log = logging.getLogger("ampel")

# ── Ticker-Konfiguration ─────────────────────────────────────────────────

IWDA_TICKER = "IWDA.AS"   # iShares MSCI World, Euronext Amsterdam (EUR)
VIX_TICKER = "^VIX"
US10Y_TICKER = "^TNX"     # CBOE 10-Year Treasury Note Yield
US2Y_TICKER = "2YY=F"     # 2-Year Treasury Yield Future (Fallback nötig)


# ── Daten holen ──────────────────────────────────────────────────────────

def fetch_iwda_data():
    """IWDA-Kurs, SMAs, ATH und abgeleitete Werte holen."""
    ticker = yf.Ticker(IWDA_TICKER)

    # 2 Jahre für SMA200-Berechnung
    hist = ticker.history(period="2y")
    if hist.empty:
        raise RuntimeError(f"Keine Daten für {IWDA_TICKER} erhalten")

    close = hist["Close"]
    price = round(float(close.iloc[-1]), 2)
    sma50 = round(float(close.rolling(50).mean().iloc[-1]), 2)
    sma200 = round(float(close.rolling(200).mean().iloc[-1]), 2)

    # ATH aus gesamter Historie
    all_hist = ticker.history(period="max")
    ath = round(float(all_hist["Close"].max()), 2)

    delta_ath_pct = round(((price - ath) / ath) * 100, 1)
    puffer_sma50_pct = round(((price - sma50) / sma50) * 100, 1)
    golden_cross = sma50 > sma200

    log.info("IWDA: %.2f€ | SMA50: %.2f | SMA200: %.2f | ATH: %.2f", price, sma50, sma200, ath)

    return {
        "price": price,
        "sma50": sma50,
        "sma200": sma200,
        "ath": ath,
        "delta_ath_pct": delta_ath_pct,
        "puffer_sma50_pct": puffer_sma50_pct,
        "golden_cross": golden_cross,
    }


def fetch_vix_data():
    """VIX-Wert, Vorwoche und Richtung holen."""
    ticker = yf.Ticker(VIX_TICKER)
    hist = ticker.history(period="1mo")
    if hist.empty:
        raise RuntimeError(f"Keine Daten für {VIX_TICKER} erhalten")

    close = hist["Close"]
    value = round(float(close.iloc[-1]), 2)

    # Wert vor ~5 Handelstagen
    if len(close) >= 6:
        prev_week = round(float(close.iloc[-6]), 2)
    else:
        prev_week = round(float(close.iloc[0]), 2)

    # Richtung bestimmen (Schwelle 0.5 Punkte)
    diff = value - prev_week
    if diff > 0.5:
        direction = "rising"
    elif diff < -0.5:
        direction = "falling"
    else:
        direction = "flat"

    log.info("VIX: %.2f (%s, Vorwoche: %.2f)", value, direction, prev_week)

    return {
        "value": value,
        "direction": direction,
        "prev_week": prev_week,
    }


def _try_fetch_yield(ticker_symbol):
    """Versucht einen Yield-Ticker zu laden. Gibt float oder None zurück."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="5d")
        if not hist.empty:
            val = hist["Close"].dropna()
            if not val.empty:
                return round(float(val.iloc[-1]), 2)
    except Exception as e:
        log.debug("Ticker %s fehlgeschlagen: %s", ticker_symbol, e)
    return None


def fetch_yields_data(db, cpi_override=None):
    """Treasury Yields, Spread, CPI und Real Yield holen.

    Args:
        db: MongoDB-Datenbankinstanz (für Fallback-Werte)
        cpi_override: Optionaler CPI-Wert (überschreibt DB-Wert)
    """
    # US 10Y
    us10y = _try_fetch_yield(US10Y_TICKER)
    if us10y is None:
        raise RuntimeError(f"Keine Daten für {US10Y_TICKER} (US 10Y) erhalten")
    log.info("US 10Y: %.2f%%", us10y)

    # US 2Y — Cascading Fallback
    us2y = _try_fetch_yield(US2Y_TICKER)
    if us2y is None:
        log.warning("US 2Y (%s) nicht verfügbar, verwende Fallback aus DB", US2Y_TICKER)
        us2y = _get_last_value(db, "market.yields.us2y")
        if us2y is None:
            raise RuntimeError("US 2Y: Weder yfinance noch DB-Fallback verfügbar")
        log.info("US 2Y (Fallback): %.2f%%", us2y)
    else:
        log.info("US 2Y: %.2f%%", us2y)

    # CPI — aus Override, letzter Analyse, oder Default
    # CPI ändert sich nur monatlich, Default ist letzter bekannter US CPI
    CPI_DEFAULT = 2.4
    if cpi_override is not None:
        cpi = round(float(cpi_override), 1)
        log.info("CPI (Override): %.1f%%", cpi)
    else:
        cpi = _get_last_value(db, "market.yields.cpi")
        if cpi is None:
            cpi = CPI_DEFAULT
            log.warning("Kein CPI in DB, verwende Default: %.1f%%", cpi)
        else:
            log.info("CPI (aus DB): %.1f%%", cpi)

    spread = round(us10y - us2y, 2)

    # Spread-Direction durch Vergleich mit letzter Analyse
    last_spread = _get_last_value(db, "market.yields.spread")
    if last_spread is not None:
        diff = spread - last_spread
        if diff > 0.05:
            spread_direction = "widening"
        elif diff < -0.05:
            spread_direction = "narrowing"
        else:
            spread_direction = "flat"
    else:
        spread_direction = "flat"

    real_yield = round(us10y - cpi, 2)

    log.info("Spread: %.2f%% (%s) | Real Yield: %.2f%%", spread, spread_direction, real_yield)

    return {
        "us10y": us10y,
        "us2y": us2y,
        "spread": spread,
        "spread_direction": spread_direction,
        "real_yield": real_yield,
        "cpi": cpi,
    }


def _get_last_value(db, field_path):
    """Holt einen verschachtelten Wert aus der letzten Analyse."""
    last = db.analyses.find_one(sort=[("date", -1)])
    if not last:
        return None
    obj = last
    for key in field_path.split("."):
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def fetch_all_market_data(db, cpi_override=None):
    """Holt alle Marktdaten und gibt das vollständige market-Dict zurück."""
    iwda = fetch_iwda_data()
    vix = fetch_vix_data()
    yields = fetch_yields_data(db, cpi_override=cpi_override)

    return {
        **iwda,
        "vix": vix,
        "yields": yields,
    }


# ── Mechanische Signale ──────────────────────────────────────────────────

def calculate_mechanical_signals(market):
    """Berechnet die mechanischen Signale nach den Ampel-Regeln.

    Regeln (aus ampel-prompt-v4.md):
    - Trend: green wenn Kurs > SMA50, sonst red
    - Volatilität: green bei VIX 0-25, yellow bei 25-30, red bei >30
    - Makro: green bei Spread > 0, red bei Spread <= 0
    - Sentiment: Placeholder green (wird von Claude bestimmt)
    """
    # Trend
    trend_mech = "green" if market["price"] > market["sma50"] else "red"

    # Volatilität
    vix_val = market["vix"]["value"]
    if vix_val <= 25:
        vol_mech = "green"
    elif vix_val <= 30:
        vol_mech = "yellow"
    else:
        vol_mech = "red"

    # Makro
    macro_mech = "green" if market["yields"]["spread"] > 0 else "red"

    # Sentiment — Placeholder, Claude bestimmt den echten Wert
    sent_mech = "green"

    signals = {
        "trend": trend_mech,
        "volatility": vol_mech,
        "macro": macro_mech,
        "sentiment": sent_mech,
    }

    score = sum(1 for v in signals.values() if v == "green")

    log.info(
        "Mechanische Signale: T=%s V=%s M=%s S=%s → Score %d/4",
        trend_mech, vol_mech, macro_mech, sent_mech, score,
    )

    return signals, score
