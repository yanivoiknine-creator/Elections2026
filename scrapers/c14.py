# -*- coding: utf-8 -*-
"""ערוץ 14 (חדשות 14).

לערוץ 14 יש שני מקורות, ואנחנו משתמשים בשניהם:

1. **עמוד הארכיון של תגית "סקר מנדטים"** (/archive/53747) — כתבות הסקר של
   הערוץ. זה המקור הראשי: הכתבות עולות לפני שה-API מתעדכן, והפרוזה בהן
   מפרטת את כל המפלגות. הסקר של 27.8 למשל הופיע כאן בזמן שה-API עוד החזיק
   את זה של 24.8.
2. **API הסקרים** של עמוד /elections26 — מחזיק ארכיון של כל הגופים עם
   תאריך, מכון סוקר ומספר נשאלים (הנתונים נאספים מאתר "המדד"). משמש
   לגיבוי ולזריעת ההיסטוריה.

שימו לב ש-/elections26 עצמו מציג כברירת מחדל *ממוצע ארוך-טווח* של סקרי
הערוץ ולא את הסקר האחרון, ולכן אין להשתמש בו כמקור לסקר בודד.

הערה על ה-API: הרשימות הערביות המאוחדות מדווחות בו כ-0 (ערוץ 14 אינו
מפרסם אותן), ולכן ההפרש ל-120 מיוחס לרשימה המשותפת — ראו _convert.
כתבת הסקר של 24.8 מאשרת שההשלמה נכונה: היא מציינת במפורש חד"ש-תע"ל-בל"ד 5,
בדיוק הפער שההשלמה חישבה.
"""
import re
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parties as P
from scrapers.base import get_json, get_text, strip_html, sanity_problem
from scrapers.common import (collect_links, filter_polls, is_own_poll,
                             find_date, article_text)
from scrapers.text_parser import parse_seats

API = "https://www.c14.co.il/api/elections26/polls?year={year}"
SITE_URL = "https://www.c14.co.il/elections26"
ARCHIVE_URL = "https://www.c14.co.il/archive/53747"
BASE = "https://www.c14.co.il"
ARTICLE_RE = r"(?:https://www\.c14\.co\.il)?/article/\d+"
OUTLET = "חדשות 14"

OWN = r"חדשות\s*14|ערוץ\s*14|שלמה\s+פילבר|סקר\s+מנדטים"
FOREIGN = r"סקר\s+(?:חדשות\s*1[23]|כאן|מעריב|i24|זמן\s+ישראל|ישראל\s+היום)"

# מפתחות המפלגות ב-API של ערוץ 14 -> מזהים קנוניים אצלנו
KEY_MAP = {
    "likud": "likud",
    "shas": "shas",
    "yahadutHatora": "yahadut",
    "otzmaYehudit": "otzma",
    "religiousZionism": "tzionut",
    "yashar": "yashar",
    "bennett": "beyahad",
    "democrats": "democrats",
    "israelBeytenu": "yisrael_beit",
    "kahol": "kachol_lavan",
    "yeshAtid": "yesh_atid",
    "tropperHandel": "bayit_tzioni",
    "reservists": "bayit_tzioni",
    "unitedArab": "joint",
    "hadashTaal": "hadash_taal",
    "balad": "balad",
    "raam": "raam",
}

_cache = {}


def fetch_api(year=None, force=False):
    year = year or datetime.now().year
    if force or year not in _cache:
        payload = get_json(API.format(year=year),
                           headers={"Referer": SITE_URL})
        _cache[year] = payload
    return _cache[year]


def clear_cache():
    _cache.clear()


# ערוץ 14 אינו מפרסם את הרשימות הערביות המאוחדות, ולכן הן מגיעות מה-API
# כאפס וסכום הסקר יוצא נמוך מ-120. בכל סקר כזה בדקנו שכל הרשימות הערביות
# מאופסות יחד, והפער בדיוק בגודל הבלוק הערבי:
#   * רע"ם מדווח והשאר מאופסות  -> הפער הוא הרשימה המשותפת (בד"כ 4-7)
#   * גם רע"ם מאופס             -> הפער הוא כל הבלוק הערבי (בד"כ 11-13)
# לכן משלימים את ההפרש ל-120 כרשימה המשותפת. זו השלמה מתועדת ולא מדידה,
# והיא מסומנת ב-raw כדי שתישאר גלויה.
_JOINT_KEYS = ("unitedArab", "hadashTaal", "balad")
KNESSET_SEATS = 120
MAX_INFERRED = 20      # פער גדול מזה אינו "רשימה חסרה" אלא נתון פגום


