# -*- coding: utf-8 -*-
"""i24NEWS.

עמוד התגית "סקר מנדטים" מרכז את הכתבות. סקרי הערוץ עצמו מתפרסמים תחת
/he/news/israel-elections-2026/polls/ ומסומנים בטקסט כ-"סקר i24NEWS"
(מכון דיירקט פולס). i24 מסקר גם סקרים של גופים אחרים, ולכן יש בדיקת בעלות.

המנדטים מחולצים מהפרוזה — i24 לא מפרסמת טבלה מובנית.
"""
import re

from scrapers.base import get_text, sanity_problem
from scrapers.common import collect_links, filter_polls, is_own_poll, find_date, article_text
from scrapers.text_parser import parse_seats

TAG_URL = ("https://www.i24news.tv/he/tags/"
           "%D7%A1%D7%A7%D7%A8-%D7%9E%D7%A0%D7%93%D7%98%D7%99%D7%9D")
BASE = "https://www.i24news.tv"
ARTICLE_RE = r"(?:https://www\.i24news\.tv)?/he/news/[^\"]*?artc-[0-9a-f]+"

OWN = r"i24NEWS|i24news|דיירקט\s*פולס|צוריאל\s+שרון"
FOREIGN = r"סקר\s+(?:חדשות\s*1[234]|כאן|מעריב|זמן\s+ישראל|ישראל\s+היום)"


def find_poll_articles():
    html = get_text(TAG_URL)
    return filter_polls(collect_links(html, ARTICLE_RE, BASE))


def parse_article(url):
    html = get_text(url)
    text = article_text(html)
    return {
        "poll_date": find_date(text, html),
        "results": parse_seats(text),
        "title": _title(html),
        "url": url,
        "pollster": "דיירקט פולס" if re.search(r"דיירקט\s*פולס", text) else None,
        "raw": {"extractor": "prose", "text": text[:4000]},
        "_text": text,
    }


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return "סקר i24NEWS"
    from scrapers.base import strip_html
    return strip_html(m.group(1)).split("|")[0].split(" - i24")[0].strip()


def latest():
    articles = find_poll_articles()
    if not articles:
        raise RuntimeError("לא נמצאו כתבות סקר בעמוד התגית של i24")
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
    raise RuntimeError("לא נמצאה כתבת סקר תקינה ב-i24. " + " | ".join(errors[:3]))
