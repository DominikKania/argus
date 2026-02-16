# Argus — Investment Knowledge Base

## Was ist Argus?

Argus ist mein persönliches Investment-Wissenssystem. Es speichert Marktanalysen, trackt Thesen und baut über Zeit ein Gedächtnis auf, aus dem ich lerne. Lokal, simpel, erweiterbar.

**Erstes Modul: Ampel** — ein Signalsystem das 4 Indikatoren (Trend, Volatilität, Makro, Sentiment) zu einer Gesamtbewertung (GRÜN/GELB/ROT) verdichtet.

Wir fangen simpel an und bauen aus.

## Tech-Stack

- **Datenbank:** MongoDB (lokal)
- **Backend:** Python (pymongo)
- **CLI:** `python argus.py <command>` via argparse
- **DB-Name:** `argus`

## Phase 1: MVP

### Collection: `analyses`

```json
{
  "date": "2026-02-15",
  "weekday": "Saturday",

  "market": {
    "price": 112.6,
    "sma50": 112.0,
    "sma200": 105.0,
    "ath": 115.09,
    "delta_ath_pct": -2.2,
    "puffer_sma50_pct": 0.5,
    "golden_cross": true,
    "vix": {
      "value": 15.0,
      "direction": "falling",
      "prev_week": 23.0
    },
    "yields": {
      "us10y": 4.07,
      "us2y": 3.42,
      "spread": 0.65,
      "spread_direction": "widening",
      "real_yield": 1.67,
      "cpi": 2.4
    }
  },

  "signals": {
    "trend":      { "mechanical": "green", "context": "yellow", "note": "Puffer nur 0,5% — extrem fragil" },
    "volatility": { "mechanical": "green", "context": "green",  "note": "CPI-Relief, VIX normalisiert" },
    "macro":      { "mechanical": "green", "context": "green",  "note": "Spread positiv, CPI unter Erwartung" },
    "sentiment":  { "mechanical": "yellow","context": "yellow", "note": "AI-Scare vs. CPI-Relief gegenläufig" }
  },

  "rating": {
    "mechanical_score": 3,
    "overall": "GREEN_FRAGILE",
    "reasoning": "3/4 mechanisch grün, aber Trend-Puffer minimal"
  },

  "beller_check": null,

  "sentiment_events": [
    {
      "headline": "Software-Sektor Selloff beschleunigt sich",
      "affects_portfolio": "sector_only",
      "cascade_risk": "medium",
      "is_primary": true
    }
  ],

  "recommendation": {
    "action": "hold",
    "detail": "Halten. Sektor-Rotation ist für IWDA Nullsummenspiel."
  },

  "thesis": {
    "statement": "NVIDIA Earnings entscheiden ob AI-Scare berechtigt oder Überreaktion",
    "catalyst": "NVIDIA Earnings",
    "catalyst_date": "2026-02-25",
    "expected_if_positive": "AI-Scare entkräftet, Software stabilisiert",
    "expected_if_negative": "Software-Selloff beschleunigt, aber nur ~14,5% IWDA betroffen"
  },

  "escalation_trigger": "Kurs unter SMA50 (112€) ohne Reversal in 5 Tagen",
  "crash_rule_active": false
}
```

### Collection: `theses`

```json
{
  "created_date": "2026-02-15",
  "analysis_id": "<ObjectId>",
  "statement": "NVIDIA Earnings entscheiden ob AI-Scare berechtigt oder Überreaktion",
  "catalyst": "NVIDIA Earnings",
  "catalyst_date": "2026-02-25",
  "expected_if_positive": "AI-Scare entkräftet",
  "expected_if_negative": "Software-Selloff beschleunigt",
  "status": "open",
  "resolution": null,
  "resolution_date": null,
  "accuracy": null,
  "lessons_learned": null
}
```

## CLI-Befehle (Phase 1)

```bash
# Analyse speichern
python argus.py save --json analysis.json

# Letzte Analyse anzeigen
python argus.py latest

# Verlauf (kompakt)
python argus.py history              # Letzte 10
python argus.py history --all

# Offene Thesen
python argus.py theses

# These auflösen
python argus.py resolve <id> --outcome "..." --accuracy correct

# Export für Ampel-Prompt (formatierter Text-Block)
python argus.py export
```

Das wars für Phase 1. Kein `trends`, kein `stats`, kein `review --deep` — das kommt später.

## Anforderungen

- Ein einzelnes Script: `argus.py`
- Dependency: nur `pymongo`
- Validierung: Pflichtfelder prüfen, Enum-Werte für `mechanical`/`context` (green/yellow/red), `direction` (rising/falling/flat), `action` (hold/buy/partial_sell/hedge/wait)
- Indexes: `date`, `rating.overall`, `theses.status`
- Fehlerbehandlung auf Deutsch
- README.md mit Setup

## `export` Befehl — Output-Format

Der wichtigste Befehl. Gibt einen formatierten Block aus, den ich in meinen Claude-Chat einfüge:

```
=== ARGUS EXPORT ===

📊 VERLAUF (letzte 5 Analysen)
| Datum | Kurs | Δ ATH | T | V | M | S | Gesamt | Empfehlung |
|-------|------|-------|---|---|---|---|--------|------------|
| 15.02 | 112,6€ | −2,2% | 🟡 | 🟢 | 🟢 | 🟡 | GRÜN (fragil) | Halten |

📌 OFFENE THESEN
- [15.02] NVIDIA Earnings entscheiden ob AI-Scare berechtigt (Katalysator: 25.02)

📈 LETZTE ANALYSE (15.02)
- Gesamt: GRÜN (fragil) | Mechanisch: 3/4
- These: NVIDIA Earnings 25.02
- Trigger: Kurs unter SMA50 ohne Reversal in 5 Tagen

=== ENDE EXPORT ===
```

## Starte mit Schritt 1

Baue `argus.py` mit DB-Verbindung und dem `save` + `latest` Befehl. Frag bei Unklarheiten.
