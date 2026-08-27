# -*- coding: utf-8 -*-
"""זריעת היסטוריה — טעינה חד-פעמית של סקרי העבר, כדי שהגרפים לא יתחילו ריקים.

שני האתרים שחושפים API (N12 וערוץ 14) מחזיקים ארכיון של כל הסקרים של *כל*
הערוצים מתחילת 2026. משם אפשר למלא רטרואקטיבית גם את ההיסטוריה של 13 וכאן,
שאצלם באתר עצמו זמין רק הסקר האחרון בכל כתבה.

סקרים שנטענו כך מסומנים origin='seed' כדי להבדיל אותם מגרידה ישירה. הסקר
האחרון תמיד נגרד ישירות מהאתר עצמו בלחיצה על "בדוק סקרים חדשים".

הרצה:  python seed.py            טוען רק סקרים שחסרים
        python seed.py --force    טוען מחדש גם סקרים קיימים (אחרי שינוי בפרסר)
"""
import sys

import db
import sources
from scrapers import n12, c14

# מזהי המקורות אצלנו -> איך הם נקראים בכל אחד משני הארכיונים
MAP = {
    "n12":    {"n12_creator": n12.CREATOR_N12,          "c14_outlet": "חדשות 12"},
    "tv13":   {"n12_creator": n12.CREATOR_13,           "c14_outlet": "חדשות 13"},
    "kan":    {"n12_creator": n12.CREATOR_KAN,          "c14_outlet": "כאן חדשות"},
    "c14":    {"n12_creator": None,                     "c14_outlet": "חדשות 14"},
    "maariv": {"n12_creator": n12.CREATOR_MAARIV,       "c14_outlet": "מעריב"},
    "hayom":  {"n12_creator": n12.CREATOR_ISRAEL_HAYOM, "c14_outlet": "ישראל היום"},
    "zman":   {"n12_creator": n12.CREATOR_ZMAN,         "c14_outlet": "זמן ישראל"},
    "i24":    {"n12_creator": None,                     "c14_outlet": "i24 news"},
}


def _from_n12_archive(creator_id):
    data = n12.fetch_api()
    return [{"poll_date": p["date"], "results": p["results"], "pollster": None,
             "raw": {"archive": "n12", "api_id": p["api_id"]}}
            for p in n12.surveys_by_creator(data, creator_id) if p["date"]]


def _from_c14_archive(outlet):
    return [{"poll_date": p["poll_date"], "results": p["results"],
             "pollster": p.get("pollster"),
             "raw": {"archive": "c14", **(p.get("raw") or {})}}
            for p in c14.polls_by_outlet(outlet) if p["poll_date"]]


def seed_source(key, verbose=True, force=False):
    """טוען היסטוריה למקור אחד. מעדיף את ארכיון N12 — הוא שלם יותר.

    ארכיון ערוץ 14 מדווח לעיתים 0 לרשימות הערביות המאוחדות, ולכן הוא משמש
    רק להשלמת תאריכים שאינם קיימים בארכיון של N12.
    """
    cfg = MAP[key]
    name = sources.SOURCES[key]["name"]
    polls, seen = [], set()

    if cfg["n12_creator"] is not None:
        for p in _from_n12_archive(cfg["n12_creator"]):
            polls.append(p)
            seen.add(p["poll_date"])
    for p in _from_c14_archive(cfg["c14_outlet"]):
        if p["poll_date"] not in seen:
            polls.append(p)
            seen.add(p["poll_date"])

    polls.sort(key=lambda p: p["poll_date"])
    # ב-force דורסים גם סקרים שכבר קיימים, חוץ מאלה שנגרדו ישירות מהאתר
    existing = {q["poll_date"] for q in db.get_polls(source=key)
                if not force or q["origin"] == "scrape"}

    added = 0
    for p in polls:
        if p["poll_date"] in existing:
            continue          # לא דורסים סקר שנגרד ישירות מהאתר
        if not p["results"]:
            continue
        db.save_poll(key, p["poll_date"], p["results"],
                     title=f"סקר {name} – {p['poll_date']}",
                     pollster=p.get("pollster"), origin="seed",
                     raw=p.get("raw"))
        added += 1

    if verbose:
        print(f"  {name:<12} נטענו {added:>3} סקרים "
              f"(סה\"כ במאגר: {len(db.get_polls(source=key))})")
    return added


def main():
    force = "--force" in sys.argv
    db.init()
    print("טוען היסטוריית סקרים מהארכיונים הפתוחים"
          + (" (מרענן גם סקרים קיימים)" if force else "") + "...\n")
    total = 0
    for key in sources.ORDER:
        try:
            total += seed_source(key, force=force)
        except Exception as e:
            nm = sources.SOURCES[key]["name"]
            print(f"  {nm:<12} נכשל: {type(e).__name__}: {e}")
    merged = db.merge_duplicates()   # אותו סקר שנשמר בתאריכים סמוכים
    print(f"\nסה\"כ נוספו {total} סקרים" +
          (f", ואוחדו {merged} כפילויות." if merged else "."))

    for key in sources.ORDER:
        polls = db.get_polls(source=key)
        if polls:
            nm = sources.SOURCES[key]["name"]
            print(f"  {nm:<12} {len(polls):>3} סקרים | "
                  f"{polls[-1]['poll_date']} .. {polls[0]['poll_date']}")


if __name__ == "__main__":
    sys.exit(main())
