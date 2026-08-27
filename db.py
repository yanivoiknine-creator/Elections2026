# -*- coding: utf-8 -*-
"""אחסון הסקרים ב-SQLite."""
import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "polls.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS polls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,          -- מזהה המקור: n12 / tv13 / c14 / kan
    poll_date    TEXT NOT NULL,          -- YYYY-MM-DD, תאריך פרסום הסקר
    title        TEXT,
    url          TEXT,
    pollster     TEXT,                   -- מכון הסקרים (אם צוין בכתבה)
    origin       TEXT NOT NULL DEFAULT 'scrape',  -- scrape = נגרד מהאתר, seed = נטען מארכיון
    fetched_at   TEXT NOT NULL,
    raw          TEXT,                   -- הטקסט/JSON הגולמי, לניפוי באגים
    UNIQUE(source, poll_date)
);

CREATE TABLE IF NOT EXISTS results (
    poll_id      INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    party        TEXT NOT NULL,          -- מזהה קנוני מ-parties.py
    seats        REAL NOT NULL,
    PRIMARY KEY (poll_id, party)
);

CREATE TABLE IF NOT EXISTS refresh_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    ran_at      TEXT NOT NULL,
    status      TEXT NOT NULL,           -- new / unchanged / error
    message     TEXT,
    poll_date   TEXT
);

CREATE INDEX IF NOT EXISTS idx_polls_source_date ON polls(source, poll_date DESC);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init():
    with connect() as con:
        con.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


NEAR_DAYS = 2


def _same_poll_nearby(con, source, poll_date, results):
    """מאתר סקר קיים שהוא בעצם אותו סקר, רק בתאריך שונה ביום-יומיים.

    הארכיונים מתארכים סקר לפי יום הפרסום, ואילו גרף הסקר שבכתבה מתארך אותו
    לפי יום הדגימה. בלי האיחוד הזה אותו סקר נשמר פעמיים.
    ההשוואה היא על המפלגות עם מנדטים בפועל — אפסים ("לא עוברת את אחוז
    החסימה") מדווחים אחרת בכל מחלץ.
    """
    target = {k: v for k, v in results.items() if v}
    rows = con.execute(
        "SELECT id, poll_date FROM polls WHERE source=?"
        " AND ABS(JULIANDAY(poll_date) - JULIANDAY(?)) <= ?",
        (source, poll_date, NEAR_DAYS)).fetchall()
    for row in rows:
        got = {r["party"]: r["seats"] for r in con.execute(
            "SELECT party, seats FROM results WHERE poll_id=? AND seats != 0",
            (row["id"],))}
        if got and got == target:
            return row
    return None


def save_poll(source, poll_date, results, title=None, url=None,
              pollster=None, origin="scrape", raw=None):
    """שומר סקר. מחזיר (poll_id, is_new).

    אם כבר קיים סקר מאותו מקור באותו תאריך — מעדכן אותו במקום ליצור כפילות.
    """
    if not results:
        raise ValueError("סקר ללא תוצאות")
    with connect() as con:
        cur = con.execute("SELECT id FROM polls WHERE source=? AND poll_date=?",
                          (source, poll_date))
        row = cur.fetchone()
        if row is None:
            row = _same_poll_nearby(con, source, poll_date, results)
        is_new = row is None
        if is_new:
            cur = con.execute(
                "INSERT INTO polls (source, poll_date, title, url, pollster, origin, fetched_at, raw)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (source, poll_date, title, url, pollster, origin, _now(),
                 json.dumps(raw, ensure_ascii=False) if raw is not None else None))
            poll_id = cur.lastrowid
        else:
            poll_id = row["id"]
            existing_origin = con.execute(
                "SELECT origin FROM polls WHERE id=?", (poll_id,)).fetchone()["origin"]
            # סקר שנגרד ישירות מהאתר גובר על אותו סקר מארכיון: הוא מדויק
            # יותר, ובלעדי הכלל הזה הזריעה והגרידה היו דורסות זו את זו
            # בכל הרצה ומייצרות "עדכון" מדומה בלי סוף.
            keep = existing_origin == "scrape" and origin != "scrape"
            con.execute(
                "UPDATE polls SET title=COALESCE(?,title), url=COALESCE(?,url),"
                " pollster=COALESCE(?,pollster), origin=?, raw=COALESCE(?,raw),"
                " fetched_at=? WHERE id=?",
                (title, url, pollster, existing_origin if keep else origin,
                 json.dumps(raw, ensure_ascii=False) if raw is not None else None,
                 _now(), poll_id))
            if keep:
                return poll_id, False
            con.execute("DELETE FROM results WHERE poll_id=?", (poll_id,))
        con.executemany("INSERT INTO results (poll_id, party, seats) VALUES (?,?,?)",
                        [(poll_id, p, float(s)) for p, s in results.items()])
        return poll_id, is_new


def log_refresh(source, status, message=None, poll_date=None):
    with connect() as con:
        con.execute(
            "INSERT INTO refresh_log (source, ran_at, status, message, poll_date) VALUES (?,?,?,?,?)",
            (source, _now(), status, message, poll_date))


