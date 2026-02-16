#!/usr/bin/env python3
"""Argus — Investment Knowledge Base CLI"""

import argparse
import json
import os
import sys
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, ASCENDING

# ── Konstanten ──────────────────────────────────────────────────────────────

DB_NAME = "argus"
VALID_COLORS = {"green", "yellow", "red"}
VALID_DIRECTIONS = {"rising", "falling", "flat"}
VALID_ACTIONS = {"hold", "buy", "partial_sell", "hedge", "wait"}
VALID_ACCURACY = {"correct", "partially_correct", "wrong"}
VALID_THESIS_STATUS = {"open", "resolved"}
VALID_OVERALL_RATINGS = {
    "GREEN", "GREEN_FRAGILE", "YELLOW", "YELLOW_BEARISH", "RED", "RED_CAPITULATION",
}

REQUIRED_MARKET_FIELDS = ["price", "sma50", "sma200", "ath", "delta_ath_pct",
                          "puffer_sma50_pct", "golden_cross", "vix", "yields"]
REQUIRED_VIX_FIELDS = ["value", "direction", "prev_week"]
REQUIRED_YIELDS_FIELDS = ["us10y", "us2y", "spread", "spread_direction",
                          "real_yield", "cpi"]
REQUIRED_SIGNAL_FIELDS = ["mechanical", "context"]
SIGNAL_NAMES = ["trend", "volatility", "macro", "sentiment"]
REQUIRED_RATING_FIELDS = ["mechanical_score", "overall", "reasoning"]
REQUIRED_RECOMMENDATION_FIELDS = ["action", "detail"]
REQUIRED_TOP_FIELDS = ["date", "market", "signals", "rating", "recommendation"]

# ── Emoji-Mapping ───────────────────────────────────────────────────────────

COLOR_EMOJI = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}

OVERALL_DISPLAY = {
    "GREEN": "GR\u00dcN",
    "GREEN_FRAGILE": "GR\u00dcN (fragil)",
    "YELLOW": "GELB",
    "YELLOW_BEARISH": "GELB (b\u00e4risch)",
    "RED": "ROT",
    "RED_CAPITULATION": "ROT (Kapitulation)",
}

ACTION_DISPLAY = {
    "hold": "Halten",
    "buy": "Kaufen",
    "partial_sell": "Teilverkauf",
    "hedge": "Absichern",
    "wait": "Abwarten",
}


# ── DB-Verbindung ──────────────────────────────────────────────────────────

def get_db():
    uri = os.environ.get("ARGUS_MONGO_URI", "mongodb://root:root@host.docker.internal:27017/?authSource=admin")
    client = MongoClient(uri)
    return client[DB_NAME]


def ensure_indexes(db):
    db.analyses.create_index([("date", ASCENDING)], unique=True)
    db.analyses.create_index([("rating.overall", ASCENDING)])
    db.theses.create_index([("status", ASCENDING)])


# ── Validierung ─────────────────────────────────────────────────────────────

