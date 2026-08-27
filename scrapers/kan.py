# -*- coding: utf-8 -*-
"""כאן 11 — מרכז הסקרים.

עמוד הלובי (kan.org.il/lobby/skarim) מרכז את כתבות הסקר. כל כתבה מטמיעה
גרף Infogram עם טבלת המנדטים המלאה, ו-Infogram חושף את הנתונים כ-JSON
בתוך window.infographicData. זה המקור המדויק ביותר עבור כאן, כי גוף הכתבה
מזכיר בפרוזה רק חלק מהמפלגות.

שרשרת הניסיונות:
    1. Infogram של הכתבה החדשה ביותר   (טבלה מלאה)
    2. פרוזה של הכתבה                   (חלקי, אבל עדיף מכלום)
"""
import re
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parties as P
from scrapers.base import get_text, strip_html, sanity_problem
from scrapers.common import seats_from_infograms, chart_date, find_date
from scrapers.text_parser import parse_seats

LOBBY_URL = "https://www.kan.org.il/lobby/skarim/"
# בלובי יש שני סוגי קישורים לאותה כתבה: אחד עוטף תמונה ונושא aria-label עם
# הכותרת, והשני עוטף את הכותרת כטקסט. תופסים את שניהם.
ARTICLE_RE = re.compile(
    r'<a\s([^>]*href="(https://www\.kan\.org\.il/content/kan-news/[^"]+?/\d+/)"[^>]*)>(.*?)</a>',
    re.S)
ARIA_RE = re.compile(r'aria-label="([^"]*)"')


def find_poll_articles():
    """כתבות הסקר בעמוד הלובי, לפי הסדר שבו האתר מציג אותן (החדש ראשון)."""
    html = get_text(LOBBY_URL)
    titles, order = {}, []
    for m in ARTICLE_RE.finditer(html):
        attrs, url, inner = m.group(1), m.group(2), m.group(3)
        aria = ARIA_RE.search(attrs)
        title = (aria.group(1) if aria else strip_html(inner)).strip()
        title = re.sub(r"\s+", " ", title)
        if url not in titles:
            order.append(url)
        # מעדיפים את הכותרת הארוכה מבין שני הקישורים לאותה כתבה
        if len(title) > len(titles.get(url, "")):
            titles[url] = title
    return [{"url": u, "title": titles[u]} for u in order if "סקר" in titles[u]]






def parse_article(url):
    html = get_text(url)
    text = strip_html(html)

    results, chart_title = seats_from_infograms(html)
    source = "infogram"
    if len(results) < 8:
        # גיבוי: חילוץ מהפרוזה. פחות שלם, אבל טוב מכלום.
        results = parse_seats(text) or results
        source = "prose"

    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = strip_html(m.group(1)) if m else ""
    pollster = None
    pm = re.search(r"על\s+ידי\s+מכון\s+([֐-׿\"' ]{2,25})", text)
    if pm:
        pollster = pm.group(1).strip()

    return {
        "poll_date": chart_date(chart_title) or find_date(text, html),
        "results": results,
        "title": title.split("|")[0].strip() or "סקר כאן חדשות",
        "url": url,
        "pollster": pollster,
        "raw": {"extractor": source, "chart_title": chart_title},
    }


def latest():
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאו כתבות סקר בעמוד הלובי של כאן")
    errors = []
    for art in articles[:5]:
        try:
            out = parse_article(art["url"])
            problem = sanity_problem(out["results"])
            if problem is None:
                return out
            errors.append(f"{art['url']}: {problem}")
        except Exception as e:
            errors.append(f"{art['url']}: {e}")
    raise RuntimeError("לא נמצאה כתבת סקר תקינה בכאן. " + " | ".join(errors[:3]))
