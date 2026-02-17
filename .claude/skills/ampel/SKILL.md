---
name: ampel
description: Vollständige Ampel-Analyse durchführen (Marktdaten holen, analysieren, in MongoDB speichern)
user-invocable: true
---

# Ampel-Analyse durchführen

Du führst eine vollständige Argus-Ampel-Analyse durch. Folge diesen Schritten exakt:

## Schritt 1: Historie laden

Führe aus:
```bash
python argus.py export
```
Merke dir den Output — er enthält die letzten 5 Analysen und offene Thesen. Das ist dein Kontext für Trendvergleiche.

## Schritt 2: Marktdaten abrufen

Suche per Web nach den aktuellen Daten für **heute** ($CURRENT_DATE):

1. **IWDA / iShares MSCI World ETF (EUNL.DE / IWDA.AS)**: Kurs, SMA50, SMA200, ATH, Golden Cross
2. **VIX (CBOE Volatility Index)**: aktueller Wert + Vorwoche
3. **US-Renditen**: 10Y Treasury Yield, 2Y Treasury Yield
4. **CPI**: letzter veröffentlichter US-CPI-Wert
5. **Sentiment-Events**: relevante Markt-Nachrichten der letzten Tage

Berechne daraus:
- `delta_ath_pct`: ((Kurs - ATH) / ATH) * 100
- `puffer_sma50_pct`: ((Kurs - SMA50) / SMA50) * 100
- `spread`: US10Y - US2Y
- `spread_direction`: "widening" / "narrowing" / "flat" (Vergleich mit letzter Analyse)
- `real_yield`: US10Y - CPI
- `vix.direction`: "rising" / "falling" / "flat" (Vergleich mit Vorwoche)

## Schritt 3: Mechanische Signale bestimmen

### Trend
- **green**: Kurs > SMA50 UND SMA50 > SMA200 (Golden Cross)
- **yellow**: Kurs > SMA200 aber unter SMA50, ODER Puffer < 1%
- **red**: Kurs < SMA200

### Volatilität
- **green**: VIX < 20 UND fallend oder stabil
- **yellow**: VIX 20-30 ODER steigend
- **red**: VIX > 30

### Makro
- **green**: Spread positiv UND Real Yield < 2.5%
- **yellow**: Spread negativ ODER Real Yield 2.5-3%
- **red**: Spread negativ UND Real Yield > 3%

### Sentiment
- **green**: keine marktbreiten negativen Events
- **yellow**: gemischte Signale oder sektorspezifische Risiken
- **red**: breite Panik, multiple negative Katalysatoren

## Schritt 4: Kontext-Signale + Rating

Bewerte jedes mechanische Signal im Kontext:
- Gibt es Faktoren die das Signal abschwächen oder verstärken?
- Setze `context` auf die angepasste Farbe (kann vom mechanischen Signal abweichen)
- Schreibe eine kurze `note` pro Signal

**Mechanical Score**: Zähle grüne mechanische Signale (0-4)

**Overall Rating**:
- `GREEN`: 4/4 grün oder 3/4 grün mit stabilem Kontext
- `GREEN_FRAGILE`: 3/4 grün aber mit Risikofaktoren (z.B. niedriger Puffer)
- `YELLOW`: 2/4 grün oder gemischte Signale
- `YELLOW_BEARISH`: 1-2/4 grün mit negativem Trend
- `RED`: 0-1/4 grün, multiple Warnsignale
- `RED_CAPITULATION`: 0/4 grün, Panik-Indikatoren

**Recommendation**:
- `hold`: Keine Änderung nötig
- `buy`: Gelegenheit bei Dip in grünem Umfeld
- `partial_sell`: Risikoreduktion sinnvoll
- `hedge`: Absicherung empfohlen
- `wait`: Unklar, abwarten

## Schritt 5: JSON erstellen und speichern

Erstelle das vollständige Analyse-JSON nach dem Schema in `argus-claude-code-prompt.md`. Schreibe es nach `analysis_today.json` und führe aus:

```bash
python argus.py save --json analysis_today.json
```

## Schritt 6: Ergebnis anzeigen

Führe aus:
```bash
python argus.py latest
```

Zeige dem User eine kurze Zusammenfassung:
- Datum + Gesamtbewertung
- Änderungen gegenüber letzter Analyse
- Ggf. neue These oder aufgelöste These
- Eskalations-Trigger wenn relevant
