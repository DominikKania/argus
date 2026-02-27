# Argus — Modul: Earnings

## Was ist das Earnings-Modul?

Systematische Earnings-Analyse für Einzelaktien. Getrennt von der Ampel:
- **Ampel** = strategisch ("Soll ich investiert sein?") — Makro-Signalsystem für passive ETF-Allokation
- **Earnings** = taktisch ("Welche Titel haben jetzt ein Setup?") — Einzelaktien-Analyse rund um Quartalszahlen

## Ziel & Grundidee

### Das Problem

Börsennotierte Unternehmen müssen alle 3 Monate öffentlich berichten, wie viel sie verdient haben — die sogenannten Quartalszahlen (Earnings). Das passiert 4x pro Jahr und ist jedes Mal ein riesiges Event: An einem einzigen Tag kann eine Aktie 10-20% steigen oder fallen. Die meisten Anleger reagieren dabei rein emotional — sie lesen eine Schlagzeile und handeln impulsiv. Es gibt keinen systematischen Lernprozess.

### Der Ansatz am konkreten Beispiel: NVIDIA

NVIDIA meldet 4x im Jahr Quartalszahlen — immer Ende Februar, Mai, August und November, typischerweise nach US-Börsenschluss (ca. 22:00 Uhr deutscher Zeit). Nehmen wir die **Q4-Zahlen am 25. Februar 2026** als Beispiel für den kompletten Kreislauf: **Prognose → Beobachtung → Vergleich → Lernen.**

**~17. Februar — Pre-Earnings Analyse**
```bash
python argus.py earnings NVDA
```
Etwa eine Woche vor dem Termin sammelst du alle verfügbaren Daten. Das System holt automatisch: Aktueller Kurs (128,50$), was Analysten erwarten (EPS 0,82$), ob NVIDIA die letzten Quartale die Erwartungen geschlagen hat (4/4 Beats), wie viel Kursbewegung der Markt erwartet (±8,5%). Optional recherchiert die KI die aktuelle Stimmung im Netz (Upgrades, Downgrades, Risikofaktoren).

Dann gibst du deine begründete Einschätzung ab: Wird der Kurs steigen, fallen, oder seitwärts gehen? Mit welcher Überzeugung? Warum?
> "Bullish, medium confidence — 4/4 Beats, starker Analysten-Konsens, aber AI-Capex-Sorgen als Risiko."

Alles wird in der Datenbank gespeichert. Jetzt wartest du auf den Termin.

**25. Februar, ~22:00 Uhr — Earnings werden veröffentlicht**
NVIDIA meldet die Zahlen nach Börsenschluss. Du liest die Ergebnisse, schaust die Reaktion im Aftermarket. Hier machst du noch nichts im System — die Börse muss erst einen Tag mit den neuen Zahlen handeln.

**26. Februar abends — Post-Earnings Analyse**
```bash
python argus.py earnings NVDA --post
```
Jetzt schaust du, was tatsächlich passiert ist. Das System holt die Ergebnisse: EPS 0,89$ (Beat! +8,5% über Erwartung) — aber der Kurs ist trotzdem gefallen. Eröffnung bei 118$ (Gap-Down -8,2%), Schluss bei 115$ (-10,5%).

Das System erkennt automatisch technische Muster (Gap-Down + Bearish Engulfing + 3,5x Volume) und prüft die "Kindle Rule" — einen kombinierten Indikator der zeigt, ob die Kursbewegung nachhaltig ist. Dann der entscheidende Schritt: Deine Prognose wird mit der Realität verglichen (bullish → Kurs gefallen → **falsch**) und eine Lektion formuliert: "Gute Zahlen, aber die Guidance (Ausblick) war schwächer als erhofft. Der Markt reagiert nicht auf Vergangenheit sondern auf Zukunft."

**Die Zeitlinie auf einen Blick:**
```
17. Feb           25. Feb (22:00)        26. Feb abends
   |                   |                      |
   ▼                   ▼                      ▼
Pre-Analyse         NVIDIA meldet          Post-Analyse
"Bullish,           EPS 0,89 (Beat!)       Kurs -10,5%
medium"             Guidance schwach        Kindle: Bearish
                                           Prognose: FALSCH ✘
                                           Lektion gelernt ✓
```