def validate_analysis(data):
    errors = []

    for field in REQUIRED_TOP_FIELDS:
        if field not in data:
            errors.append(f"Pflichtfeld '{field}' fehlt.")

    if errors:
        return errors

    # date
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        errors.append("Feld 'date' muss Format YYYY-MM-DD haben.")

    # market
    market = data["market"]
    for f in REQUIRED_MARKET_FIELDS:
        if f not in market:
            errors.append(f"Pflichtfeld 'market.{f}' fehlt.")

    if "vix" in market:
        for f in REQUIRED_VIX_FIELDS:
            if f not in market["vix"]:
                errors.append(f"Pflichtfeld 'market.vix.{f}' fehlt.")
        if market["vix"].get("direction") not in VALID_DIRECTIONS:
            errors.append(f"'market.vix.direction' muss einer von {sorted(VALID_DIRECTIONS)} sein.")

    if "yields" in market:
        for f in REQUIRED_YIELDS_FIELDS:
            if f not in market["yields"]:
                errors.append(f"Pflichtfeld 'market.yields.{f}' fehlt.")
        if market["yields"].get("spread_direction") not in VALID_DIRECTIONS:
            errors.append(f"'market.yields.spread_direction' muss einer von {sorted(VALID_DIRECTIONS)} sein.")

    # signals
    signals = data["signals"]
    for sig in SIGNAL_NAMES:
        if sig not in signals:
            errors.append(f"Signal '{sig}' fehlt in 'signals'.")
            continue
        for f in REQUIRED_SIGNAL_FIELDS:
            if f not in signals[sig]:
                errors.append(f"Pflichtfeld 'signals.{sig}.{f}' fehlt.")
        if signals[sig].get("mechanical") not in VALID_COLORS:
            errors.append(f"'signals.{sig}.mechanical' muss einer von {sorted(VALID_COLORS)} sein.")
        if signals[sig].get("context") not in VALID_COLORS:
            errors.append(f"'signals.{sig}.context' muss einer von {sorted(VALID_COLORS)} sein.")

    # rating
    rating = data["rating"]
    for f in REQUIRED_RATING_FIELDS:
        if f not in rating:
            errors.append(f"Pflichtfeld 'rating.{f}' fehlt.")
    if rating.get("overall") not in VALID_OVERALL_RATINGS:
        errors.append(f"'rating.overall' muss einer von {sorted(VALID_OVERALL_RATINGS)} sein.")

    # recommendation
    rec = data["recommendation"]
    for f in REQUIRED_RECOMMENDATION_FIELDS:
        if f not in rec:
            errors.append(f"Pflichtfeld 'recommendation.{f}' fehlt.")
    if rec.get("action") not in VALID_ACTIONS:
        errors.append(f"'recommendation.action' muss einer von {sorted(VALID_ACTIONS)} sein.")

    # sentiment_events (optional, aber wenn vorhanden validieren)
    for i, evt in enumerate(data.get("sentiment_events", []) or []):
        if "headline" not in evt:
            errors.append(f"'sentiment_events[{i}].headline' fehlt.")

    return errors


# ── Befehle ─────────────────────────────────────────────────────────────────

