#!/usr/bin/env python3
"""Ampel-Datensammlung via yfinance + mechanische Signalberechnung."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

log = logging.getLogger("ampel")

# ── Ticker-Konfiguration ─────────────────────────────────────────────────

IWDA_TICKER = "IWDA.AS"   # iShares MSCI World, Euronext Amsterdam (EUR)
VIX_TICKER = "^VIX"
US10Y_TICKER = "^TNX"     # CBOE 10-Year Treasury Note Yield
US2Y_TICKER = "2YY=F"     # 2-Year Treasury Yield Future (Fallback nötig)

# Sektor-ETFs (US) für Rotationsanalyse
SECTOR_TICKERS = {
    "tech": "XLK",
    "healthcare": "XLV",
    "consumer_staples": "XLP",
    "utilities": "XLU",
    "financials": "XLF",
    "industrials": "XLI",
    "energy": "XLE",
}

# Regionale Vergleichs-ETFs
SPY_TICKER = "SPY"    # S&P 500
EZU_TICKER = "EZU"    # iShares MSCI Eurozone

# Währung
EURUSD_TICKER = "EURUSD=X"

# Credit Spread ETFs (HY vs IG als Proxy)
HYG_TICKER = "HYG"   # iShares iBoxx High Yield Corporate Bond ETF
LQD_TICKER = "LQD"   # iShares iBoxx Investment Grade Corporate Bond ETF

# Commodities & Safe Havens
OIL_TICKER = "BZ=F"   # Brent Crude Oil Futures
GOLD_TICKER = "GC=F"  # Gold Futures
DXY_TICKER = "DX-Y.NYB"  # US Dollar Index

# Top-15 MSCI World Holdings für aggregierte Earnings-Daten
EARNINGS_TICKERS = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech",
    "AMZN": "Tech", "GOOG": "Tech", "META": "Tech", "TSM": "Tech",
    "JPM": "Financials", "V": "Financials",
    "LLY": "Healthcare", "UNH": "Healthcare",
    "BRK-B": "Conglomerate", "PG": "Consumer Staples",
    "XOM": "Energy", "JNJ": "Healthcare",
}


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
            spread_direction = "rising"
        elif diff < -0.05:
            spread_direction = "falling"
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


def fetch_sector_rotation():
    """Holt 1-Monats-Performance der Sektor-ETFs für Rotationsanalyse.

    Returns:
        dict mit sectors, risk_on_vs_off — oder None bei Fehler.
    """
    sectors = {}
    offensive_perfs = []
    defensive_perfs = []

    for name, ticker_sym in SECTOR_TICKERS.items():
        try:
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="1mo")
            if hist.empty or len(hist) < 2:
                log.warning("Sektor %s (%s): keine Daten", name, ticker_sym)
                continue
            close = hist["Close"]
            perf = round(((float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0])) * 100, 2)
            sectors[name] = {"perf_1m": perf, "ticker": ticker_sym}

            if name in ("tech", "financials", "industrials", "energy"):
                offensive_perfs.append(perf)
            elif name in ("healthcare", "consumer_staples", "utilities"):
                defensive_perfs.append(perf)
        except Exception as e:
            log.warning("Sektor %s (%s) fehlgeschlagen: %s", name, ticker_sym, e)

    risk_on_vs_off = None  # type: Optional[float]
    if offensive_perfs and defensive_perfs:
        avg_off = sum(offensive_perfs) / len(offensive_perfs)
        avg_def = sum(defensive_perfs) / len(defensive_perfs)
        risk_on_vs_off = round(avg_off - avg_def, 2)

    log.info("Sektoren: %d geladen, Risk-On vs Off: %s", len(sectors), risk_on_vs_off)
    return {"sectors": sectors, "risk_on_vs_off": risk_on_vs_off}


def fetch_regional_comparison():
    """Vergleicht Europa (EZU) vs USA (SPY) Performance über 1 Monat.

    Returns:
        dict mit spy_perf_1m, ezu_perf_1m, usa_vs_europe — oder None bei Fehler.
    """
    result = {}

    for label, ticker_sym in [("spy", SPY_TICKER), ("ezu", EZU_TICKER)]:
        try:
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="1mo")
            if hist.empty or len(hist) < 2:
                log.warning("Regional %s: keine Daten", ticker_sym)
                result[label + "_perf_1m"] = None
                continue
            close = hist["Close"]
            perf = round(((float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0])) * 100, 2)
            result[label + "_perf_1m"] = perf
        except Exception as e:
            log.warning("Regional %s fehlgeschlagen: %s", ticker_sym, e)
            result[label + "_perf_1m"] = None

    spy_p = result.get("spy_perf_1m")
    ezu_p = result.get("ezu_perf_1m")
    if spy_p is not None and ezu_p is not None:
        result["usa_vs_europe"] = round(spy_p - ezu_p, 2)
    else:
        result["usa_vs_europe"] = None

    log.info("Regional: SPY %s%%, EZU %s%%, Diff: %s",
             result.get("spy_perf_1m"), result.get("ezu_perf_1m"), result.get("usa_vs_europe"))
    return result


def fetch_seasonality():
    """Berechnet historische monatliche Durchschnittsrenditen von IWDA.

    Returns:
        dict mit current_month, avg_return_pct, monthly_returns, seasonal_bias — oder None.
    """
    try:
        ticker = yf.Ticker(IWDA_TICKER)
        hist = ticker.history(period="max")
        if hist.empty or len(hist) < 252:
            log.warning("Saisonalität: nicht genug IWDA-Historie")
            return None

        monthly = hist["Close"].resample("ME").last()
        monthly_returns = monthly.pct_change().dropna()

        avg_by_month = {}
        for idx, ret in monthly_returns.items():
            m = idx.month
            if m not in avg_by_month:
                avg_by_month[m] = []
            avg_by_month[m].append(float(ret))

        monthly_avgs = {}
        for m, rets in avg_by_month.items():
            monthly_avgs[str(m)] = round(sum(rets) / len(rets) * 100, 2)

        current_month = datetime.now().month
        current_avg = monthly_avgs.get(str(current_month), 0.0)

        if current_avg > 0.5:
            bias = "bullish"
        elif current_avg < -0.5:
            bias = "bearish"
        else:
            bias = "neutral"

        log.info("Saisonalität: Monat %d, avg %.2f%%, Bias: %s", current_month, current_avg, bias)
        return {
            "current_month": current_month,
            "avg_return_pct": current_avg,
            "monthly_returns": monthly_avgs,
            "seasonal_bias": bias,
        }
    except Exception as e:
        log.warning("Saisonalität fehlgeschlagen: %s", e)
        return None


def fetch_put_call_ratio():
    """Berechnet Put/Call Ratio aus SPY Options Open Interest.

    Returns:
        dict mit put_oi, call_oi, ratio, signal — oder None bei Fehler.
    """
    try:
        spy = yf.Ticker(SPY_TICKER)
        dates = spy.options
        if not dates:
            log.warning("Put/Call: keine SPY-Optionstermine")
            return None

        chain = spy.option_chain(dates[0])
        if chain is None:
            return None

        calls_df = chain.calls
        puts_df = chain.puts

        if calls_df.empty or puts_df.empty:
            log.warning("Put/Call: leere Options-Chain")
            return None

        total_call_oi = int(calls_df["openInterest"].sum())
        total_put_oi = int(puts_df["openInterest"].sum())

        if total_call_oi == 0:
            log.warning("Put/Call: Call OI ist 0")
            return None

        ratio = round(total_put_oi / total_call_oi, 2)

        if ratio > 1.2:
            signal = "bearish"
        elif ratio < 0.7:
            signal = "bullish"
        else:
            signal = "neutral"

        log.info("Put/Call: Puts %d, Calls %d, Ratio %.2f (%s)", total_put_oi, total_call_oi, ratio, signal)
        return {
            "put_oi": total_put_oi,
            "call_oi": total_call_oi,
            "ratio": ratio,
            "signal": signal,
        }
    except Exception as e:
        log.warning("Put/Call Ratio fehlgeschlagen: %s", e)
        return None


def fetch_eurusd():
    """Holt EUR/USD Kurs, 1-Monats-Veränderung und Richtung.

    Returns:
        dict mit rate, change_1m_pct, direction — oder None bei Fehler.
    """
    try:
        t = yf.Ticker(EURUSD_TICKER)
        hist = t.history(period="1mo")
        if hist.empty or len(hist) < 2:
            log.warning("EUR/USD: keine Daten")
            return None

        close = hist["Close"]
        rate = round(float(close.iloc[-1]), 4)
        rate_1m_ago = round(float(close.iloc[0]), 4)
        change_1m_pct = round(((rate - rate_1m_ago) / rate_1m_ago) * 100, 2)

        # Richtung bestimmen (Schwelle 0.5%)
        if change_1m_pct > 0.5:
            direction = "rising"    # EUR stärker
        elif change_1m_pct < -0.5:
            direction = "falling"   # USD stärker
        else:
            direction = "flat"

        log.info("EUR/USD: %.4f (1M: %+.2f%%, %s)", rate, change_1m_pct, direction)
        return {
            "rate": rate,
            "change_1m_pct": change_1m_pct,
            "direction": direction,
        }
    except Exception as e:
        log.warning("EUR/USD fehlgeschlagen: %s", e)
        return None


def fetch_credit_spread():
    """Berechnet Credit Spread Proxy aus HYG vs LQD Performance.

    HYG (High Yield) vs LQD (Investment Grade): Wenn HYG relativ
    zu LQD fällt, weiten sich Credit Spreads = Risk-Off.

    Returns:
        dict mit hyg_price, lqd_price, hyg_perf_1m, lqd_perf_1m,
              spread_proxy, direction — oder None bei Fehler.
    """
    try:
        hyg_data = {}
        lqd_data = {}

        for label, ticker_sym, target in [("HYG", HYG_TICKER, hyg_data),
                                           ("LQD", LQD_TICKER, lqd_data)]:
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="1mo")
            if hist.empty or len(hist) < 2:
                log.warning("Credit Spread %s: keine Daten", label)
                return None
            close = hist["Close"]
            target["price"] = round(float(close.iloc[-1]), 2)
            target["perf_1m"] = round(
                ((float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0])) * 100, 2
            )

        # Spread-Proxy: HYG perf - LQD perf
        # Positiv = HY outperformt IG = Credit Spreads engen ein = Risk-On
        # Negativ = HY underperformt IG = Credit Spreads weiten sich = Risk-Off
        spread_proxy = round(hyg_data["perf_1m"] - lqd_data["perf_1m"], 2)

        if spread_proxy > 0.5:
            direction = "narrowing"   # Risk-On
        elif spread_proxy < -0.5:
            direction = "widening"    # Risk-Off
        else:
            direction = "flat"

        log.info("Credit Spread: HYG %+.2f%% LQD %+.2f%%, Proxy: %+.2f%% (%s)",
                 hyg_data["perf_1m"], lqd_data["perf_1m"], spread_proxy, direction)
        return {
            "hyg_price": hyg_data["price"],
            "lqd_price": lqd_data["price"],
            "hyg_perf_1m": hyg_data["perf_1m"],
            "lqd_perf_1m": lqd_data["perf_1m"],
            "spread_proxy": spread_proxy,
            "direction": direction,
        }
    except Exception as e:
        log.warning("Credit Spread fehlgeschlagen: %s", e)
        return None


def fetch_oil():
    """Holt Brent-Ölpreis, 1-Monats-Veränderung und Richtung.

    Returns:
        dict mit price, change_1m_pct, direction — oder None bei Fehler.
    """
    try:
        t = yf.Ticker(OIL_TICKER)
        hist = t.history(period="1mo")
        if hist.empty or len(hist) < 2:
            log.warning("Öl: keine Daten")
            return None

        close = hist["Close"]
        price = round(float(close.iloc[-1]), 2)
        price_1m = round(float(close.iloc[0]), 2)
        change = round(((price - price_1m) / price_1m) * 100, 2)
        direction = "rising" if change > 2 else ("falling" if change < -2 else "flat")

        log.info("Öl (Brent): $%.2f (1M: %+.2f%%, %s)", price, change, direction)
        return {
            "price": price,
            "change_1m_pct": change,
            "direction": direction,
        }
    except Exception as e:
        log.warning("Öl-Daten fehlgeschlagen: %s", e)
        return None


def fetch_gold():
    """Holt Goldpreis, 1-Monats-Veränderung und Richtung.

    Returns:
        dict mit price, change_1m_pct, direction — oder None bei Fehler.
    """
    try:
        t = yf.Ticker(GOLD_TICKER)
        hist = t.history(period="1mo")
        if hist.empty or len(hist) < 2:
            log.warning("Gold: keine Daten")
            return None

        close = hist["Close"]
        price = round(float(close.iloc[-1]), 2)
        price_1m = round(float(close.iloc[0]), 2)
        change = round(((price - price_1m) / price_1m) * 100, 2)
        direction = "rising" if change > 1 else ("falling" if change < -1 else "flat")

        log.info("Gold: $%.2f (1M: %+.2f%%, %s)", price, change, direction)
        return {
            "price": price,
            "change_1m_pct": change,
            "direction": direction,
        }
    except Exception as e:
        log.warning("Gold-Daten fehlgeschlagen: %s", e)
        return None


def fetch_dxy():
    """Holt US Dollar Index, 1-Monats-Veränderung und Richtung.

    Returns:
        dict mit value, change_1m_pct, direction — oder None bei Fehler.
    """
    try:
        t = yf.Ticker(DXY_TICKER)
        hist = t.history(period="1mo")
        if hist.empty or len(hist) < 2:
            log.warning("DXY: keine Daten")
            return None

        close = hist["Close"]
        value = round(float(close.iloc[-1]), 2)
        value_1m = round(float(close.iloc[0]), 2)
        change = round(((value - value_1m) / value_1m) * 100, 2)
        direction = "rising" if change > 0.5 else ("falling" if change < -0.5 else "flat")

        log.info("DXY: %.2f (1M: %+.2f%%, %s)", value, change, direction)
        return {
            "value": value,
            "change_1m_pct": change,
            "direction": direction,
        }
    except Exception as e:
        log.warning("DXY-Daten fehlgeschlagen: %s", e)
        return None


def fetch_earnings_aggregate():
    """Holt aggregierte Earnings-Daten der Top-15 MSCI World Holdings.

    Sammelt Beat-Rate, Forward Growth, Revisions-Momentum und Earnings-Kalender.
    Verwendet eigenen ThreadPool für parallele Ticker-Abfragen.

    Returns:
        dict mit beat_rate, fwd_eps_growth, revision_direction, by_sector etc.
        — oder None bei Fehler.
    """
    import pandas as pd

    def _fetch_ticker_data(sym):
        """Holt Earnings-Daten für einen einzelnen Ticker."""
        t = yf.Ticker(sym)
        data = {}

        # Earnings History (letzte 4 Quartale: actual vs estimate)
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                data["earnings_history"] = eh
        except Exception:
            pass

        # Forward EPS Estimates
        try:
            ee = t.earnings_estimate
            if ee is not None and not ee.empty:
                data["earnings_estimate"] = ee
        except Exception:
            pass

        # EPS Revisions (up/down in 7d/30d)
        try:
            er = t.eps_revisions
            if er is not None and not er.empty:
                data["eps_revisions"] = er
        except Exception:
            pass

        # Revenue Estimates
        try:
            re_ = t.revenue_estimate
            if re_ is not None and not re_.empty:
                data["revenue_estimate"] = re_
        except Exception:
            pass

        # Calendar (next earnings date)
        try:
            cal = t.calendar
            if cal is not None:
                data["calendar"] = cal
        except Exception:
            pass

        return data

    try:
        # Parallel fetch für alle Ticker
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_ticker_data, sym): sym
                       for sym in EARNINGS_TICKERS}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    result = future.result()
                    if result:
                        results[sym] = result
                except Exception as e:
                    log.warning("Earnings %s fehlgeschlagen: %s", sym, e)

        if not results:
            log.warning("Earnings: keine Ticker-Daten erhalten")
            return None

        # ── Aggregation ──

        # Beat Rate aus earnings_history
        total_beats = 0
        total_quarters = 0
        surprises = []
        recently_reported = []
        today = datetime.now()

        sector_data = {}  # sector -> {beats, quarters, surprises, ...}

        for sym, data in results.items():
            sector = EARNINGS_TICKERS[sym]
            if sector not in sector_data:
                sector_data[sector] = {
                    "beats": 0, "quarters": 0, "surprises": [],
                    "fwd_eps_growths": [], "rev_up_7d": 0, "rev_down_7d": 0,
                    "rev_up_30d": 0, "rev_down_30d": 0, "tickers": [],
                }
            sd = sector_data[sector]
            sd["tickers"].append(sym)

            eh = data.get("earnings_history")
            if eh is not None and not eh.empty:
                for _, row in eh.iterrows():
                    actual = row.get("epsActual")
                    estimate = row.get("epsEstimate")
                    if pd.notna(actual) and pd.notna(estimate) and estimate != 0:
                        total_quarters += 1
                        sd["quarters"] += 1
                        surprise_pct = round(((actual - estimate) / abs(estimate)) * 100, 1)
                        surprises.append(surprise_pct)
                        sd["surprises"].append(surprise_pct)
                        if actual >= estimate:
                            total_beats += 1
                            sd["beats"] += 1

                # Letztes Quartal für recently_reported
                last_row = eh.iloc[0] if len(eh) > 0 else None
                if last_row is not None:
                    q_date = eh.index[0] if hasattr(eh.index[0], 'strftime') else None
                    actual = last_row.get("epsActual")
                    estimate = last_row.get("epsEstimate")
                    if q_date and pd.notna(actual) and pd.notna(estimate) and estimate != 0:
                        surprise = round(((actual - estimate) / abs(estimate)) * 100, 1)
                        recently_reported.append({
                            "ticker": sym,
                            "date": q_date.strftime("%Y-%m-%d") if hasattr(q_date, 'strftime') else str(q_date),
                            "surprise_pct": surprise,
                            "sector": sector,
                        })

            # Forward EPS Growth aus earnings_estimate
            # DataFrame: Index=period (0q, +1q, 0y, +1y), Spalten inkl. 'growth'
            ee = data.get("earnings_estimate")
            if ee is not None and not ee.empty:
                try:
                    if "growth" in ee.columns and "0y" in ee.index:
                        growth_val = ee.loc["0y", "growth"]
                        if pd.notna(growth_val):
                            sd["fwd_eps_growths"].append(float(growth_val))
                except Exception:
                    pass

            # EPS Revisions
            # DataFrame: Index=period (0q, +1q, 0y, +1y),
            # Spalten: upLast7days, upLast30days, downLast30days, downLast7Days
            er = data.get("eps_revisions")
            if er is not None and not er.empty:
                try:
                    # Summiere über relevante Perioden (0q + 0y)
                    for period in ["0q", "0y"]:
                        if period not in er.index:
                            continue
                        row = er.loc[period]
                        if "upLast7days" in er.columns and pd.notna(row.get("upLast7days")):
                            sd["rev_up_7d"] += int(row["upLast7days"])
                        if "downLast7Days" in er.columns and pd.notna(row.get("downLast7Days")):
                            sd["rev_down_7d"] += int(row["downLast7Days"])
                        if "upLast30days" in er.columns and pd.notna(row.get("upLast30days")):
                            sd["rev_up_30d"] += int(row["upLast30days"])
                        if "downLast30days" in er.columns and pd.notna(row.get("downLast30days")):
                            sd["rev_down_30d"] += int(row["downLast30days"])
                except Exception:
                    pass

        # ── Gesamt-Aggregation ──

        beat_rate_pct = round((total_beats / total_quarters * 100), 1) if total_quarters > 0 else 0
        avg_surprise = round(sum(surprises) / len(surprises), 1) if surprises else 0

        # Forward EPS Growth (Durchschnitt aller Ticker mit Daten)
        all_fwd_growths = []
        for sd in sector_data.values():
            all_fwd_growths.extend(sd["fwd_eps_growths"])
        fwd_eps_growth_0y = round(sum(all_fwd_growths) / len(all_fwd_growths), 3) if all_fwd_growths else None

        # Revisions-Momentum
        total_rev_up_7d = sum(sd["rev_up_7d"] for sd in sector_data.values())
        total_rev_down_7d = sum(sd["rev_down_7d"] for sd in sector_data.values())
        total_rev_up_30d = sum(sd["rev_up_30d"] for sd in sector_data.values())
        total_rev_down_30d = sum(sd["rev_down_30d"] for sd in sector_data.values())
        net_rev_7d = total_rev_up_7d - total_rev_down_7d
        net_rev_30d = total_rev_up_30d - total_rev_down_30d

        if net_rev_30d > 5:
            rev_direction = "rising"
        elif net_rev_30d < -5:
            rev_direction = "falling"
        else:
            rev_direction = "flat"

        # Earnings Health
        if beat_rate_pct >= 75 and rev_direction == "rising" and (fwd_eps_growth_0y or 0) > 0.10:
            earnings_health = "strong"
        elif beat_rate_pct >= 75 and rev_direction != "falling":
            earnings_health = "moderate"
        elif beat_rate_pct >= 60 and rev_direction != "falling":
            earnings_health = "moderate"
        elif rev_direction == "falling" or beat_rate_pct < 60:
            earnings_health = "weak"
        else:
            earnings_health = "moderate"

        if rev_direction == "falling" and beat_rate_pct < 70:
            earnings_health = "deteriorating"

        # Sektor-Zusammenfassung
        by_sector = {}
        for sector, sd in sector_data.items():
            s_beat_pct = round((sd["beats"] / sd["quarters"] * 100), 1) if sd["quarters"] > 0 else 0
            s_surprise = round(sum(sd["surprises"]) / len(sd["surprises"]), 1) if sd["surprises"] else 0
            s_fwd = round(sum(sd["fwd_eps_growths"]) / len(sd["fwd_eps_growths"]), 3) if sd["fwd_eps_growths"] else None
            s_net_rev = (sd["rev_up_30d"] - sd["rev_down_30d"])
            s_rev_dir = "rising" if s_net_rev > 2 else ("falling" if s_net_rev < -2 else "flat")

            by_sector[sector] = {
                "beat_rate": f"{sd['beats']}/{sd['quarters']}",
                "beat_rate_pct": s_beat_pct,
                "avg_surprise_pct": s_surprise,
                "fwd_eps_growth": s_fwd,
                "revision_direction": s_rev_dir,
                "tickers": sd["tickers"],
            }

        # Upcoming Earnings aus Calendar
        upcoming = []
        today_date = today.date()
        for sym, data in results.items():
            cal = data.get("calendar")
            if cal is not None:
                try:
                    # calendar ist ein dict, Earnings Date ist eine Liste von date-Objekten
                    if isinstance(cal, dict):
                        ed_list = cal.get("Earnings Date", [])
                    else:
                        ed_list = []

                    if not isinstance(ed_list, (list, tuple)):
                        ed_list = [ed_list]

                    for d in ed_list:
                        if hasattr(d, 'strftime') and d > today_date:
                            upcoming.append({
                                "ticker": sym,
                                "date": d.strftime("%Y-%m-%d"),
                                "sector": EARNINGS_TICKERS[sym],
                            })
                            break
                except Exception:
                    pass

        upcoming.sort(key=lambda x: x["date"])
        recently_reported.sort(key=lambda x: x["date"], reverse=True)

        result = {
            "beat_rate": f"{total_beats}/{total_quarters}",
            "beat_rate_pct": beat_rate_pct,
            "avg_surprise_pct": avg_surprise,
            "fwd_eps_growth_0y": fwd_eps_growth_0y,
            "net_revisions_7d": net_rev_7d,
            "net_revisions_30d": net_rev_30d,
            "revision_direction": rev_direction,
            "earnings_health": earnings_health,
            "by_sector": by_sector,
            "upcoming": upcoming[:5],
            "recently_reported": recently_reported[:5],
            "tickers_loaded": len(results),
        }

        log.info("Earnings: %d/%d Ticker, Beat %s (%.0f%%), Health: %s, Revisions: %s",
                 len(results), len(EARNINGS_TICKERS),
                 result["beat_rate"], beat_rate_pct, earnings_health, rev_direction)
        return result

    except Exception as e:
        log.warning("Earnings-Aggregation fehlgeschlagen: %s", e)
        return None


def fetch_top_holdings_data(db):
    """Fetch current price data for portfolio top holdings from DB config."""
    portfolio = db.portfolio.find_one({"_id": "default"})
    if not portfolio or not portfolio.get("top_holdings"):
        return None

    holdings = portfolio["top_holdings"]
    tickers = [h["ticker"] for h in holdings]

    results = []
    for h in holdings:
        ticker = h["ticker"]
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="3mo")
            if hist.empty:
                continue

            close_series = hist["Close"]
            current = float(close_series.iloc[-1])
            sma50_val = float(close_series.rolling(50).mean().iloc[-1]) if len(close_series) >= 50 else None

            # 1-month performance
            one_month_ago = len(close_series) - 22 if len(close_series) >= 22 else 0
            perf_1m = ((current / float(close_series.iloc[one_month_ago])) - 1) * 100

            puffer = round(((current / sma50_val) - 1) * 100, 2) if sma50_val and sma50_val == sma50_val else None

            results.append({
                "ticker": ticker,
                "name": h.get("name", ticker),
                "sector": h.get("sector", ""),
                "weight_pct": h.get("weight_pct", 0),
                "price": round(current, 2),
                "sma50": round(sma50_val, 2) if sma50_val and sma50_val == sma50_val else None,
                "above_sma50": current > sma50_val if sma50_val and sma50_val == sma50_val else None,
                "puffer_sma50_pct": puffer,
                "perf_1m_pct": round(perf_1m, 2),
            })
        except Exception as e:
            log.warning("Top-Holding %s fehlgeschlagen: %s", ticker, e)

    if not results:
        return None

    above_count = sum(1 for r in results if r.get("above_sma50") is True)
    total = sum(1 for r in results if r.get("above_sma50") is not None)

    # Gewichteter Durchschnitt Puffer SMA50
    with_puffer = [r for r in results if r.get("puffer_sma50_pct") is not None]
    total_weight = sum(r["weight_pct"] for r in with_puffer) or 1
    avg_puffer = sum(r["puffer_sma50_pct"] * r["weight_pct"] for r in with_puffer) / total_weight

    # Tech vs Nicht-Tech Aufschlüsselung
    tech = [r for r in with_puffer if r.get("sector", "").lower() == "tech"]
    non_tech = [r for r in with_puffer if r.get("sector", "").lower() != "tech"]
    tech_avg_puffer = (sum(r["puffer_sma50_pct"] * r["weight_pct"] for r in tech)
                       / (sum(r["weight_pct"] for r in tech) or 1)) if tech else None
    non_tech_avg_perf = (sum(r["perf_1m_pct"] * r["weight_pct"] for r in non_tech)
                         / (sum(r["weight_pct"] for r in non_tech) or 1)) if non_tech else None

    return {
        "holdings": results,
        "above_sma50_count": above_count,
        "total_count": total,
        "above_sma50_pct": round(above_count / total * 100) if total else 0,
        "avg_puffer_sma50_pct": round(avg_puffer, 2),
        "tech_avg_puffer_pct": round(tech_avg_puffer, 2) if tech_avg_puffer is not None else None,
        "non_tech_avg_perf_1m_pct": round(non_tech_avg_perf, 2) if non_tech_avg_perf is not None else None,
    }


def fetch_all_market_data(db, cpi_override=None):
    """Holt alle Marktdaten und gibt das vollständige market-Dict zurück."""
    # Core-Daten (sequentiell — kritisch)
    iwda = fetch_iwda_data()
    vix = fetch_vix_data()
    yields = fetch_yields_data(db, cpi_override=cpi_override)

    # Erweiterte Daten (parallel — alle optional)
    extended = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_sector_rotation): "sector_rotation",
            executor.submit(fetch_regional_comparison): "regional",
            executor.submit(fetch_seasonality): "seasonality",
            executor.submit(fetch_put_call_ratio): "put_call",
            executor.submit(fetch_eurusd): "eurusd",
            executor.submit(fetch_credit_spread): "credit_spread",
            executor.submit(fetch_oil): "oil",
            executor.submit(fetch_gold): "gold",
            executor.submit(fetch_dxy): "dxy",
            executor.submit(fetch_earnings_aggregate): "earnings",
            executor.submit(fetch_top_holdings_data, db): "top_holdings",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                extended[key] = future.result()
            except Exception as e:
                log.warning("%s fehlgeschlagen: %s", key, e)
                extended[key] = None

    market = {
        **iwda,
        "vix": vix,
        "yields": yields,
        **extended,
    }

    # ETF-Holdings-Divergenz berechnen
    th = market.get("top_holdings")
    if th and th.get("avg_puffer_sma50_pct") is not None:
        etf_puffer = market.get("puffer_sma50_pct", 0)
        holdings_puffer = th["avg_puffer_sma50_pct"]
        gap = round(etf_puffer - holdings_puffer, 2)
        tech_puffer = th.get("tech_avg_puffer_pct")
        th["divergence"] = {
            "etf_puffer_pct": etf_puffer,
            "holdings_avg_puffer_pct": holdings_puffer,
            "gap_pct": gap,
            "compensation_active": gap > 3.0,
            "tech_drag": tech_puffer is not None and tech_puffer < -3.0,
        }

    return market


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