**Mai 2026 — nächste NVIDIA-Earnings, Q1-Zahlen**
Du hast jetzt einen Datenpunkt mehr. Du weißt: "Bei NVIDIA kann ein Beat trotzdem zum Kurseinbruch führen, wenn die Guidance enttäuscht." Das fließt in deine nächste Einschätzung ein.

### Was du über Zeit gewinnst

Nach 20-30 dokumentierten Earnings baut sich ein persönliches Wissensarchiv auf:

- **Trefferquote:** "Ich lag in 65% der Fälle richtig" → objektives Feedback statt Bauchgefühl
- **Mustererkennung:** "Wenn die IV deutlich über dem historischen Durchschnitt liegt, fällt der Kurs danach oft — selbst bei guten Zahlen" (weil zu viel Erwartung eingepreist war)
- **Kindle Rule Validierung:** "Wenn Gap + Engulfing + Volume in eine Richtung zeigen, ging es in 80% der Fälle weiter in diese Richtung" → nutzbares Handelssignal
- **Typische Fallen:** "Beat allein reicht nicht — der Markt reagiert auf die Guidance (Ausblick), nicht auf die vergangenen Zahlen"

### Kernprinzip

> **Nicht vorhersagen, sondern systematisch besser werden.**
> Jede Earnings-Analyse ist ein Datenpunkt. Über Zeit entsteht aus vielen Datenpunkten echtes Wissen darüber, welche Signale tatsächlich funktionieren und welche nicht.

Das Modul ist kein Trading-System das automatisch handelt. Es ist ein **Lern- und Analysewerkzeug**, das dich zwingt, deine Einschätzungen zu dokumentieren, mit der Realität abzugleichen und daraus zu lernen — statt dieselben Fehler immer wieder zu machen.

## Workflow

```
1. Watchlist pflegen      →  Ticker die mich interessieren
2. Pre-Earnings Analyse   →  VOR dem Termin: Setup bewerten
3. Post-Earnings Update   →  NACH dem Termin: Reaktion vs. Prognose
4. Über Zeit lernen       →  Trefferquote tracken, Muster erkennen
```

## Tech

- **Script:** `argus.py` (erweitert bestehendes CLI)
- **Datenquellen:** Kombiniert (siehe unten)
- **LLM-Provider:** Konfigurierbar via Env-Variablen
- **DB:** MongoDB `argus` — neue Collections: `watchlist`, `earnings`
- **Pattern-Erkennung:** Selbst implementiert (kein ta-lib nötig)

## Datenquellen-Architektur

Zwei Schichten, klar getrennt:

### Schicht 1: API (yfinance) — Harte Zahlencommit & psuh alles
Automatisch, deterministisch, keine LLM-Abhängigkeit.

| Datenpunkt | Quelle |
|-----------|--------|
| Kurs, OHLCV, Volume | `yfinance` |
| SMA50, SMA200, RSI | Berechnet aus OHLCV |
| EPS actual/estimate | `Ticker.get_earnings_history()` |
| Earnings-Datum | `Ticker.get_earnings_dates()` |
| Options-IV, Expected Move | `Ticker.option_chain()` |
| Analysten-Ratings (Counts) | `Ticker.get_recommendations()` |
| Kursziel | `Ticker.info['targetMeanPrice']` |
| Pattern-Erkennung (Post) | Berechnet aus OHLCV |

### Schicht 2: LLM + Web Search — Stimmung & Kontext
Qualitativ, LLM-gestützt. Liefert das, was Zahlen nicht zeigen.

| Datenpunkt | Methode |
|-----------|---------|
| Analysten-Stimmung (Trend) | Web Search → LLM-Zusammenfassung |
| Letzte Upgrades/Downgrades | Web Search → LLM-Extraktion |
| Sektor-Sentiment | Web Search → LLM-Einschätzung |
| Risikofaktoren | Web Search → LLM-Identifikation |
| Earnings-Erwartungen (narrativ) | Web Search → LLM-Zusammenfassung |
| Post-Earnings Lektion | LLM-Analyse der Daten |

