# -*- coding: utf-8 -*-
"""מנוע הריענון: הולך לאתרים, מחפש סקר חדש, ומעדכן את מסד הנתונים."""
import db
import sources
from scrapers import themadad
from scrapers.base import sanity_problem


def refresh_source(key):
    """בודק מקור אחד. מחזיר dict עם התוצאה — לעולם לא זורק חריגה.

    סטטוסים:
        new       — נמצא סקר שלא היה במערכת
        updated   — סקר מאותו תאריך כבר היה, והנתונים עודכנו
        unchanged — הסקר האחרון באתר הוא זה שכבר שמור
        error     — הגרידה נכשלה
    """
    src = sources.get(key)
    if not src:
        return {"source": key, "status": "error", "message": "מקור לא מוכר"}

    before = db.latest_poll(key)
    origin, note = "scrape", ""
    try:
        found = src["module"].latest()
    except Exception as e:
        # האתר לא נגיש (למשל 403 לשרתי ענן, כמו ב-GitHub Actions). לוקחים
        # את אותו סקר מאתר "המדד", שמרכז את הסקרים של כל הגופים.
        direct_err = f"{type(e).__name__}: {e}"
        try:
            found = themadad.latest(key)
            origin, note = "madad", " (דרך אתר המדד — האתר עצמו לא נגיש)"
        except Exception as e2:
            msg = f"{direct_err} | גיבוי המדד: {type(e2).__name__}: {e2}"
            db.log_refresh(key, "error", msg)
            return {"source": key, "name": src["name"], "status": "error",
                    "message": msg}

    # אתר המדד מתעדכן לעיתים לפני שהגוף מעלה את הכתבה שלו. אם יש שם סקר
    # חדש יותר מזה שנמצא באתר עצמו, לוקחים אותו — אחרת היינו מפספסים סקרים.
    if origin == "scrape":
        try:
            newer = themadad.latest(key)
            if newer["poll_date"] > found["poll_date"]:
                found, origin = newer, "madad"
                note = " (מאתר המדד — מוקדם יותר מהפרסום באתר עצמו)"
        except Exception:
            pass

    problem = sanity_problem(found["results"])
    if problem:
        db.log_refresh(key, "error", f"נתונים לא סבירים — {problem}", found.get("poll_date"))
        return {"source": key, "name": src["name"], "status": "error",
                "message": f"נתונים לא סבירים — {problem}{note}"}

    # ההשוואה היא על המפלגות עם מנדטים בפועל. מחלצים שונים מציינים אפסים
    # ("לא עוברת את אחוז החסימה") באופן שונה, וזה לא הופך את הסקר לחדש.
    def seats(d):
        return {k: v for k, v in d.items() if v}

    is_same_date = bool(before and before["poll_date"] == found["poll_date"])
    # "אותו סקר" נקבע לפי המספרים, לא רק לפי התאריך: מקורות שונים מתארכים
    # את אותו סקר לפי יום הדגימה או יום הפרסום, בהפרש של יום.
    same_numbers = (is_same_date and seats(before["results"]) == seats(found["results"])
                    ) or db.has_equivalent_poll(key, found["poll_date"], found["results"])

    if same_numbers:
        db.log_refresh(key, "unchanged", note.strip() or None, found["poll_date"])
        return {"source": key, "name": src["name"], "status": "unchanged",
                "poll_date": found["poll_date"],
                "message": f"אין סקר חדש (האחרון: {found['poll_date']}){note}"}

    db.save_poll(key, found["poll_date"], found["results"],
                 title=found.get("title"), url=found.get("url"),
                 pollster=found.get("pollster"), origin=origin,
                 raw=found.get("raw"))

    status = "updated" if is_same_date else "new"
    msg = (f"הנתונים של {found['poll_date']} עודכנו" if is_same_date
           else f"נמצא סקר חדש מ-{found['poll_date']}") + note
    db.log_refresh(key, status, msg, found["poll_date"])
    return {"source": key, "name": src["name"], "status": status,
            "poll_date": found["poll_date"], "title": found.get("title"),
            "url": found.get("url"), "message": msg,
            "total": round(sum(found["results"].values()), 1),
            "n_parties": len([1 for v in found["results"].values() if v])}


def refresh_all():
    """בודק את כל המקורות ומחזיר סיכום."""
    # מנקים מטמון של מודולים שמחזיקים תשובת API בזיכרון, כדי לא לקבל נתון ישן
    themadad.clear_cache()
    for key in sources.ORDER:
        mod = sources.SOURCES[key]["module"]
        if hasattr(mod, "clear_cache"):
            try:
                mod.clear_cache()
            except Exception:
                pass

    results = [refresh_source(key) for key in sources.ORDER]
    db.merge_duplicates()      # ריפוי עצמי: אותו סקר בתאריכים סמוכים
    return {
        "results": results,
        "new": [r for r in results if r["status"] == "new"],
        "errors": [r for r in results if r["status"] == "error"],
        "summary": _summary(results),
    }


def _summary(results):
    new = [r for r in results if r["status"] == "new"]
    upd = [r for r in results if r["status"] == "updated"]
    err = [r for r in results if r["status"] == "error"]
    parts = []
    if new:
        parts.append("נמצאו " + str(len(new)) + " סקרים חדשים: " +
                     ", ".join(f"{r['name']} ({r['poll_date']})" for r in new))
    if upd:
        parts.append(f"{len(upd)} סקרים עודכנו")
    if not new and not upd:
        parts.append("אין סקרים חדשים")
    if err:
        parts.append(f"{len(err)} מקורות נכשלו: " + ", ".join(r["name"] for r in err))
    return " · ".join(parts)
