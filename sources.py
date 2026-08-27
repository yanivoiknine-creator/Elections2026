# -*- coding: utf-8 -*-
"""רישום המקורות: כל אתר, איך מגרדים אותו, ואיך מציגים אותו."""
from scrapers import n12, tv13, c14, kan, i24, hayom, maariv, zman

SOURCES = {
    "n12": {
        "name": "החדשות 12",
        "short": "N12",
        "color": "#db0000",
        "site": "https://special.n12.co.il/elections2026",
        "how": "API של מתחם הבחירות (mako_elections) — מחזיר תמיד את הסקר העדכני",
        "module": n12,
    },
    "tv13": {
        "name": "חדשות 13",
        "short": "רשת 13",
        "color": "#0a58ca",
        "site": "https://13tv.co.il/tags/2026-elections/",
        "how": "סריקת עמוד התגית לאיתור כתבת הסקר החדשה, וחילוץ המנדטים מגוף הכתבה",
        "module": tv13,
    },
    "c14": {
        "name": "חדשות 14",
        "short": "ערוץ 14",
        "color": "#c9a227",
        "site": "https://www.c14.co.il/archive/53747",
        "how": ("סריקת ארכיון תגית 'סקר מנדטים' וחילוץ מגוף הכתבה; "
                "API הסקרים של עמוד /elections26 משמש כגיבוי ולהיסטוריה"),
        "note": ("בסקרים שנטענו מה-API: ערוץ 14 אינו מפרסם שם את הרשימות "
                 "הערביות המאוחדות, ולכן המנדטים החסרים להשלמת 120 מיוחסים "
                 "לרשימה המשותפת ומסומנים בטבלה. כתבות הסקר עצמן כן מפרטות "
                 "אותן, ומאשרות שההשלמה נכונה."),
        "module": c14,
    },
    "kan": {
        "name": "כאן 11",
        "short": "כאן",
        "color": "#00a0e0",
        "site": "https://www.kan.org.il/lobby/skarim/",
        "how": "סריקת מרכז הסקרים לאיתור הכתבה החדשה, וקריאת טבלת ה-Infogram שבתוכה",
        "module": kan,
    },
    "i24": {
        "name": "i24NEWS",
        "short": "i24",
        "color": "#e8112d",
        "site": ("https://www.i24news.tv/he/tags/"
                 "%D7%A1%D7%A7%D7%A8-%D7%9E%D7%A0%D7%93%D7%98%D7%99%D7%9D"),
        "how": "סריקת עמוד התגית 'סקר מנדטים', וחילוץ המנדטים מגוף הכתבה",
        "module": i24,
    },
    "hayom": {
        "name": "ישראל היום",
        "short": "היום",
        "color": "#1d4ed8",
        "site": ("https://www.israelhayom.co.il/tag/"
                 "%D7%A1%D7%A7%D7%A8%20%D7%9E%D7%A0%D7%93%D7%98%D7%99%D7%9D"),
        "how": "סריקת עמוד התגית, וקריאת טבלת ה-Infogram המוטמעת בכתבה",
        "module": hayom,
    },
    "maariv": {
        "name": "מעריב",
        "short": "מעריב",
        "color": "#7c3aed",
        "site": "https://www.maariv.co.il/news/elections-2026",
        "how": "סריקת עמוד התגית, וקריאת טבלת ה-Infogram המוטמעת בכתבה",
        "note": ("מעריב מסקרת גם סקרים של ערוצים אחרים באותו עמוד תגית. "
                 "האפליקציה מקבלת רק כתבה שמצוין בה במפורש שזה סקר מעריב "
                 "(מכון לזר), ומדלגת על השאר."),
        "module": maariv,
    },
    "zman": {
        "name": "זמן ישראל",
        "short": "זמן",
        "color": "#5537a9",
        "site": "https://www.zman.co.il/feed/33350/",
        "how": "סריקת פיד תגית הסקרים, וקריאת טבלת הנתונים שליד הגרף בכתבה",
        "module": zman,
    },
}

ORDER = ["n12", "tv13", "c14", "kan", "i24", "hayom", "maariv", "zman"]


def get(key):
    return SOURCES.get(key)


def meta(key):
    """פרטי המקור בלי אובייקט המודול — בטוח להעברה לתבנית."""
    s = SOURCES[key]
    return {k: v for k, v in s.items() if k != "module"} | {"key": key}


def all_meta():
    return [meta(k) for k in ORDER]