### Ablauf Pre-Earnings

```
1. yfinance → Harte Zahlen abrufen (Kurs, EPS, IV, Analysten-Counts)
2. LLM + Web Search → Stimmung recherchieren
3. LLM → Assessment generieren (Richtung, Konfidenz, Begründung)
4. Zusammenführen → In MongoDB speichern
```

### Ablauf Post-Earnings

```
1. yfinance → Neue Kursdaten, tatsächliche EPS-Zahlen
2. Pattern-Erkennung → Gap, Engulfing, Volume, Breakout, Kindle Rule
3. LLM → Lektion formulieren (warum hat der Markt so reagiert?)
4. Vergleich → Prediction vs. Realität bewerten
```

## LLM-Provider Konfiguration

Via Environment-Variablen — Provider-agnostisch:

```bash
# OpenAI / Azure OpenAI / OpenAI-kompatible APIs
ARGUS_LLM_PROVIDER=openai
ARGUS_LLM_API_KEY=sk-...
ARGUS_LLM_BASE_URL=https://api.openai.com/v1          # Optional, Default
ARGUS_LLM_MODEL=gpt-4o                                 # Optional, Default

# Azure OpenAI
ARGUS_LLM_PROVIDER=azure
ARGUS_LLM_API_KEY=ae77efe4...
ARGUS_LLM_BASE_URL=https://docuopaiswewsit.openai.azure.com/
ARGUS_LLM_MODEL=docuneogpt41nano
ARGUS_LLM_API_VERSION=2024-12-01-preview               # Nur für Azure

# Anthropic
ARGUS_LLM_PROVIDER=anthropic
ARGUS_LLM_API_KEY=sk-ant-...
ARGUS_LLM_MODEL=claude-sonnet-4-5-20250929

# Lokal (Ollama)
ARGUS_LLM_PROVIDER=ollama
ARGUS_LLM_BASE_URL=http://localhost:11434/v1
ARGUS_LLM_MODEL=llama3
```

### LLM-Client Implementierung

```python
def get_llm_client():
    """Erstellt LLM-Client basierend auf ARGUS_LLM_* Env-Variablen."""
    provider = os.environ.get("ARGUS_LLM_PROVIDER", "openai")
    api_key = os.environ.get("ARGUS_LLM_API_KEY")
    base_url = os.environ.get("ARGUS_LLM_BASE_URL")
    model = os.environ.get("ARGUS_LLM_MODEL", "gpt-4o")

    if provider == "azure":
        from openai import AzureOpenAI
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=os.environ.get("ARGUS_LLM_API_VERSION", "2024-12-01-preview"),
        ), model

    elif provider == "anthropic":
        from anthropic import Anthropic
        return Anthropic(api_key=api_key), model

    else:  # openai, ollama, oder jeder OpenAI-kompatible Provider
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs), model
```

### LLM-Aufrufe im Earnings-Modul

Das LLM wird für 3 konkrete Aufgaben genutzt:

**1. Pre-Earnings: Stimmungs-Recherche**
```
System: Du bist ein Finanzanalyst. Fasse die aktuelle Analysten-Stimmung zusammen.
User: Recherchiere die aktuelle Stimmung zu {ticker} vor den Earnings am {date}.
      Harte Zahlen (bereits vorhanden): {api_data}
      Fasse zusammen: Letzte Upgrades/Downgrades, Sektor-Sentiment, Risikofaktoren.
```

**2. Pre-Earnings: Assessment**
```
System: Du bist ein Finanzanalyst. Bewerte das Earnings-Setup.
User: Basierend auf diesen Daten, bewerte {ticker}:
      {api_data + sentiment_data}
      Antworte im JSON-Format:
      {"direction": "bullish|bearish|neutral", "confidence": "high|medium|low", "reasoning": "..."}
```

**3. Post-Earnings: Lektion**
```
System: Du bist ein Finanzanalyst. Analysiere die Earnings-Reaktion.
User: {ticker} Earnings am {date}:
      Prognose: {pre_assessment}
      Ergebnis: EPS {actual} vs {estimate}, Kurs {move_pct}%
      Patterns: {patterns}
      Was ist die Lektion? Warum hat der Markt so reagiert?
```

