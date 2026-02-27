#!/usr/bin/env python3
"""Argus — Investment Knowledge Base CLI"""

import argparse
import io
import json
import os
import sys
from datetime import datetime

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
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
    db.prices.create_index([("ticker", ASCENDING), ("date", ASCENDING)], unique=True)
    db.watchlist.create_index([("ticker", ASCENDING)], unique=True)
    db.researches.create_index([("topic", ASCENDING)], unique=True)
    db.researches.create_index([("status", ASCENDING)])
    db.news_topics.create_index([("topic", ASCENDING)], unique=True)
    db.news_topics.create_index([("active", ASCENDING)])
    db.news_results.create_index([("topic", ASCENDING), ("date", ASCENDING)], unique=True)
    db.news_results.create_index([("date", ASCENDING)])

    # IWDA.AS als Default-Eintrag
    db.watchlist.update_one(
        {"ticker": "IWDA.AS"},
        {"$setOnInsert": {
            "ticker": "IWDA.AS",
            "name": "iShares Core MSCI World UCITS ETF",
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "category": "etf",
        }},
        upsert=True,
    )


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
        if "summary" not in evt:
            errors.append(f"'sentiment_events[{i}].summary' fehlt.")

    return errors


# ── Befehle ─────────────────────────────────────────────────────────────────

def save_analysis(db, data):
    """Speichert eine validierte Analyse in MongoDB und erstellt ggf. eine These.

    Wird von cmd_save() und ampel_auto.run_auto_ampel() genutzt.
    """
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

    save_analysis(db, data)


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


def cmd_transcribe(args):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("Fehler: faster-whisper nicht installiert. Bitte 'pip install faster-whisper' ausführen.", file=sys.stderr)
        sys.exit(1)

    audio_path = args.file
    if not os.path.isfile(audio_path):
        print(f"Fehler: Datei '{audio_path}' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    model_size = args.model
    language = args.language

    print(f"Lade Modell '{model_size}'...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transkribiere '{os.path.basename(audio_path)}'...", file=sys.stderr)
    segments, info = model.transcribe(audio_path, language=language)

    print(f"Sprache: {info.language} (Konfidenz: {info.language_probability:.0%})\n", file=sys.stderr)

    full_text = []
    for segment in segments:
        full_text.append(segment.text.strip())

    transcript = " ".join(full_text)
    print(transcript)


def cmd_research(args):
    from backend.llm import call_llm as api_call_llm

    db = get_db()
    ensure_indexes(db)

    action = args.research_action or "list"

    if action == "list":
        docs = list(db.researches.find({}, {"results": 0}).sort("updated_date", -1))
        if not docs:
            print("Keine Research-Themen vorhanden.")
            return
        print(f"\n{'Topic':<30} {'Status':<12} {'Erstellt':<12} {'Letzter Lauf'}")
        print("-" * 70)
        for doc in docs:
            last_run = doc.get("last_run_date") or "-"
            print(f"{doc['title'][:28]:<30} {doc['status']:<12} {doc['created_date']:<12} {last_run}")
        print()

    elif action == "add":
        import re as re_mod
        title = args.title
        slug = title.lower()
        for char, repl in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
            slug = slug.replace(char, repl)
        slug = re_mod.sub(r"[^a-z0-9]+", "-", slug).strip("-")

        existing = db.researches.find_one({"topic": slug})
        if existing:
            print(f"Fehler: Topic '{slug}' existiert bereits.", file=sys.stderr)
            sys.exit(1)

        print(f"Generiere Prompt für '{title}'...")
        from backend.routers.research import PROMPT_HELPER_SYSTEM
        try:
            prompt = api_call_llm(
                PROMPT_HELPER_SYSTEM,
                [{"role": "user", "content": f"Erstelle einen Research-Prompt zum Thema: {title}"}],
            )
        except Exception as e:
            print(f"Fehler bei Prompt-Generierung: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"\n--- Generierter Prompt ---\n{prompt}\n--- Ende ---\n")

        now = datetime.now().strftime("%Y-%m-%d")
        doc = {
            "topic": slug,
            "title": title,
            "prompt": prompt,
            "status": "ready",
            "results": None,
            "relevance_summary": None,
            "error_message": None,
            "created_date": now,
            "updated_date": now,
            "last_run_date": None,
        }
        db.researches.insert_one(doc)
        print(f"Research-Topic '{title}' (slug: {slug}) erstellt.")

    elif action == "run":
        topic_slug = args.topic
        doc = db.researches.find_one({"topic": topic_slug})
        if not doc:
            print(f"Fehler: Topic '{topic_slug}' nicht gefunden.", file=sys.stderr)
            sys.exit(1)

        if not doc.get("prompt", "").strip():
            print("Fehler: Kein Prompt definiert.", file=sys.stderr)
            sys.exit(1)

        print(f"Starte Research für '{doc['title']}'...")
        db.researches.update_one({"_id": doc["_id"]}, {"$set": {"status": "running"}})

        # Marktkontext laden
        analysis = db.analyses.find_one(sort=[("date", -1)])
        market_context = ""
        if analysis:
            analysis.pop("_id", None)
            analysis.pop("simplified", None)
            market_context = (
                "\n\n## AKTUELLER MARKTKONTEXT\n"
                + json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
            )

        from backend.routers.research import RESEARCH_SYSTEM_PROMPT, _extract_relevance_summary
        try:
            results = api_call_llm(
                RESEARCH_SYSTEM_PROMPT,
                [{"role": "user", "content": doc["prompt"] + market_context}],
            )
        except Exception as e:
            db.researches.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "error", "error_message": str(e)}},
            )
            print(f"Fehler: {e}", file=sys.stderr)
            sys.exit(1)

        relevance = _extract_relevance_summary(results)
        now = datetime.now().strftime("%Y-%m-%d")
        db.researches.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "status": "completed",
                "results": results,
                "relevance_summary": relevance,
                "error_message": None,
                "updated_date": now,
                "last_run_date": now,
            }},
        )
        print(f"Research abgeschlossen für '{doc['title']}'.")
        if relevance:
            print(f"Relevanz: {relevance}")

    elif action == "show":
        topic_slug = args.topic
        doc = db.researches.find_one({"topic": topic_slug})
        if not doc:
            print(f"Fehler: Topic '{topic_slug}' nicht gefunden.", file=sys.stderr)
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"  {doc['title']} ({doc['status']})")
        print(f"{'='*60}")
        print(f"\nPrompt:\n{doc['prompt']}")
        if doc.get("results"):
            print(f"\n{'─'*60}")
            print(f"Ergebnis ({doc.get('last_run_date', '?')}):\n")
            print(doc["results"])
        if doc.get("relevance_summary"):
            print(f"\nRelevanz: {doc['relevance_summary']}")
        if doc.get("error_message"):
            print(f"\nFehler: {doc['error_message']}")
        print()

    elif action == "delete":
        topic_slug = args.topic
        result = db.researches.delete_one({"topic": topic_slug})
        if result.deleted_count:
            print(f"Topic '{topic_slug}' gelöscht.")
        else:
            print(f"Fehler: Topic '{topic_slug}' nicht gefunden.", file=sys.stderr)
            sys.exit(1)


