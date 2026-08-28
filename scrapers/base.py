# -*- coding: utf-8 -*-
"""עזרי HTTP משותפים לכל המגרדים.

חלק מהאתרים מוגנים ב-Cloudflare / Akamai שחוסמים לקוחות HTTP רגילים לפי
טביעת האצבע של ה-TLS — לא לפי כותרות. לכן ברירת המחדל היא curl_cffi, שמחקה
ClientHello של כרום אמיתי. httpx נשאר כגיבוי אם curl_cffi לא מותקן.
"""
import re
import html as _html

try:
    from curl_cffi import requests as _curl
    HAVE_CURL_CFFI = True
except ImportError:                                   # pragma: no cover
    _curl = None
    HAVE_CURL_CFFI = False

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 45

# חלק מהאתרים חוסמים לפי טביעת האצבע של ה-TLS ולא רק לפי כתובת ה-IP:
# zman.co.il למשל מחזיר 403 לפרופיל edge101 ו-200 לפרופיל chrome, מאותו
# מחשב בדיוק. לכן על 403 מנסים שוב עם פרופיל דפדפן אחר לפני שמוותרים.
IMPERSONATE_CHAIN = ("chrome", "chrome131", "safari155", "chrome99_android")

# ה-widget של N12 מתארח על hostname עם קו תחתון, ולכן התעודה שלו לא מכסה
# אותו ואימות SSL נכשל. הדומיין ידוע ומגיש נתונים ציבוריים בלבד.
NO_VERIFY_HOSTS = ("mako_elections.devdinocdn.com",)


class FetchError(RuntimeError):
    pass


def _verify_for(url):
    return not any(h in url for h in NO_VERIFY_HOSTS)


def get(url, headers=None, timeout=TIMEOUT):
    """מוריד כתובת ומחזיר את תוכן התגובה כטקסט. זורק FetchError בכישלון."""
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    verify = _verify_for(url)

    last = None
    if HAVE_CURL_CFFI:
        blocked = None
        for profile in IMPERSONATE_CHAIN:
            try:
                r = _curl.get(url, headers=h, timeout=timeout, impersonate=profile,
                              verify=verify, allow_redirects=True)
            except Exception as e:
                last = e
                break                      # תקלת רשת — פרופיל אחר לא יעזור
            if r.status_code in (403, 429):
                blocked = FetchError(f"{r.status_code} עבור {url}")
                continue                   # אולי חסימה לפי טביעת אצבע
            if r.status_code >= 400:
                raise FetchError(f"{r.status_code} עבור {url}")
            return r.text
        if blocked is not None:
            raise blocked

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers=h, verify=verify) as c:
            r = c.get(url)
            if r.status_code >= 400:
                raise FetchError(f"{r.status_code} עבור {url}")
            return r.text
    except FetchError:
        raise
    except Exception as e:
        raise FetchError(f"שגיאת רשת עבור {url}: {last or e}") from e


def get_text(url, **kw):
    return get(url, **kw)


def get_json(url, headers=None, **kw):
    import json
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    body = get(url, headers=h, **kw)
    try:
        return json.loads(body)
    except ValueError as e:
        raise FetchError(f"התשובה מ-{url} אינה JSON תקין: {e}") from e


def strip_html(s: str) -> str:
    """HTML -> טקסט קריא, תוך שמירה על רווח בין בלוקים."""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<(br|/p|/div|/li|/h\d)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


# ---------- בדיקת סבירות ----------
# כתבה שאינה סקר שבועי (למשל תרחיש היפותטי) עלולה להיקרא כאילו היא סקר
# ולהחזיר מספרים אבסורדיים. הבדיקות האלה עוצרות זיהום של מסד הנתונים.
MIN_TOTAL, MAX_TOTAL = 100, 130
MAX_SINGLE_PARTY = 45
MIN_PARTIES = 8


def sanity_problem(results):
    """מחזיר תיאור בעיה אם התוצאות לא סבירות, או None אם הן תקינות."""
    if not results:
        return "לא זוהו מפלגות כלל"
    nonzero = {k: v for k, v in results.items() if v}
    if len(nonzero) < MIN_PARTIES:
        return f"זוהו רק {len(nonzero)} מפלגות עם מנדטים (נדרשות {MIN_PARTIES} לפחות)"
    total = sum(results.values())
    if not (MIN_TOTAL <= total <= MAX_TOTAL):
        return f"סך המנדטים {total:g} חורג מהטווח הסביר ({MIN_TOTAL}-{MAX_TOTAL})"
    worst = max(results.items(), key=lambda kv: kv[1])
    if worst[1] > MAX_SINGLE_PARTY:
        return f"מפלגה אחת קיבלה {worst[1]:g} מנדטים — חורג מהסביר"
    return None