### Fallback: Kein LLM konfiguriert

Wenn keine `ARGUS_LLM_*` Variablen gesetzt sind:
- Schicht 1 (API) funktioniert vollständig
- Schicht 2 (Stimmung) wird übersprungen
- Assessment muss manuell per CLI-Prompt eingegeben werden (wie in der Basis-Spec)
- Post-Lektion wird als "Manuell eintragen" markiert

## CLI-Befehle

```bash
# Watchlist verwalten
python argus.py watchlist                        # Zeige Watchlist
python argus.py watchlist --add NVDA AAPL        # Ticker hinzufügen
python argus.py watchlist --remove NVDA          # Ticker entfernen

# Pre-Earnings Analyse (VOR dem Earnings-Termin)
python argus.py earnings NVDA                    # Analyse generieren + speichern

# Post-Earnings Update (NACH dem Earnings-Termin)
python argus.py earnings NVDA --post             # Vergleich: Prognose vs. Realität

# Earnings-Historie
python argus.py earnings-history                 # Letzte 10 Earnings-Analysen
python argus.py earnings-history --ticker NVDA   # Nur für einen Ticker
```

## Collection: `watchlist`

```json
{
  "ticker": "NVDA",
  "added_date": "2026-02-17",
  "notes": "AI-Bellwether"
}
```

Index: `ticker` (unique)

## Collection: `earnings`

```json
{
  "ticker": "NVDA",
  "company": "NVIDIA Corporation",
  "earnings_date": "2026-02-25",
  "created_date": "2026-02-17",

  "pre": {
    "analyzed_at": "2026-02-17",
    "price": 128.50,
    "sma50": 125.00,
    "sma200": 110.00,
    "above_sma50": true,
    "above_sma200": true,
    "rsi_14": 55.2,

    "analyst_consensus": {
      "strong_buy": 35,
      "buy": 12,
      "hold": 5,
      "sell": 1,
      "strong_sell": 0,
      "target_mean": 175.00,
      "upside_pct": 36.2
    },

    "eps_history": [
      {
        "quarter": "Q3 2025",
        "actual": 0.81,
        "estimate": 0.75,
        "surprise_pct": 8.0
      }
    ],
    "beat_rate": "4/4",

    "volatility": {
      "atm_iv": 0.65,
      "expected_move_pct": 8.5,
      "hist_avg_earnings_move_pct": 7.2
    },

    "sentiment_context": {
      "summary": "Analysten mehrheitlich bullish nach starkem Q3. Letzte 6 Wochen: 3 Upgrades, 0 Downgrades. Sektor unter Druck wegen AI-Capex-Fatigue, aber NVDA als Profiteur der Infrastruktur-Ausgaben gesehen.",
      "recent_upgrades": ["Morgan Stanley → Overweight (10.02)", "Goldman Sachs → Buy (03.02)"],
      "recent_downgrades": [],
      "risk_factors": ["AI-Capex-Fatigue könnte auf Guidance drücken", "Hohe Erwartungen eingepreist"],
      "source": "llm"
    },

    "assessment": {
      "direction": "bullish",
      "confidence": "medium",
      "reasoning": "4/4 Beats, starker Analysten-Konsens, IV leicht erhöht. Aber AI-Capex-Fatigue als Risiko.",
      "source": "llm"
    }
  },

  "post": null
}
```

### Post-Earnings Update (wenn `--post` ausgeführt)

Das `post`-Feld wird nach dem Earnings-Termin befüllt:

```json
{
  "post": {
    "analyzed_at": "2026-02-26",
    "eps_actual": 0.89,
    "eps_estimate": 0.82,
    "surprise_pct": 8.5,
    "price_before_close": 128.50,
    "price_after_open": 118.00,
    "price_after_close": 115.00,
    "move_pct": -10.5,
    "volume_vs_avg": 3.5,

    "gap": {
      "type": "gap_down",
      "size_pct": -8.2
    },

    "candle": {
      "pattern": "bearish_engulfing",
      "body_ratio": 2.1
    },

    "breakout": {
      "broke_sma50": true,
      "broke_sma200": false
    },

    "kindle_rule": {
      "signal": "bearish",
      "confirmed": true,
      "trigger": "Gap-Down + Bearish Engulfing + Volume 3.5x"
    },

    "prediction_correct": false,
    "lesson": {
      "text": "Gute Zahlen, aber Markt preist AI-Capex-Sorgen ein. Guidance war schwächer als erhofft.",
      "source": "llm"
    }
  }
}
```

Index: `ticker` + `earnings_date` (compound, unique)

## Pre-Earnings Analyse — Datenfluss

### Schritt 1: API-Daten (yfinance)

| Datenpunkt | yfinance-Methode | Beschreibung |
|-----------|-----------------|-------------|
| Kurs, SMA50, SMA200 | `Ticker.history()` | OHLCV-Daten, SMAs selbst berechnet |
| RSI(14) | Berechnet aus Close-Preisen | Relative Strength Index |
| Analysten-Ratings | `Ticker.get_recommendations()` | Strong Buy/Buy/Hold/Sell/Strong Sell |
| Kursziel | `Ticker.info['targetMeanPrice']` | Durchschnittliches Analysten-Kursziel |
| EPS-History | `Ticker.get_earnings_history()` | Letzte 4 Quartale: Actual vs. Estimate |
| Earnings-Datum | `Ticker.get_earnings_dates()` | Nächster Earnings-Termin |
| Implied Volatility | `Ticker.option_chain()` | ATM-Options-IV für Expected Move |
| Expected Move | Berechnet: `Kurs × IV / sqrt(252)` | Erwartete Kursbewegung am Earnings-Tag |

### Schritt 2: Stimmung & Kontext (LLM + Web Search)

Wenn LLM konfiguriert (`ARGUS_LLM_PROVIDER` gesetzt):
- LLM recherchiert via Web Search nach aktueller Analysten-Stimmung
- Extrahiert: letzte Upgrades/Downgrades, Sektor-Sentiment, Risikofaktoren
- Wird als `pre.sentiment_context` gespeichert

### Schritt 3: Assessment

**Mit LLM:** Assessment wird automatisch generiert — LLM bewertet API-Daten + Stimmung und gibt `direction`, `confidence`, `reasoning` zurück.

**Ohne LLM (Fallback):** User wird interaktiv gefragt:
```
Richtung? [bullish/bearish/neutral]: bullish
Konfidenz? [high/medium/low]: medium
Begründung: 4/4 Beats, starker Konsens
```

## Post-Earnings Analyse — Pattern-Erkennung

Wird automatisch aus den OHLCV-Daten berechnet:

### 1. Gap-Erkennung
```
gap_pct = (open_after - close_before) / close_before × 100
- gap_pct > 1%   → "gap_up"
- gap_pct < -1%  → "gap_down"
- sonst          → "flat"
```

### 2. Volume-Surge
```
volume_ratio = volume_earnings_day / avg_volume_20d
- ratio > 2.0  → Volume-Surge bestätigt
```

### 3. Engulfing-Pattern
```
Body der Earnings-Kerze umschließt Body der Vorkerze komplett:
- bullish_engulfing: Vorkerze rot, Earnings-Kerze grün, größerer Body
- bearish_engulfing: Vorkerze grün, Earnings-Kerze rot, größerer Body
- none: kein Engulfing
```

### 4. Breakout
```
- broke_sma50:  Kurs war über SMA50 und fällt darunter (oder umgekehrt)
- broke_sma200: Kurs war über SMA200 und fällt darunter (oder umgekehrt)
```

### 5. Kindle Rule (Kernindikator)
```
Wenn Gap + Engulfing + Volume-Surge in gleicher Richtung:
  → signal: "bullish" oder "bearish"
  → confirmed: true
  → Hohe Wahrscheinlichkeit dass Kurs in diese Richtung weitergeht

Wenn nicht alle drei bestätigen:
  → confirmed: false
  → Kein klares Signal
```

## Output-Format: Pre-Earnings