def _convert(poll):
    raw = poll.get("parties") or {}

    results = {}
    for raw_key, seats in raw.items():
        key = KEY_MAP.get(raw_key) or P.match_party(raw_key)
        if not key or seats is None:
            continue
        # reservists ו-tropperHandel ממופים לאותה מפלגה — מחברים ולא דורסים
        results[key] = results.get(key, 0.0) + float(seats)

    inferred = 0.0
    no_joint_reported = all(not raw.get(k) for k in _JOINT_KEYS)
    gap = KNESSET_SEATS - sum(results.values())
    if no_joint_reported and 0 < gap <= MAX_INFERRED:
        results["joint"] = results.get("joint", 0.0) + gap
        inferred = gap
    return results, inferred


def polls_by_outlet(outlet=OUTLET, year=None):
    """כל הסקרים של גוף מסוים, מהישן לחדש."""
    payload = fetch_api(year)
    out = []
    for p in payload.get("polls", []):
        if p.get("mediaOutlet") != outlet:
            continue
        results, inferred = _convert(p)
        if not results:
            continue
        out.append({
            "poll_date": p.get("date"),
            "results": results,
            "title": f"סקר {outlet} – {p.get('date')}",
            "url": SITE_URL,
            "pollster": p.get("pollster"),
            "raw": {"api_id": p.get("id"), "respondents": p.get("respondents"),
                    "source": payload.get("source"),
                    "inferred_joint": inferred or None},
        })
    out.sort(key=lambda x: x["poll_date"] or "")
    return out


def find_poll_articles():
    """כתבות הסקר בעמוד הארכיון של תגית 'סקר מנדטים'."""
    html = get_text(ARCHIVE_URL)
    return filter_polls(collect_links(html, ARTICLE_RE, BASE))


def parse_article(url):
    html = get_text(url)
    text = article_text(html)
    return {
        "poll_date": find_date(text, html),
        "results": parse_seats(text),
        "title": _title(html),
        "url": url,
        "pollster": "שלמה פילבר" if re.search(r"פילבר", text) else None,
        "raw": {"extractor": "prose"},
        "_text": text,
    }


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return "סקר חדשות 14"
    return strip_html(m.group(1)).split(" - ערוץ 14")[0].split("|")[0].strip()


def latest():
    """הסקר האחרון: קודם מכתבות הארכיון, ואם לא הצליח — מה-API."""
    errors = []
    try:
        for art in find_poll_articles()[:6]:
            try:
                out = parse_article(art["url"])
                if not is_own_poll(out.pop("_text"), OWN, FOREIGN):
                    continue
                problem = sanity_problem(out["results"])
                if problem is None:
                    return out
                errors.append(f"{art['url']}: {problem}")
            except Exception as e:
                errors.append(f"{art['url']}: {e}")
    except Exception as e:
        errors.append(f"עמוד הארכיון: {e}")

    polls = polls_by_outlet()
    if polls:
        return polls[-1]
    # גיבוי אחרון: "סקר הסקרים" המרונדר בעמוד הבחירות (ממוצע, לא סקר בודד)
    return _from_page()


def _from_page():
    """גיבוי: חילוץ מהעמוד המרונדר. מסומן במפורש כממוצע ולא כסקר בודד."""
    html = get_text(SITE_URL)
    results = {}
    # <span class="sr-only">הליכוד<!-- -->, <!-- -->35<!-- --> מנדטים</span>
    for m in re.finditer(
            r'<span class="sr-only">(.*?)<!-- -->,\s*<!-- -->(\d{1,3})<!-- -->\s*מנדטים</span>',
            html):
        key = P.match_party(strip_html(m.group(1)))
        if key:
            results[key] = float(m.group(2))
    if not results:
        for m in re.finditer(r'aria-label="([^",]+),\s*(\d{1,3})\s+מנדטים"', html):
            key = P.match_party(m.group(1))
            if key:
                results.setdefault(key, float(m.group(2)))
    if not results:
        raise RuntimeError("לא הצלחתי לחלץ מנדטים מהעמוד של ערוץ 14")
    return {
        "poll_date": datetime.now().strftime("%Y-%m-%d"),
        "results": results,
        "title": "ממוצע סקרי ערוץ 14 (מהעמוד, לא סקר בודד)",
        "url": SITE_URL,
        "pollster": None,
        "raw": {"extractor": "page-fallback"},
    }
