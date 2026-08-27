# -*- coding: utf-8 -*-
"""מנוע הריענון: הולך לאתרים, מחפש סקר חדש, ומעדכן את מסד הנתונים."""
import db
import sources
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
    try:
        found = src["module"].latest()
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        db.log_refresh(key, "error", msg)
        return {"source": key, "name": src["name"], "status": "error", "message": msg}

    problem = sanity_problem(found["results"])
    if problem:
        db.log_refresh(key, "error", f"נתונים לא סבירים — {problem}", found.get("poll_date"))
        return {"source": key, "name": src["name"], "status": "error",
                "message": f"נתונים לא סבירים — {problem}"}

    # ההשוואה היא על המפלגות עם מנדטים בפועל. מחלצים שונים מציינים אפסים
    # ("לא עוברת את אחוז החסימה") באופן שונה, וזה לא הופך את הסקר לחדש.
    def seats(d):
        return {k: v for k, v in d.items() if v}

    is_same_date = bool(before and before["poll_date"] == found["poll_date"])
    same_numbers = is_same_date and seats(before["results"]) == seats(found["results"])

    if same_numbers:
        db.log_refresh(key, "unchanged", None, found["poll_date"])
        return {"source": key, "name": src["name"], "status": "unchanged",
                "poll_date": found["poll_date"],
                "message": f"אין סקר חדש (האחרון: {found['poll_date']})"}

    db.save_poll(key, found["poll_date"], found["results"],
                 title=found.get("title"), url=found.get("url"),
                 pollster=found.get("pollster"), origin="scrape",
                 raw=found.get("raw"))

    status = "updated" if is_same_date else "new"
    msg = (f"הנתונים של {found['poll_date']} עודכנו" if is_same_date
           else f"נמצא סקר חדש מ-{found['poll_date']}")
    db.log_refresh(key, status, msg, found["poll_date"])
    return {"source": key, "name": src["name"], "status": status,
            "poll_date": found["poll_date"], "title": found.get("title"),
            "url": found.get("url"), "message": msg,
            "total": round(sum(found["results"].values()), 1),
            "n_parties": len([1 for v in found["results"].values() if v])}


def refresh_all():
    """בודק את כל המקורות ומחזיר סיכום."""
    # מנקים מטמון של מודולים שמחזיקים תשובת API בזיכרון, כדי לא לקבל נתון ישן
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
