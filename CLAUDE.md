# Argus — Investment Knowledge Base

Persönliches Investment-Wissenssystem mit MongoDB-Backend. Speichert Marktanalysen, trackt Thesen, baut Gedächtnis auf.

## Modul: Ampel

Signalsystem: 4 Indikatoren (Trend, Volatilität, Makro, Sentiment) → Gesamtbewertung (GRÜN/GELB/ROT) → Handlungsempfehlung.

## Tech

- **Script:** `argus.py` (CLI via argparse)
- **DB:** MongoDB `argus` — Collections: `analyses`, `theses`
- **Connection:** `mongodb://root:root@host.docker.internal:27017/?authSource=admin`
- **Python:** venv im Projektordner, Dependencies via `requirements.in` / `pip-compile`

## Schema

Vollständiges Analyse-Schema siehe `argus-claude-code-prompt.md`, Beispiel siehe `example_analysis.json`.

## Commands

- `/project:ampel` — Vollständige Ampel-Analyse durchführen (Daten holen → analysieren → speichern)
