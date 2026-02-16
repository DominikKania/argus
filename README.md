# Argus — Investment Knowledge Base

Persönliches Investment-Wissenssystem. Speichert Marktanalysen, trackt Thesen und baut über Zeit ein Gedächtnis auf.

**Erstes Modul: Ampel** — Signalsystem das 4 Indikatoren (Trend, Volatilität, Makro, Sentiment) zu einer Gesamtbewertung (GRÜN/GELB/ROT) verdichtet.

## Setup

### Voraussetzungen

- Python 3.10+
- MongoDB (lokal via Docker)

### Installation

```bash
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### Dependencies verwalten

Direkte Abhängigkeiten stehen in `requirements.in`, die eingefrorenen Versionen in `requirements.txt`:

```bash
# Neue Dependency in requirements.in eintragen, dann:
pip-compile requirements.in

# Alle Packages auf neueste Versionen aktualisieren:
pip-compile --upgrade requirements.in
```


## Verwendung

```bash
# Analyse speichern
python argus.py save --json analysis.json

# Letzte Analyse anzeigen
python argus.py latest

# Verlauf (letzte 10)
python argus.py history

# Alle Analysen
python argus.py history --all

# Offene Thesen
python argus.py theses

# These auflösen
python argus.py resolve <id> --outcome "..." --accuracy correct

# Export für Ampel-Prompt (formatierter Text-Block)
python argus.py export
```

## Datenbank

- **DB-Name:** `argus`
- **Collections:** `analyses`, `theses`
- **Indexes:** `date` (unique), `rating.overall`, `theses.status`

## Analyse-JSON Format

Siehe `argus-claude-code-prompt.md` für das vollständige Schema oder `example_analysis.json` für ein Beispiel.