def cmd_save(args):
    db = get_db()
    ensure_indexes(db)

    try:
        with open(args.json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Fehler: Datei '{args.json}' nicht gefunden.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Fehler: Ung\u00fcltiges JSON — {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_analysis(data)
    if errors:
        print("Validierungsfehler:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # weekday automatisch setzen
    dt = datetime.strptime(data["date"], "%Y-%m-%d")
    weekdays_de = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    data["weekday"] = weekdays_de[dt.weekday()]

    # Prüfen ob Analyse für dieses Datum bereits existiert
    existing = db.analyses.find_one({"date": data["date"]})
    if existing:
        print(f"Fehler: Analyse f\u00fcr {data['date']} existiert bereits. L\u00f6sche sie zuerst oder w\u00e4hle ein anderes Datum.", file=sys.stderr)
        sys.exit(1)

    result = db.analyses.insert_one(data)
    analysis_id = result.inserted_id
    print(f"Analyse gespeichert: {data['date']} | {OVERALL_DISPLAY.get(data['rating']['overall'], data['rating']['overall'])}")

    # These automatisch anlegen wenn vorhanden
    thesis_data = data.get("thesis")
    if thesis_data and thesis_data.get("statement"):
        thesis_doc = {
            "created_date": data["date"],
            "analysis_id": analysis_id,
            "statement": thesis_data["statement"],
            "catalyst": thesis_data.get("catalyst"),
            "catalyst_date": thesis_data.get("catalyst_date"),
            "expected_if_positive": thesis_data.get("expected_if_positive"),
            "expected_if_negative": thesis_data.get("expected_if_negative"),
            "status": "open",
            "resolution": None,
            "resolution_date": None,
            "accuracy": None,
            "lessons_learned": None,
        }
        db.theses.insert_one(thesis_doc)
        print(f"These angelegt: {thesis_data['statement'][:60]}...")


def cmd_latest(args):
    db = get_db()
    doc = db.analyses.find_one(sort=[("date", -1)])
    if not doc:
        print("Keine Analysen vorhanden.")
        return
    print_analysis_detail(doc)


def cmd_history(args):
    db = get_db()
    limit = 0 if args.all else 10
    cursor = db.analyses.find(sort=[("date", -1)])
    if limit:
        cursor = cursor.limit(limit)

    docs = list(cursor)
    if not docs:
        print("Keine Analysen vorhanden.")
        return

    print_history_table(docs)


def cmd_theses(args):
    db = get_db()
    docs = list(db.theses.find({"status": "open"}).sort("created_date", -1))
    if not docs:
        print("Keine offenen Thesen.")
        return

    print(f"\n{'ID':<26} {'Datum':<12} {'Statement':<50} {'Katalysator'}")
    print("-" * 110)
    for doc in docs:
        tid = str(doc["_id"])[:12]
        date = doc["created_date"]
        stmt = doc["statement"][:48]
        cat = doc.get("catalyst") or "-"
        cat_date = doc.get("catalyst_date") or ""
        if cat_date:
            cat = f"{cat} ({cat_date})"
        print(f"{tid:<26} {date:<12} {stmt:<50} {cat}")


def cmd_resolve(args):
    db = get_db()

    try:
        oid = ObjectId(args.id)
    except Exception:
        print(f"Fehler: Ung\u00fcltige ID '{args.id}'.", file=sys.stderr)
        sys.exit(1)

    thesis = db.theses.find_one({"_id": oid})
    if not thesis:
        print(f"Fehler: These mit ID '{args.id}' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    if thesis["status"] == "resolved":
        print(f"These bereits aufgel\u00f6st am {thesis.get('resolution_date', '?')}.", file=sys.stderr)
        sys.exit(1)

    if args.accuracy not in VALID_ACCURACY:
        print(f"Fehler: --accuracy muss einer von {sorted(VALID_ACCURACY)} sein.", file=sys.stderr)
        sys.exit(1)

    update = {
        "status": "resolved",
        "resolution": args.outcome,
        "resolution_date": datetime.now().strftime("%Y-%m-%d"),
        "accuracy": args.accuracy,
    }
    if args.lessons:
        update["lessons_learned"] = args.lessons

    db.theses.update_one({"_id": oid}, {"$set": update})
    print(f"These aufgel\u00f6st: {thesis['statement'][:60]}...")
    print(f"  Ergebnis: {args.outcome}")
    print(f"  Genauigkeit: {args.accuracy}")


def cmd_export(args):
    db = get_db()

    # Letzte 5 Analysen für Verlauf
    docs = list(db.analyses.find(sort=[("date", -1)]).limit(5))
    if not docs:
        print("Keine Analysen vorhanden.")
        return

    docs_asc = list(reversed(docs))
    latest = docs[0]

    # Offene Thesen
    theses = list(db.theses.find({"status": "open"}).sort("created_date", -1))

    print("=== ARGUS EXPORT ===\n")

    # Verlauf
    print("\U0001f4ca VERLAUF (letzte 5 Analysen)")
    print("| Datum | Kurs | \u0394 ATH | T | V | M | S | Gesamt | Empfehlung |")
    print("|-------|------|-------|---|---|---|---|--------|------------|")
    for doc in docs_asc:
        date = format_date_short(doc["date"])
        price = format_price(doc["market"]["price"])
        delta = f"{doc['market']['delta_ath_pct']:+.1f}%".replace(".", ",")
        t = signal_emoji(doc["signals"]["trend"])
        v = signal_emoji(doc["signals"]["volatility"])
        m = signal_emoji(doc["signals"]["macro"])
        s = signal_emoji(doc["signals"]["sentiment"])
        overall = OVERALL_DISPLAY.get(doc["rating"]["overall"], doc["rating"]["overall"])
        action = ACTION_DISPLAY.get(doc["recommendation"]["action"], doc["recommendation"]["action"])
        print(f"| {date} | {price} | {delta} | {t} | {v} | {m} | {s} | {overall} | {action} |")

    # Offene Thesen
    if theses:
        print(f"\n\U0001f4cc OFFENE THESEN")
        for t in theses:
            date = format_date_short(t["created_date"])
            cat_info = ""
            if t.get("catalyst_date"):
                cat_info = f" (Katalysator: {format_date_short(t['catalyst_date'])})"
            print(f"- [{date}] {t['statement']}{cat_info}")

    # Letzte Analyse
    print(f"\n\U0001f4c8 LETZTE ANALYSE ({format_date_short(latest['date'])})")
    score = latest["rating"]["mechanical_score"]
    overall = OVERALL_DISPLAY.get(latest["rating"]["overall"], latest["rating"]["overall"])
    print(f"- Gesamt: {overall} | Mechanisch: {score}/4")

    thesis = latest.get("thesis")
    if thesis and thesis.get("statement"):
        cat_date = thesis.get("catalyst_date", "")
        if cat_date:
            cat_date = f" {format_date_short(cat_date)}"
        print(f"- These: {thesis.get('catalyst', '')}{cat_date}")

    trigger = latest.get("escalation_trigger")
    if trigger:
        print(f"- Trigger: {trigger}")

    print("\n=== ENDE EXPORT ===")


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def format_date_short(date_str):
    """'2026-02-15' -> '15.02'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m")
    except (ValueError, TypeError):
        return date_str or "?"


def format_price(price):
    """112.6 -> '112,6€'"""
    return f"{price:,.1f}\u20ac".replace(",", "X").replace(".", ",").replace("X", ".")


def signal_emoji(signal):
    """Gibt Context-Farbe als Emoji zurück (context > mechanical)."""
    color = signal.get("context", signal.get("mechanical", "yellow"))
    return COLOR_EMOJI.get(color, "\u2753")


def print_history_table(docs):
    delta_header = "\u0394 ATH"
    print(f"\n{'Datum':<12} {'Kurs':>10} {delta_header:>8} {'T':>3} {'V':>3} {'M':>3} {'S':>3}  {'Gesamt':<20} {'Empfehlung'}")
    print("-" * 90)
    for doc in docs:
        date = doc["date"]
        price = format_price(doc["market"]["price"])
        delta = f"{doc['market']['delta_ath_pct']:+.1f}%"
        t = signal_emoji(doc["signals"]["trend"])
        v = signal_emoji(doc["signals"]["volatility"])
        m = signal_emoji(doc["signals"]["macro"])
        s = signal_emoji(doc["signals"]["sentiment"])
        overall = OVERALL_DISPLAY.get(doc["rating"]["overall"], doc["rating"]["overall"])
        action = ACTION_DISPLAY.get(doc["recommendation"]["action"], doc["recommendation"]["action"])
        print(f"{date:<12} {price:>10} {delta:>8} {t:>3} {v:>3} {m:>3} {s:>3}  {overall:<20} {action}")


def print_analysis_detail(doc):
    date = doc["date"]
    weekday = doc.get("weekday", "")
    m = doc["market"]
    signals = doc["signals"]
    rating = doc["rating"]
    rec = doc["recommendation"]

    overall = OVERALL_DISPLAY.get(rating["overall"], rating["overall"])
    action = ACTION_DISPLAY.get(rec["action"], rec["action"])

    print(f"\n{'='*60}")
    print(f"  ANALYSE {date} ({weekday})")
    print(f"{'='*60}")

    print(f"\n  Markt:")
    print(f"    Kurs: {format_price(m['price'])}  |  SMA50: {m['sma50']}  |  SMA200: {m['sma200']}")
    print(f"    ATH: {m['ath']}  |  \u0394 ATH: {m['delta_ath_pct']}%  |  Puffer SMA50: {m['puffer_sma50_pct']}%")
    print(f"    Golden Cross: {'Ja' if m['golden_cross'] else 'Nein'}")

    vix = m.get("vix", {})
    print(f"    VIX: {vix.get('value', '?')} ({vix.get('direction', '?')}) | Vorwoche: {vix.get('prev_week', '?')}")

    y = m.get("yields", {})
    print(f"    US10Y: {y.get('us10y', '?')}  |  US2Y: {y.get('us2y', '?')}  |  Spread: {y.get('spread', '?')} ({y.get('spread_direction', '?')})")
    print(f"    Real Yield: {y.get('real_yield', '?')}  |  CPI: {y.get('cpi', '?')}")

    print(f"\n  Signale:")
    for name in SIGNAL_NAMES:
        sig = signals[name]
        mech = COLOR_EMOJI.get(sig["mechanical"], "?")
        ctx = COLOR_EMOJI.get(sig["context"], "?")
        note = sig.get("note", "")
        label = name.capitalize()
        print(f"    {label:<12} Mech: {mech}  Kontext: {ctx}  {note}")

    print(f"\n  Bewertung: {overall}  (Mechanisch: {rating['mechanical_score']}/4)")
    print(f"  Begr\u00fcndung: {rating['reasoning']}")

    print(f"\n  Empfehlung: {action}")
    print(f"  Detail: {rec['detail']}")

    # These
    thesis = doc.get("thesis")
    if thesis and thesis.get("statement"):
        print(f"\n  These: {thesis['statement']}")
        if thesis.get("catalyst"):
            print(f"  Katalysator: {thesis['catalyst']} ({thesis.get('catalyst_date', '?')})")

    # Escalation
    trigger = doc.get("escalation_trigger")
    if trigger:
        print(f"\n  Eskalations-Trigger: {trigger}")

    crash = doc.get("crash_rule_active")
    if crash:
        print(f"  Crash-Regel: AKTIV")

    # Sentiment Events
    events = doc.get("sentiment_events")
    if events:
        print(f"\n  Sentiment-Events:")
        for evt in events:
            primary = " [PRIM\u00c4R]" if evt.get("is_primary") else ""
            print(f"    - {evt['headline']}{primary} (Risiko: {evt.get('cascade_risk', '?')})")

    print()


# ── CLI Setup ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="argus",
        description="Argus \u2014 Investment Knowledge Base",
    )
    sub = parser.add_subparsers(dest="command")

    # save
    p_save = sub.add_parser("save", help="Analyse aus JSON-Datei speichern")
    p_save.add_argument("--json", required=True, help="Pfad zur JSON-Datei")

    # latest
    sub.add_parser("latest", help="Letzte Analyse anzeigen")

    # history
    p_hist = sub.add_parser("history", help="Verlauf anzeigen")
    p_hist.add_argument("--all", action="store_true", help="Alle Analysen anzeigen")

    # theses
    sub.add_parser("theses", help="Offene Thesen anzeigen")

    # resolve
    p_res = sub.add_parser("resolve", help="These aufl\u00f6sen")
    p_res.add_argument("id", help="These-ID (MongoDB ObjectId)")
    p_res.add_argument("--outcome", required=True, help="Was ist passiert?")
    p_res.add_argument("--accuracy", required=True,
                       choices=sorted(VALID_ACCURACY),
                       help="Genauigkeit: correct, partially_correct, wrong")
    p_res.add_argument("--lessons", help="Lessons Learned (optional)")

    # export
    sub.add_parser("export", help="Formatierten Export f\u00fcr Claude-Chat")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "save": cmd_save,
        "latest": cmd_latest,
        "history": cmd_history,
        "theses": cmd_theses,
        "resolve": cmd_resolve,
        "export": cmd_export,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