def cmd_auto_ampel(args):
    from ampel_auto import setup_logging, run_auto_ampel

    setup_logging()
    db = get_db()
    ensure_indexes(db)

    result = run_auto_ampel(
        db,
        date_override=args.date,
        cpi_override=args.cpi,
        dry_run=args.dry_run,
    )

    if result and not args.dry_run:
        print()
        print_analysis_detail(result)


def cmd_watchlist(args):
    db = get_db()
    ensure_indexes(db)

    action = args.watchlist_action or "show"

    if action == "show":
        docs = list(db.watchlist.find().sort("ticker", 1))
        if not docs:
            print("Watchlist ist leer.")
            return
        print(f"\n{'Ticker':<12} {'Name':<40} {'Kategorie':<10} {'Hinzugefügt'}")
        print("-" * 80)
        for doc in docs:
            print(f"{doc['ticker']:<12} {doc.get('name', '?'):<40} {doc.get('category', '?'):<10} {doc.get('added_date', '?')}")
        print()

    elif action == "add":
        import yfinance as yf
        for ticker in args.tickers:
            ticker = ticker.upper()
            try:
                info = yf.Ticker(ticker).info
                name = info.get("shortName") or info.get("longName") or ticker
            except Exception:
                name = ticker
            doc = {
                "ticker": ticker,
                "name": name,
                "added_date": datetime.now().strftime("%Y-%m-%d"),
                "category": "etf" if any(k in ticker.upper() for k in ["IWDA", "EUNL", "ETF"]) else "stock",
            }
            db.watchlist.update_one({"ticker": ticker}, {"$set": doc}, upsert=True)
            print(f"Hinzugefügt: {ticker} — {name}")

    elif action == "remove":
        ticker = args.ticker.upper()
        if ticker == "IWDA.AS":
            print("Fehler: IWDA.AS kann nicht entfernt werden (Default-ETF).", file=sys.stderr)
            sys.exit(1)
        result = db.watchlist.delete_one({"ticker": ticker})
        if result.deleted_count:
            print(f"Entfernt: {ticker}")
        else:
            print(f"Fehler: '{ticker}' nicht in Watchlist.", file=sys.stderr)
            sys.exit(1)


