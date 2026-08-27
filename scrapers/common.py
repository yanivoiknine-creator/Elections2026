# -*- coding: utf-8 -*-
"""תשתית משותפת למגרדים שעובדים לפי "עמוד תגית -> כתבה".

רוב האתרים עובדים באותו דפוס: יש עמוד שמרכז את כתבות הסקרים, ומשם נכנסים
לכתבה החדשה ביותר ומחלצים ממנה את המנדטים.

שתי נקודות שחוזרות בכל האתרים ולכן יושבות כאן:

* **בעלות על הסקר** — אתרים כמו מעריב ו-i24 מסקרים גם סקרים של ערוצים
  אחרים ("סקר חדשות 13: הליכוד מגיע לשפל"). בלי בדיקה, סקר של ערוץ אחד
  היה נרשם על שם ערוץ אחר. לכן כל מקור מגדיר ביטוי שחייב להופיע בכתבה.
* **תאריך הסקר** — לרוב מופיע בכתבה בפורמט עברי/מקומי, ולא כמטא-דאטה נקייה.
"""
import json
import re
import html as _html
from datetime import datetime

import parties as P
from scrapers.base import strip_html, get_text

HEB_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6,
    "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}


def collect_links(html, url_re, base=""):
    """כל הקישורים שתואמים לתבנית, בסדר הופעתם, עם הכותרת הטובה ביותר.

    כותרת נלקחת מ-aria-label / title אם יש (הרבה אתרים עוטפים תמונה בקישור
    בלי טקסט), אחרת מהטקסט שבתוך התג.
    """
    pat = re.compile(
        r'<a\s([^>]*?)href="(' + url_re + r')"([^>]*)>(.*?)</a>', re.S)
    titles, order = {}, []
    for m in pat.finditer(html):
        url, attrs, inner = m.group(2), m.group(1) + m.group(3), m.group(4)
        aria = re.search(r'(?:aria-label|title)="([^"]*)"', attrs)
        title = _html.unescape(aria.group(1)) if aria else strip_html(inner)
        title = re.sub(r"\s+", " ", title).strip()
        if url not in titles:
            order.append(url)
            titles[url] = ""
        if len(title) > len(titles[url]):
            titles[url] = title
    return [{"url": (base + u if u.startswith("/") else u), "title": titles[u]}
            for u in order]


def filter_polls(links, must_match=r"סקר|מנדט"):
    pat = re.compile(must_match)
    return [x for x in links if pat.search(x["title"])]


def is_own_poll(text, own_re, foreign_re=None):
    """האם הכתבה מדווחת על הסקר של האתר עצמו ולא של גוף אחר."""
    if not re.search(own_re, text):
        return False
    if foreign_re and re.search(foreign_re, text) and not re.search(own_re, text[:600]):
        return False
    return True


def find_date(text, html=""):
    """תאריך הסקר מתוך הכתבה. מנסה כמה פורמטים נפוצים.

    מטא-דאטה מובנית קודמת לתאריך שבטקסט: כתבות מזכירות לעיתים את תאריך
    *הסקר הקודם* ("ירידה לעומת סקר i24NEWS ב-18 באוגוסט"), ותאריך כזה
    היה נבחר בטעות כתאריך הסקר הנוכחי.
    """
    for pat in (r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})',
                r'property="article:published_time"\s+content="(\d{4}-\d{2}-\d{2})',
                r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    # 27/08/2026  או  27.8.2026
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # "26 באוגוסט 2026"  /  "26 באוגוסט"
    m = re.search(r"\b(\d{1,2})\s+ב?(" + "|".join(HEB_MONTHS) + r")\b(?:\s+(20\d{2}))?", text)
    if m:
        d, mo, y = int(m.group(1)), HEB_MONTHS[m.group(2)], int(m.group(3) or datetime.now().year)
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def article_text(html, max_chars=12000):
    """גוף הכתבה כטקסט. חותך את הזנב כדי לא לגרור כתבות מומלצות."""
    text = strip_html(html)
    # מתחילים מהמקום שבו מתחיל הדיווח בפועל, אם אפשר לזהות אותו
    m = re.search(r"(אם\s+הבחירות\s+היו\s+נערכות|לפי\s+הסקר|מהסקר\s+עולה|"
                  r"על\s+פי\s+הסקר|כך\s+עולה\s+מסקר|בסקר\s+ש)", text)
    if m and m.start() > 400:
        text = text[m.start() - 400:]
    return text[:max_chars]