def get_polls(source=None, limit=None):
    """מחזיר סקרים מהחדש לישן, כל אחד עם dict של תוצאות."""
    q = "SELECT * FROM polls"
    args = []
    if source:
        q += " WHERE source=?"
        args.append(source)
    q += " ORDER BY poll_date DESC, id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    with connect() as con:
        polls = [dict(r) for r in con.execute(q, args)]
        if not polls:
            return []
        ids = ",".join(str(p["id"]) for p in polls)
        by_poll = {}
        for r in con.execute(f"SELECT poll_id, party, seats FROM results WHERE poll_id IN ({ids})"):
            by_poll.setdefault(r["poll_id"], {})[r["party"]] = r["seats"]
        for p in polls:
            p["results"] = by_poll.get(p["id"], {})
            raw = p.pop("raw", None)
            # דגל קטן שנשלף מה-raw: כמה מנדטים הושלמו לרשימה המשותפת
            # (ערוץ 14 אינו מפרסם אותה). מאפשר לסמן את זה בממשק.
            p["inferred_joint"] = None
            if raw:
                try:
                    p["inferred_joint"] = json.loads(raw).get("inferred_joint")
                except (ValueError, AttributeError):
                    pass
        return polls


def latest_poll(source):
    p = get_polls(source=source, limit=1)
    return p[0] if p else None


def last_refresh(source=None):
    q = "SELECT * FROM refresh_log"
    args = []
    if source:
        q += " WHERE source=?"
        args.append(source)
    q += " ORDER BY id DESC LIMIT 1"
    with connect() as con:
        r = con.execute(q, args).fetchone()
        return dict(r) if r else None


def recent_log(limit=30):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM refresh_log ORDER BY id DESC LIMIT ?", (limit,))]


JSON_PATH = os.path.join(os.path.dirname(DB_PATH), "polls.json")


def export_json(path=None):
    """שומר את כל הסקרים כקובץ JSON.

    ה-SQLite הוא קובץ בינארי ולכן לא מתאים ל-Git: כל ריצה הייתה מוסיפה
    עותק שלם להיסטוריה. ה-JSON הוא טקסט, הדיפים שלו קריאים והוא נדחס
    היטב, ולכן הוא מה שנשמר במאגר ומשמש להעברת הנתונים בין הרצות.
    """
    path = path or JSON_PATH
    polls = get_polls()
    for p in polls:
        p.pop("id", None)
        # זמן השליפה משתנה בכל ריצה גם כשהנתונים זהים. בלי להשמיט אותו,
        # כל הרצה של המשימה המתוזמנת הייתה יוצרת commit ריק ב-Git.
        p.pop("fetched_at", None)
    payload = {"count": len(polls),
               "polls": sorted(polls, key=lambda p: (p["source"], p["poll_date"]))}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
    return len(polls)


def import_json(path=None):
    """טוען סקרים מקובץ ה-JSON. לא דורס סקרים שכבר קיימים במסד."""
    path = path or JSON_PATH
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    added = 0
    for p in payload.get("polls", []):
        if not p.get("results"):
            continue
        try:
            _pid, is_new = save_poll(
                p["source"], p["poll_date"], p["results"],
                title=p.get("title"), url=p.get("url"),
                pollster=p.get("pollster"), origin=p.get("origin", "seed"),
                raw={"inferred_joint": p["inferred_joint"]} if p.get("inferred_joint") else None)
            added += 1 if is_new else 0
        except (KeyError, ValueError):
            continue
    return added


def merge_duplicates():
    """מאחד סקרים כפולים שנשמרו בתאריכים סמוכים לפני שהאיחוד הופעל.

    שומרים את הגרסה שנגרדה מהאתר עצמו (origin='scrape') על פני זו שנטענה
    מארכיון, כי היא נושאת את התאריך שהמקור עצמו נתן לסקר. מחזיר כמה נמחקו.
    """
    removed = 0
    with connect() as con:
        for (source,) in con.execute("SELECT DISTINCT source FROM polls").fetchall():
            polls = con.execute(
                "SELECT id, poll_date, origin FROM polls WHERE source=? ORDER BY poll_date",
                (source,)).fetchall()
            seats = {}
            for p in polls:
                seats[p["id"]] = {r["party"]: r["seats"] for r in con.execute(
                    "SELECT party, seats FROM results WHERE poll_id=? AND seats != 0",
                    (p["id"],))}
            dropped = set()
            for i, a in enumerate(polls):
                if a["id"] in dropped or not seats[a["id"]]:
                    continue
                for b in polls[i + 1:]:
                    if b["id"] in dropped:
                        continue
                    days = (_date(b["poll_date"]) - _date(a["poll_date"])).days
                    if days > NEAR_DAYS:
                        break
                    if seats[a["id"]] != seats[b["id"]]:
                        continue
                    loser = b if a["origin"] == "scrape" else a
                    dropped.add(loser["id"])
                    if loser["id"] == a["id"]:
                        break
            for pid in dropped:
                con.execute("DELETE FROM results WHERE poll_id=?", (pid,))
                con.execute("DELETE FROM polls WHERE id=?", (pid,))
                removed += 1
    return removed


def _date(s):
    from datetime import date
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


def delete_poll(poll_id):
    with connect() as con:
        con.execute("DELETE FROM results WHERE poll_id=?", (poll_id,))
        con.execute("DELETE FROM polls WHERE id=?", (poll_id,))