def cmd_fetch(args):
    import yfinance as yf

    db = get_db()
    ensure_indexes(db)

    period = args.period or "5d"

    # Ticker bestimmen
    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = [doc["ticker"] for doc in db.watchlist.find().sort("ticker", 1)]
        if not tickers:
            print("Watchlist ist leer. Füge zuerst Ticker hinzu: argus.py watchlist add NVDA")
            return

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            # Für SMA-Berechnung brauchen wir mindestens 200 Tage
            hist = t.history(period="2y")
            if hist.empty:
                print(f"  {ticker}: Keine Daten erhalten", file=sys.stderr)
                continue

            close = hist["Close"]
            sma50_series = close.rolling(50).mean()
            sma200_series = close.rolling(200).mean()

            # Nur den gewünschten Zeitraum speichern
            if period == "max" or period == "2y":
                save_hist = hist
            else:
                # Anzahl Tage aus period ableiten
                period_map = {"5d": 5, "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}
                days = period_map.get(period, 5)
                save_hist = hist.tail(days)

            count = 0
            for idx in save_hist.index:
                date_str = idx.strftime("%Y-%m-%d")
                row = save_hist.loc[idx]
                sma50_val = sma50_series.get(idx)
                sma200_val = sma200_series.get(idx)

                doc = {
                    "ticker": ticker,
                    "date": date_str,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
                if sma50_val and not (sma50_val != sma50_val):  # NaN check
                    doc["sma50"] = round(float(sma50_val), 2)
                if sma200_val and not (sma200_val != sma200_val):  # NaN check
                    doc["sma200"] = round(float(sma200_val), 2)

                db.prices.update_one(
                    {"ticker": ticker, "date": date_str},
                    {"$set": doc},
                    upsert=True,
                )
                count += 1

            print(f"{ticker}: {count} Tage gespeichert")

        except Exception as e:
            print(f"{ticker}: Fehler — {e}", file=sys.stderr)


def cmd_prices(args):
    db = get_db()
    ticker = args.ticker.upper()

    query = {"ticker": ticker}
    cursor = db.prices.find(query).sort("date", -1)

    if not args.all:
        days = args.days or 10
        cursor = cursor.limit(days)

    docs = list(cursor)
    if not docs:
        print(f"Keine Kursdaten für '{ticker}'. Zuerst laden: argus.py fetch --ticker {ticker} --period 1y")
        return

    # Name aus Watchlist holen
    wl = db.watchlist.find_one({"ticker": ticker})
    name = wl["name"] if wl else ticker
    print(f"\n{ticker} — {name}")
    print(f"{'Datum':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>10} {'SMA50':>8} {'SMA200':>8}")
    print("-" * 84)

    for doc in docs:
        vol = doc.get("volume", 0)
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        elif vol >= 1_000:
            vol_str = f"{vol/1_000:.0f}K"
        else:
            vol_str = str(vol)

        sma50 = f"{doc['sma50']:.2f}" if "sma50" in doc else "-"
        sma200 = f"{doc['sma200']:.2f}" if "sma200" in doc else "-"

        print(f"{doc['date']:<12} {doc['open']:>8.2f} {doc['high']:>8.2f} {doc['low']:>8.2f} {doc['close']:>8.2f} {vol_str:>10} {sma50:>8} {sma200:>8}")

    print()


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

    # Erweiterte Marktdaten
    sr = m.get("sector_rotation")
    if sr and sr.get("sectors"):
        print(f"\n  Sektor-Rotation (1M):")
        for name, data in sr["sectors"].items():
            print(f"    {name.replace('_', ' ').title()}: {data['perf_1m']:+.2f}%")
        if sr.get("risk_on_vs_off") is not None:
            print(f"    Risk-On vs. Defensive: {sr['risk_on_vs_off']:+.2f}pp")

    reg = m.get("regional")
    if reg:
        parts = []
        if reg.get("spy_perf_1m") is not None:
            parts.append(f"USA: {reg['spy_perf_1m']:+.2f}%")
        if reg.get("ezu_perf_1m") is not None:
            parts.append(f"Europa: {reg['ezu_perf_1m']:+.2f}%")
        if parts:
            print(f"  Regional (1M): {' | '.join(parts)}")
        if reg.get("usa_vs_europe") is not None:
            print(f"    USA vs Europa: {reg['usa_vs_europe']:+.2f}pp")

    pc = m.get("put_call")
    if pc:
        print(f"    Put/Call: {pc['ratio']:.2f} ({pc['signal']})")

    seas = m.get("seasonality")
    if seas:
        print(f"    Saisonalität: avg {seas['avg_return_pct']:+.2f}% ({seas['seasonal_bias']})")

    # LLM Market Context
    mctx = doc.get("market_context")
    if mctx:
        notes = [(k.replace("_note", "").replace("_", " ").title(), v)
                 for k, v in mctx.items() if v]
        if notes:
            print(f"\n  Markt-Kontext:")
            for label, note in notes:
                print(f"    {label}: {note}")

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
            primary = " [PRIMÄR]" if evt.get("is_primary") else ""
            print(f"    - {evt['headline']}{primary} (Risiko: {evt.get('cascade_risk', '?')})")
            summary = evt.get("summary")
            if summary:
                print(f"      → {summary}")

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

    # transcribe
    p_trans = sub.add_parser("transcribe", help="Audio-Datei transkribieren (lokal via Whisper)")
    p_trans.add_argument("file", help="Pfad zur Audio-Datei (.ogg, .mp3, .wav, ...)")
    p_trans.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"],
                         help="Whisper-Modell (Default: base)")
    p_trans.add_argument("--language", default="de", help="Sprache (Default: de)")

    # research
    p_research = sub.add_parser("research", help="Deep Research verwalten")
    rs_sub = p_research.add_subparsers(dest="research_action")
    rs_sub.add_parser("list", help="Alle Research-Themen anzeigen")
    p_rs_add = rs_sub.add_parser("add", help="Neues Research-Thema erstellen")
    p_rs_add.add_argument("title", help="Titel des Themas (z.B. 'Trump Zollpolitik')")
    p_rs_run = rs_sub.add_parser("run", help="Research ausführen")
    p_rs_run.add_argument("topic", help="Topic-Slug")
    p_rs_show = rs_sub.add_parser("show", help="Research-Ergebnis anzeigen")
    p_rs_show.add_argument("topic", help="Topic-Slug")
    p_rs_del = rs_sub.add_parser("delete", help="Research-Thema löschen")
    p_rs_del.add_argument("topic", help="Topic-Slug")

    # auto-ampel
    p_auto = sub.add_parser("auto-ampel", help="Vollautomatische Ampel-Analyse durchf\u00fchren")
    p_auto.add_argument("--cpi", type=float, help="CPI-Wert \u00fcberschreiben (z.B. bei neuer Ver\u00f6ffentlichung)")
    p_auto.add_argument("--dry-run", action="store_true", help="Analyse anzeigen, aber nicht speichern")
    p_auto.add_argument("--date", help="Datum \u00fcberschreiben (YYYY-MM-DD, Default: heute)")

    # watchlist
    p_wl = sub.add_parser("watchlist", help="Watchlist verwalten")
    wl_sub = p_wl.add_subparsers(dest="watchlist_action")
    wl_sub.add_parser("show", help="Watchlist anzeigen")
    p_wl_add = wl_sub.add_parser("add", help="Ticker hinzufügen")
    p_wl_add.add_argument("tickers", nargs="+", help="Ticker-Symbole (z.B. NVDA AAPL)")
    p_wl_rm = wl_sub.add_parser("remove", help="Ticker entfernen")
    p_wl_rm.add_argument("ticker", help="Ticker-Symbol")

    # fetch
    p_fetch = sub.add_parser("fetch", help="Kursdaten via yfinance holen und speichern")
    p_fetch.add_argument("--ticker", help="Nur diesen Ticker laden")
    p_fetch.add_argument("--period", default="5d",
                         choices=["5d", "1mo", "3mo", "6mo", "1y", "2y", "max"],
                         help="Zeitraum (Default: 5d)")

    # prices
    p_prices = sub.add_parser("prices", help="Gespeicherte Kursdaten anzeigen")
    p_prices.add_argument("ticker", help="Ticker-Symbol")
    p_prices.add_argument("--days", type=int, default=10, help="Anzahl Tage (Default: 10)")
    p_prices.add_argument("--all", action="store_true", help="Alle gespeicherten Daten")

    # export
    sub.add_parser("export", help="Formatierten Export für Claude-Chat")

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
        "transcribe": cmd_transcribe,
        "auto-ampel": cmd_auto_ampel,
        "watchlist": cmd_watchlist,
        "fetch": cmd_fetch,
        "prices": cmd_prices,
        "research": cmd_research,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
