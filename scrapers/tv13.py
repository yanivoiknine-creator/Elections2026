# -*- coding: utf-8 -*-
"""חדשות 13 (רשת 13).

עמוד התגית של הבחירות מחזיק מערך פוסטים ב-__NEXT_DATA__. כתבת סקר מסומנת
ב-redStrip.text == "סקר חדשות 13", ולכן אפשר לאתר את הסקר החדש ביותר בלי
להסתמך על כתובת קבועה — בדיוק התרחיש שהאפליקציה צריכה לתמוך בו.

אחר כך פותחים את הכתבה עצמה, שוב קוראים __NEXT_DATA__, ומחלצים את המנדטים
מגוף הכתבה (articleBody) באמצעות הפרסר העברי.

הערה: 13tv מוגן ב-Akamai וחוסם בקשות בלי כותרות דפדפן מלאות — ראו base.py.
"""
import re
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.base import get_text, sanity_problem
from scrapers.text_parser import parse_seats

TAG_URL = "https://13tv.co.il/tags/2026-elections/"
BASE = "https://13tv.co.il"

# התווית האדומה שמסמנת כתבת סקר, ומילות מפתח לגיבוי
POLL_STRIP = "סקר חדשות 13"
POLL_HINTS = re.compile(r"סקר\s+חדשות\s*13|סקר\s+מנדטים")

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _next_data(html):
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise RuntimeError("לא נמצא __NEXT_DATA__ בעמוד של 13")
    return json.loads(m.group(1))


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, o


def find_poll_articles():
    """מאתר את כתבות הסקר בעמוד התגית, מהחדשה לישנה."""
    data = _next_data(get_text(TAG_URL))
    posts = []
    for grid in (data.get("props", {}).get("pageProps", {})
                 .get("page", {}).get("Content", {}).get("PageGrid") or []):
        posts.extend(grid.get("posts") or [])

    found = []
    for p in posts:
        strip = ((p.get("redStrip") or {}).get("text") or "").strip()
        title = f"{p.get('title') or ''} {p.get('secondaryTitle') or ''}"
        is_poll = (strip == POLL_STRIP) or bool(POLL_HINTS.search(title))
        if not is_poll or not p.get("link"):
            continue
        found.append({
            "url": BASE + p["link"] if p["link"].startswith("/") else p["link"],
            "title": (p.get("title") or "").strip(),
            "date": (p.get("publishDate") or p.get("updateDate") or "")[:10],
        })
    found.sort(key=lambda x: x["date"], reverse=True)
    return found


def parse_article(url):
    """כתבה בודדת -> מנדטים לכל מפלגה."""
    data = _next_data(get_text(url))
    item = (data.get("props", {}).get("pageProps", {})
            .get("page", {}).get("Content", {}).get("Item") or {})

    body = item.get("postContent") or ""
    if not body:
        # גיבוי: הטקסט המובנה של schema.org
        for path, val in _walk(data):
            if path.endswith("/articleBody") and isinstance(val, str):
                body = val
                break
    lead = item.get("secondaryTitle") or ""
    text = f"{lead}\n{body}"
    text = re.sub(r"<[^>]+>", " ", text)

    results = parse_seats(text)
    date = (item.get("publishDate") or item.get("updateDate") or "")[:10]
    return {
        "poll_date": date or datetime.now().strftime("%Y-%m-%d"),
        "results": results,
        "title": (item.get("title") or "").strip(),
        "url": url,
        "pollster": _pollster(text),
        "raw": {"text": text[:4000]},
    }


def _pollster(text):
    m = re.search(r"(?:מכון|בהנחיית|בוצע\s+על\s+ידי|נערך\s+על\s+ידי)\s+([֐-׿\"' ]{2,30})", text)
    return m.group(1).strip() if m else None


def latest():
    """הסקר החדש ביותר של חדשות 13 — מאותר דינמית, לא מכתובת קבועה."""
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאה כתבת סקר בעמוד התגית של 13")
    errors = []
    # מנסים מהחדשה לישנה — כתבה מסומנת כסקר עלולה בכל זאת להיות תרחיש
    # היפותטי ("כמה שווה מפלגת X"), ואז בדיקת הסבירות פוסלת אותה.
    for art in articles[:5]:
        try:
            out = parse_article(art["url"])
            problem = sanity_problem(out["results"])
            if problem is None:
                return out
            errors.append(f"{art['url']}: {problem}")
        except Exception as e:
            errors.append(f"{art['url']}: {e}")
    raise RuntimeError("לא נמצאה כתבת סקר תקינה ב-13. " + " | ".join(errors[:3]))