```
============================================================
  EARNINGS PRE-ANALYSE: NVDA (NVIDIA Corporation)
============================================================

  Earnings-Datum: 25.02.2026

  Kurs: $128,50  |  SMA50: $125,00  |  SMA200: $110,00
  Über SMA50: Ja  |  Über SMA200: Ja  |  RSI(14): 55,2

  Analysten:
    Strong Buy: 35  |  Buy: 12  |  Hold: 5  |  Sell: 1
    Kursziel: $175,00  |  Upside: +36,2%

  EPS-History (letzte 4 Quartale):
    Q3 2025: 0,81 vs. 0,75 (✓ +8,0%)
    Q2 2025: 0,68 vs. 0,64 (✓ +6,3%)
    Q1 2025: 0,61 vs. 0,58 (✓ +5,2%)
    Q4 2024: 0,52 vs. 0,49 (✓ +6,1%)
  Beat-Rate: 4/4

  Volatilität:
    ATM IV: 65%  |  Expected Move: ±$10,92 (±8,5%)
    Hist. Ø Earnings-Move: ±7,2%

  Stimmung & Kontext (via LLM):
    Analysten mehrheitlich bullish nach starkem Q3.
    Upgrades:   Morgan Stanley → Overweight (10.02), Goldman → Buy (03.02)
    Downgrades: —
    Risiken:    AI-Capex-Fatigue könnte auf Guidance drücken

  Assessment: BULLISH (medium) [LLM]
  Begründung: 4/4 Beats, starker Analysten-Konsens, IV leicht erhöht.
              Aber AI-Capex-Fatigue als Risiko.
```

## Output-Format: Post-Earnings

```
============================================================
  EARNINGS POST-ANALYSE: NVDA (NVIDIA Corporation)
============================================================

  Earnings-Datum: 25.02.2026

  EPS: 0,89 vs. 0,82 (✓ Beat +8,5%)

  Kursbewegung:
    Close vorher: $128,50
    Open danach:  $118,00  (Gap-Down: -8,2%)
    Close danach: $115,00  (Gesamt: -10,5%)
    Volume: 3,5x Durchschnitt

  Pattern-Erkennung:
    Gap:       ⬇ Gap-Down (-8,2%)
    Candle:    Bearish Engulfing (Body-Ratio: 2,1x)
    Breakout:  SMA50 durchbrochen ✔  |  SMA200 gehalten ✔
    Volume:    3,5x → Surge bestätigt

  🔥 KINDLE RULE: BEARISH (bestätigt)
    Trigger: Gap-Down + Bearish Engulfing + Volume 3,5x

  Prognose-Check:
    Vorher: BULLISH (medium)
    Ergebnis: FALSCH ✘
    Lektion: Gute Zahlen, aber Markt preist AI-Capex-Sorgen ein
```

## Validierung

### Enums
- `assessment.direction`: `bullish`, `bearish`, `neutral`
- `assessment.confidence`: `high`, `medium`, `low`
- `gap.type`: `gap_up`, `gap_down`, `flat`
- `candle.pattern`: `bullish_engulfing`, `bearish_engulfing`, `none`
- `kindle_rule.signal`: `bullish`, `bearish`, `none`

### Pflichtfelder Pre
- `ticker`, `earnings_date`, `pre.price`, `pre.analyst_consensus`, `pre.assessment`

### Pflichtfelder Post
- `post.price_before_close`, `post.price_after_close`, `post.move_pct`, `post.prediction_correct`

## Anforderungen

- Alles in `argus.py` (erweitert bestehendes Script)
- Dependencies: `yfinance`, `openai` (optional, für LLM), `anthropic` (optional, für Anthropic)
- LLM-Provider konfigurierbar via `ARGUS_LLM_*` Env-Variablen
- Ohne LLM: Modul funktioniert vollständig, nur Schicht 2 (Stimmung) entfällt
- `source`-Feld bei LLM-generierten Daten: `"llm"` oder `"manual"`
- Rate-Limiting: 1,5s Pause zwischen yfinance-Requests, Retry mit Backoff
- Fehlerbehandlung auf Deutsch
- UTF-8 Encoding (wie gehabt)
