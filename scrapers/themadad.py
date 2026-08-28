# -*- coding: utf-8 -*-
"""אתר "המדד" — רשת ביטחון לכל המקורות.

themadad.com/allpolls מרכז את כל סקרי המנדטים של כל כלי התקשורת בטבלה אחת
מובנית: לכל שורה יש ``data-date``, ``data-publisher`` ו-``data-pollster``,
והעמודות הן המפלגות. זה גם המקור שממנו ערוץ 14 עצמו שואב את הנתונים שלו.

**למה זה כאן:** כשהאתר מתפרסם דרך GitHub Actions, חלק מאתרי החדשות מחזירים
403 לכתובות של שרתי ענן — בריצה הראשונה זה קרה לערוץ 14 ולזמן ישראל.
המדד נגיש משם, ולכן הוא משמש כגיבוי אוטומטי לכל מקור שנחסם: המספרים
מגיעים מאותו סקר, רק דרך דלת אחרת.

הגיבוי מסומן ב-origin='madad' כדי שיהיה גלוי בממשק מאיפה הגיע הנתון.
"""
import re
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parties as P
from scrapers.base import get_text, strip_html

URL = "https://themadad.com/allpolls/"

# הטבלה מגיעה עד 2022 וכוללת גם את מחזור הבחירות הקודם. לוקחים רק את
# הסקרים למערכת הנוכחית, אחרת הגרפים היו מציגים מפלגות שכבר לא קיימות.
SINCE = "2025-12-01"

# מזהה המקור אצלנו -> איך הגוף נקרא בטבלה של המדד
PUBLISHER = {
    "n12": "חדשות 12",
    "tv13": "חדשות 13",
    "c14": "ערוץ 14",
    "kan": "כאן חדשות",
    "i24": "i24 news",
    "hayom": "ישראל היום",
    "maariv": "מעריב",
    "zman": "זמן ישראל",
}

ROW_RE = re.compile(
    r'<tr[^>]*data-date="([\d-]{10})"[^>]*data-publisher="([^"]*)"'
    r'(?:[^>]*data-pollster="([^"]*)")?[^>]*>(.*?)</tr>', re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TABLE_RE = re.compile(r"<table.*?</table>", re.S)

# 5 העמודות הראשונות הן מטא-דאטה (מספר, תאריך, משיבים, כלי תקשורת, עורך)
META_COLS = 5

_cache = {}


def fetch(force=False):
    if force or "html" not in _cache:
        _cache["html"] = get_text(URL)
    return _cache["html"]


def clear_cache():
    _cache.pop("html", None)


def _columns(table_html):
    """כותרות המפלגות -> מזהים קנוניים, לפי מיקום העמודה."""
    heads = [strip_html(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.S)]
    out = {}
    for idx, name in enumerate(heads[META_COLS:], start=META_COLS):
        key = P.match_party(name)
        if key:
            out[idx] = key
    return out


def all_polls(force=False):
    """כל השורות בטבלה -> רשימת סקרים, מהישן לחדש."""
    html = fetch(force)
    m = TABLE_RE.search(html)
    if not m:
        raise RuntimeError("לא נמצאה טבלת הסקרים באתר המדד")
    table = m.group(0)
    cols = _columns(table)
    if len(cols) < 8:
        raise RuntimeError(f"זוהו רק {len(cols)} עמודות מפלגה בטבלת המדד")

    out = []
    for date, publisher, pollster, body in ROW_RE.findall(table):
        cells = [strip_html(c) for c in CELL_RE.findall(body)]
        results = {}
        for idx, key in cols.items():
            if idx >= len(cells):
                continue
            raw = cells[idx].strip()
            # תא ריק = המפלגה לא נכללה בסקר (שונה מ-0, שפירושו מתחת לחסימה)
            if not raw:
                continue
            num = re.match(r"(\d{1,3})", raw)
            if num:
                results[key] = results.get(key, 0.0) + float(num.group(1))
        if results and date >= SINCE:
            out.append({"poll_date": date, "publisher": publisher.strip(),
                        "pollster": (pollster or "").strip() or None,
                        "results": results})
    out.sort(key=lambda p: p["poll_date"])
    return out


def polls_for(source_key, force=False):
    """כל הסקרים של מקור מסוים, בפורמט שהאפליקציה מצפה לו."""
    publisher = PUBLISHER.get(source_key)
    if not publisher:
        return []
    return [{
        "poll_date": p["poll_date"],
        "results": p["results"],
        "title": f"סקר {publisher} – {p['poll_date']}",
        "url": URL,
        "pollster": p["pollster"],
        "raw": {"archive": "themadad"},
    } for p in all_polls(force) if p["publisher"] == publisher]


def latest(source_key):
    """הסקר האחרון של מקור מסוים לפי המדד."""
    polls = polls_for(source_key)
    if not polls:
        raise RuntimeError(f"אין סקרים של {PUBLISHER.get(source_key, source_key)} באתר המדד")
    return polls[-1]
