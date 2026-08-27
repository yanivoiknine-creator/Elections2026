# -*- coding: utf-8 -*-
"""זמן ישראל.

לזמן ישראל יש פיד תגית ייעודי לסקרים (/feed/33350/) — עדיף על עמוד
/democracy/ הכללי, שרוב הקישורים בו אינם סקרים.

בכל כתבת סקר יש גרף Highcharts, ולצידו **טבלת HTML לקוראי מסך**
(`m-chart-table`) עם שמות המפלגות ב-<th> והמנדטים ב-<td>. זו טבלה מדויקת
ומלאה, ולכן היא המקור המועדף; הפרוזה משמשת רק כגיבוי.

הסוקר הקבוע הוא יוסי טאטיקה.
"""
import re

from scrapers.base import get_text, strip_html, sanity_problem
from scrapers.common import collect_links, filter_polls, is_own_poll, find_date, article_text
from scrapers.text_parser import parse_seats
import parties as P

TAG_URL = "https://www.zman.co.il/feed/33350/"
ARTICLE_RE = r"https://www\.zman\.co\.il/\d+/?"

OWN = r"יוסי\s+טאטיקה|טאטיקה|סקר\s+זמן\s+ישראל"
FOREIGN = r"סקר\s+(?:חדשות\s*1[234]|כאן|מעריב|i24|ישראל\s+היום)"

TABLE_RE = re.compile(r'<table[^>]*class="[^"]*m-chart-table[^"]*"[^>]*>(.*?)</table>', re.S)
CAPTION_RE = re.compile(r"<figcaption[^>]*>(.*?)</figcaption>", re.S)
TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def find_poll_articles():
    html = get_text(TAG_URL)
    links = collect_links(html, ARTICLE_RE)
    return filter_polls(links, must_match=r"סקר|מנדט")


def _seats_from_table(html):
    """הטבלה הנסתרת שליד הגרף -> {מפלגה: מנדטים}."""
    for m in TABLE_RE.finditer(html):
        body = m.group(1)
        heads = [strip_html(x) for x in TH_RE.findall(body)]
        cells = [strip_html(x) for x in TD_RE.findall(body)]
        if len(heads) < 8 or len(cells) < len(heads):
            continue
        results = {}
        for name, val in zip(heads, cells[:len(heads)]):
            key = P.match_party(name)
            if not key:
                continue
            # "0 (2.8%)" — לוקחים את המנדטים, לא את אחוז הקולות
            num = re.match(r"\s*(\d{1,3})", val)
            if num:
                results[key] = results.get(key, 0.0) + float(num.group(1))
        if len(results) >= 8:
            return results
    return {}


def parse_article(url):
    html = get_text(url)
    text = article_text(html)

    results = _seats_from_table(html)
    extractor = "table"
    if len(results) < 8:
        results = parse_seats(text) or results
        extractor = "prose"

    # כותרת הגרף נושאת את תאריך הסקר ("... אם הבחירות היו היום: 27/08/2026")
    caption = " ".join(strip_html(c) for c in CAPTION_RE.findall(html))
    date = find_date(caption, "") if re.search(r"\d{1,2}[./]\d{1,2}[./]20\d{2}", caption) \
        else find_date(text, html)

    return {
        "poll_date": date,
        "results": results,
        "title": _title(html),
        "url": url,
        "pollster": "יוסי טאטיקה" if re.search(r"טאטיקה", text) else None,
        "raw": {"extractor": extractor, "caption": caption[:200]},
        "_text": text,
    }


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return "סקר זמן ישראל"
    return strip_html(m.group(1)).split("|")[0].strip()


def latest():
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאו כתבות סקר בפיד של זמן ישראל")
    errors = []
    for art in articles[:6]:
        try:
            out = parse_article(art["url"])
            if not is_own_poll(out.pop("_text"), OWN, FOREIGN):
                errors.append(f"{art['url']}: סקר של גוף אחר")
                continue
            problem = sanity_problem(out["results"])
            if problem is None:
                return out
            errors.append(f"{art['url']}: {problem}")
        except Exception as e:
            errors.append(f"{art['url']}: {e}")
    raise RuntimeError("לא נמצאה כתבת סקר תקינה בזמן ישראל. " + " | ".join(errors[:3]))
