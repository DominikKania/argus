# Argus — Investment Knowledge Base

Persönliches Investment-Wissenssystem mit MongoDB-Backend. Speichert Marktanalysen, trackt Thesen und baut über Zeit ein Gedächtnis auf.

## Module

### Ampel (aktiv)

Signalsystem für den IWDA ETF (iShares Core MSCI World). 4 Indikatoren werden mechanisch + kontextbereinigt bewertet:

| Signal | Grün | Gelb | Rot |
|--------|------|------|-----|
| **Trend** | Kurs > SMA50 > SMA200 | Unter SMA50 oder Puffer < 1% | Unter SMA200 |
| **Volatilität** | VIX < 20, fallend | VIX 20-30 oder steigend | VIX > 30 |
| **Makro** | Spread positiv, Real Yield < 2.5% | Spread negativ oder Real Yield 2.5-3% | Beides negativ |
| **Sentiment** | Keine breiten Risiken | Gemischte Signale | Breite Panik |

Gesamtbewertung: `GREEN` / `GREEN_FRAGILE` / `YELLOW` / `YELLOW_BEARISH` / `RED` / `RED_CAPITULATION`

### Earnings (geplant)

Systematische Einzelaktien-Analyse rund um Quartalszahlen. Spezifikation in `argus-earnings-spec.md`.

## Setup

### Voraussetzungen

- Python 3.10+
- MongoDB (lokal via Docker)
- [Claude Code](https://claude.com/claude-code) (optional, für `/ampel` Skill)

### Installation

```bash
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### Dependencies verwalten

Direkte Abhängigkeiten stehen in `requirements.in`, die eingefrorenen Versionen in `requirements.txt`:

```bash
pip-compile requirements.in
pip-compile --upgrade requirements.in
```

## Verwendung

### Claude Code Skill

```
/ampel
```

Führt eine vollständige Ampel-Analyse durch: Marktdaten per Web-Suche holen, Signale bestimmen, JSON validieren und in MongoDB speichern.

### CLI-Befehle

```bash
# Analyse speichern
python argus.py save --json analysis.json

# Letzte Analyse anzeigen
python argus.py latest

# Verlauf (letzte 10 / alle)
python argus.py history
python argus.py history --all

# Offene Thesen
python argus.py theses

# These auflösen
python argus.py resolve <id> --outcome "..." --accuracy correct

# Audio transkribieren (benötigt faster-whisper)
python argus.py transcribe audio/datei.wav

# Export für Claude-Chat (formatierter Text-Block)
python argus.py export
```

## Datenbank

- **Connection:** `mongodb://root:root@host.docker.internal:27017/?authSource=admin`
- **DB-Name:** `argus`
- **Collections:** `analyses`, `theses`
- **Indexes:** `date` (unique), `rating.overall`, `theses.status`

## Schema

Vollständiges Analyse-Schema in `argus-claude-code-prompt.md`, Beispiel in `example_analysis.json`.

Jedes Sentiment-Event enthält eine `headline` (1 Satz) und eine `summary` (2-3 Sätze Kontext) als Pflichtfelder.