# ---------------------------------------------------------------- Infogram
# כאן 11 וישראל היום מטמיעים את טבלת המנדטים כגרף Infogram. Infogram חושף
# את נתוני הגרף כ-JSON בתוך window.infographicData, וזה מקור מדויק ומלא
# הרבה יותר מהפרוזה שמזכירה רק חלק מהמפלגות.

# ההטמעה מופיעה בשלוש צורות: HTML רגיל (כאן), בתוך JSON עם גרשיים
# מוברחים (מעריב), ובתוך JSON עם גרשיים מקודדים כ-" (ישראל היום).
# ה-data-id עצמו הוא לפעמים מזהה, לפעמים "_/מזהה", ולפעמים כתובת מלאה.
INFOGRAM_ID_RES = (
    re.compile(r'infogram-embed.{0,300}?data-id=\\{0,2}"([^"\\>]{8,120})'),
    re.compile(r'infogram-embed.{0,300}?data-id=\\{1,2}u0022([^"\\>]{8,120})'),
    re.compile(r'infogram\.com/(_?/?[0-9a-zA-Z-]{20,})'),
)
INFOGRAM_DATA_RE = re.compile(r'window\.infographicData\s*=\s*(\{.*?\});?\s*</script>', re.S)

# שורות שהן סיכום גוש ולא מפלגה. בלי הסינון, "גוש נתניהו" היה מזוהה
# כליכוד (בגלל הכינוי "נתניהו") ומקבל את מנדטי הגוש כולו.
BLOC_LABEL = re.compile(r"גוש|אופוזיציה|קואליציה|מפלגות\s+ערביות|סה\"?כ|המחנה")


def infogram_ids(html):
    """כל מזהי ה-Infogram שמוטמעים בעמוד, בסדר הופעתם."""
    out = []
    for rx in INFOGRAM_ID_RES:
        for raw in rx.findall(html):
            val = raw.strip()
            if val.startswith("http"):
                # "https://infogram.com/1pwe..." -> המזהה בסוף הנתיב
                val = val.rstrip("/").rsplit("/", 1)[-1]
            if re.fullmatch(r"_?/?[0-9a-zA-Z_-]{8,60}", val) and val not in out:
                out.append(val)
    return out


def chart_date(chart_title):
    """תאריך מתוך כותרת גרף ("סקר מנדטים 20.8.26", "מנדטים סקר 23.08")."""
    if not chart_title:
        return None
    m = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", chart_title)
    if not m:
        return None
    day, mon = int(m.group(1)), int(m.group(2))
    year = int(m.group(3) or datetime.now().year)
    if year < 100:
        year += 2000
    try:
        return datetime(year, mon, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def infogram_seats(info_id):
    """מזהה Infogram -> ({מפלגה: מנדטים}, כותרת הגרף)."""
    html = get_text(f"https://infogram.com/{info_id}")
    m = INFOGRAM_DATA_RE.search(html)
    if not m:
        return {}, None
    data = json.loads(m.group(1))
    entities = (data.get("elements", {}).get("content", {})
                .get("content", {}).get("entities") or {})

    results = {}
    for ent in entities.values():
        rows = (ent.get("props") or {}).get("chartData", {}).get("data")
        if not rows:
            continue
        for sheet in rows:
            for row in sheet:
                if not isinstance(row, list) or len(row) < 2:
                    continue
                label = (row[0] or {}).get("value") if isinstance(row[0], dict) else None
                value = (row[1] or {}).get("value") if isinstance(row[1], dict) else None
                if not label or value in (None, ""):
                    continue
                if BLOC_LABEL.search(str(label)):
                    continue
                key = P.match_party(str(label))
                if not key:
                    continue
                # הערך עשוי להיות "23 (22)" — נוכחי (קודם). לוקחים את הנוכחי.
                num = re.match(r"\s*(\d{1,3})", str(value))
                if num:
                    results.setdefault(key, float(num.group(1)))
    return results, data.get("title")


def seats_from_infograms(html, min_parties=8):
    """מנסה את כל גרפי ה-Infogram בעמוד ומחזיר את המלא שבהם."""
    best, best_title = {}, None
    for info_id in infogram_ids(html):
        try:
            res, title = infogram_seats(info_id)
        except Exception:
            continue
        if len(res) > len(best):
            best, best_title = res, title
        if len(best) >= min_parties:
            break
    return best, best_title
