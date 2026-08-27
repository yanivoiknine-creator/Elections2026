# -*- coding: utf-8 -*-
"""מעריב.

עמוד התגית "סקר מנדטים" מרכז את הכתבות, אבל מעריב מדווחת שם גם על סקרים של
ערוצים אחרים ("סקר מנדטים: הליכוד מגיע לשפל חדש" — שהוא בעצם סקר חדשות 13).
לכן בדיקת הבעלות כאן קריטית: מקבלים רק כתבה שמזכירה את מכון לזר / סקר מעריב.

הפרוזה מזכירה רק שתיים-שלוש מפלגות; טבלת המנדטים המלאה היא גרף Infogram
מוטמע, ולכן הוא המקור המועדף.
"""
import re
import urllib.parse

from scrapers.base import get_text, sanity_problem
from scrapers.common import (collect_links, filter_polls, is_own_poll, find_date,
                             article_text, seats_from_infograms, chart_date)
from scrapers.text_parser import parse_seats

TAG_URL = "https://www.maariv.co.il/tags/" + urllib.parse.quote("סקר מנדטים")
BASE = "https://www.maariv.co.il"
ARTICLE_RE = r"(?:https://www\.maariv\.co\.il)?/news/[^\"]*?article-?\d+"

OWN = r"סקר\s+מעריב|מנחם\s+לזר|מכון\s+לזר|לזר\s+מחקרים|פאנל4|מעריב\s+וג'רוזלם"
FOREIGN = r"סקר\s+(?:חדשות\s*1[234]|כאן|i24|זמן\s+ישראל|ישראל\s+היום)"


def find_poll_articles():
    html = get_text(TAG_URL)
    return filter_polls(collect_links(html, ARTICLE_RE, BASE))


def parse_article(url):
    html = get_text(url)
    text = article_text(html)

    results, ctitle = seats_from_infograms(html)
    extractor = "infogram"
    if len(results) < 8:
        results = parse_seats(text) or results
        extractor = "prose"

    return {
        "poll_date": chart_date(ctitle) or find_date(text, html),
        "results": results,
        "title": _title(html),
        "url": url,
        "pollster": "מנחם לזר (לזר מחקרים)" if re.search(r"לזר", text) else None,
        "raw": {"extractor": extractor, "chart_title": ctitle},
        "_text": text,
    }


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return "סקר מעריב"
    from scrapers.base import strip_html
    return strip_html(m.group(1)).split("|")[0].strip()


def latest():
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאו כתבות סקר בעמוד התגית של מעריב")
    errors = []
    for art in articles[:8]:
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
    raise RuntimeError("לא נמצאה כתבת סקר תקינה במעריב. " + " | ".join(errors[:3]))
