# -*- coding: utf-8 -*-
"""ישראל היום.

עמוד הבחירות הראשי בנוי מרכיבי Elementor ו-Storycards ואינו מכיל רשימת
כתבות סקרים שימושית, ולכן משתמשים בעמוד התגית "סקר מנדטים".

סקרי העיתון עצמו מסומנים כ-"סקר 'היום'" (מכון מאגר מוחות / דודי חסיד),
ובעמוד התגית יש גם כתבות דעה שמזכירות מנדטים — לכן בדיקת הבעלות נדרשת.
"""
import re
import urllib.parse

from scrapers.base import get_text, strip_html, sanity_problem
from scrapers.common import (collect_links, filter_polls, is_own_poll, find_date,
                             article_text, seats_from_infograms, chart_date)
from scrapers.text_parser import parse_seats

TAG_URL = "https://www.israelhayom.co.il/tag/" + urllib.parse.quote("סקר מנדטים")
BASE = "https://www.israelhayom.co.il"
ARTICLE_RE = r"(?:https://www\.israelhayom\.co\.il)?/[^\"]*?/article/\d+"

OWN = r'סקר\s+["“”\']?היום|ישראל\s+היום|מאגר\s+מוחות|דודי\s+חסיד'
FOREIGN = r"סקר\s+(?:חדשות\s*1[234]|כאן|מעריב|i24|זמן\s+ישראל)"


def find_poll_articles():
    html = get_text(TAG_URL)
    return filter_polls(collect_links(html, ARTICLE_RE, BASE))


def parse_article(url):
    html = get_text(url)
    text = article_text(html)

    # גוף הכתבה מדבר על מגמות, לא על מספרים — טבלת המנדטים היא גרף Infogram.
    results, chart_title = seats_from_infograms(html)
    extractor = "infogram"
    if len(results) < 8:
        results = parse_seats(text) or results
        extractor = "prose"

    return {
        "poll_date": chart_date(chart_title) or find_date(text, html),
        "results": results,
        "title": _title(html),
        "url": url,
        "pollster": _pollster(text),
        "raw": {"extractor": extractor, "chart_title": chart_title},
        "_text": text,
    }




def _pollster(text):
    if re.search(r"מאגר\s+מוחות", text):
        return "מאגר מוחות"
    if re.search(r"דודי\s+חסיד", text):
        return "דודי חסיד"
    return None


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return "סקר ישראל היום"
    return strip_html(m.group(1)).split("|")[0].strip()


def latest():
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאו כתבות סקר בעמוד התגית של ישראל היום")
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
    raise RuntimeError("לא נמצאה כתבת סקר תקינה בישראל היום. " + " | ".join(errors[:3]))
