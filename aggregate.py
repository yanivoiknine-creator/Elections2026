# -*- coding: utf-8 -*-
"""חישוב ממוצע הסקרים ובניית סדרות לגרפים."""
from datetime import date, timedelta

import db
import parties as P
import sources

# בממוצע מאחדים את הרשימות הערביות לרשימה אחת: חלק מהמקורות מדווחים
# "הרשימה המשותפת" וחלק מפרטים "חד"ש-תע"ל" ו"בל"ד" בנפרד. בלי איחוד, אותם
# מנדטים היו נספרים פעמיים בסכום הממוצע. בעמוד של כל מקור מוצג הפירוט המקורי.
MERGE_IN_AVERAGE = {"hadash_taal": "joint", "balad": "joint"}

# סקר ישן מהתקופה הזו לא נחשב "עדכני" בבניית קו המגמה של הממוצע
STALE_DAYS = 45

KNESSET_SEATS = 120


def _merge(results):
    out = {}
    for k, v in results.items():
        out[MERGE_IN_AVERAGE.get(k, k)] = out.get(MERGE_IN_AVERAGE.get(k, k), 0.0) + v
    return out


def latest_by_source():
    """הסקר האחרון מכל מקור פעיל."""
    out = {}
    for key in sources.ORDER:
        poll = db.latest_poll(key)
        if poll:
            out[key] = poll
    return out


def _normalize(rows):
    """מיישר את סכום הממוצעים ל-120 מנדטים.

    כל סקר בנפרד מסתכם ב-120, אבל סכום הממוצעים לפי מפלגה לא בהכרח.
    הסיבה: מפלגה שרק חלק מהסוקרים מדדו אותה מחולקת במספר קטן יותר משאר
    המפלגות. למשל מפלגת וינטר, שהושקה ב-25.8 — סקרים שפורסמו לפניה כלל
    לא שאלו עליה, ולכן היא מחולקת ב-6 בעוד השאר מחולקות ב-8. זה הוסיף
    0.75 מנדטים לסכום.

    לחלק אותה ב-8 היה מעוות אותה כלפי מטה (זה מניח 0 אצל מי שלא שאל),
    ולכן במקום זה מותחים את כל המפלגות באותה פרופורציה. היחס נשמר,
    והמפה שמוצגת מסתכמת ב-120 כמו כנסת אמיתית.
    """
    raw_total = sum(r["raw_avg"] for r in rows)
    factor = KNESSET_SEATS / raw_total if raw_total else 1.0
    for r in rows:
        r["avg"] = round(r["raw_avg"] * factor, 2)
    return raw_total, factor


def average(source_keys=None):
    """ממוצע הסקר האחרון מכל מקור, מנורמל ל-120 מנדטים.

    מחזיר dict עם ממוצע לכל מפלגה, מספר המקורות שתרמו לה, וסיכומי גושים.
    מפלגה נספרת רק במקורות שבסקר האחרון שלהם היא מופיעה בכלל; אפס מפורש
    ("לא עוברת את אחוז החסימה") כן נספר, כי זו מדידה ולא נתון חסר.
    """
    latest = latest_by_source()
    if source_keys:
        latest = {k: v for k, v in latest.items() if k in source_keys}

    totals, counts, contributors = {}, {}, {}
    for src, poll in latest.items():
        for party, seats in _merge(poll["results"]).items():
            totals[party] = totals.get(party, 0.0) + seats
            counts[party] = counts.get(party, 0) + 1
            contributors.setdefault(party, []).append(src)

    rows = []
    for party in totals:
        rows.append({
            "party": party,
            "name": P.display(party),
            "color": P.color(party),
            "bloc": P.bloc(party),
            "raw_avg": totals[party] / counts[party],
            "sources": counts[party],
            "of": len(latest),
            "contributors": contributors[party],
            "per_source": {s: _merge(latest[s]["results"]).get(party)
                           for s in latest},
        })
    raw_total, factor = _normalize(rows)
    rows.sort(key=lambda r: -r["avg"])

    blocs = {}
    for r in rows:
        blocs[r["bloc"]] = round(blocs.get(r["bloc"], 0.0) + r["avg"], 2)

    # מפלגות שלא כל הסוקרים מדדו — הסיבה שהנרמול נדרש בכלל
    partial = [{"name": r["name"], "sources": r["sources"], "of": r["of"],
                "raw": round(r["raw_avg"], 2)}
               for r in rows if r["sources"] < r["of"] and r["raw_avg"] > 0]

    return {
        "rows": rows,
        "blocs": blocs,
        "total": round(sum(r["avg"] for r in rows), 1),
        "raw_total": round(raw_total, 2),
        "normalized": abs(raw_total - KNESSET_SEATS) > 0.05,
        "factor": round(factor, 4),
        "partial": partial,
        "sources_used": sorted(latest.keys(), key=sources.ORDER.index),
        "dates": {s: p["poll_date"] for s, p in latest.items()},
    }


def _parse(d):
    y, m, dd = (int(x) for x in d.split("-"))
    return date(y, m, dd)


def source_series(source_key, limit=25):
    """סדרות לגרף של עמוד מקור: קו לכל מפלגה לאורך הסקרים של אותו מקור."""
    polls = db.get_polls(source=source_key, limit=limit)
    polls.reverse()                       # מהישן לחדש, כמו ציר הזמן בגרף
    return _series_from_polls(polls)


def _series_from_polls(polls):
    if not polls:
        return {"labels": [], "series": []}
    labels = [p["poll_date"] for p in polls]
    all_parties = set()
    for p in polls:
        all_parties |= {k for k, v in p["results"].items() if v}

    series = []
    for party in P.order_keys(all_parties):
        data = [p["results"].get(party) for p in polls]
        if all(v is None for v in data):
            continue
        series.append({
            "party": party,
            "name": P.display(party),
            "color": P.color(party),
            "data": data,
            "last": next((v for v in reversed(data) if v is not None), None),
        })
    series.sort(key=lambda s: -(s["last"] or 0))
    return {"labels": labels, "series": series}


def average_series(limit_days=None, source_keys=None):
    """קו מגמה של ממוצע הסקרים ("סקר הסקרים").

    לכל תאריך שבו פורסם סקר כלשהו, לוקחים מכל מקור את הסקר האחרון שלו נכון
    לאותו תאריך (אם הוא לא ישן מדי) וממצעים. כך מתקבל קו רציף ולא מדורג
    לפי מקור בודד.
    """
    keys = source_keys or sources.ORDER
    by_source = {k: sorted(db.get_polls(source=k), key=lambda p: p["poll_date"])
                 for k in keys}
    by_source = {k: v for k, v in by_source.items() if v}
    if not by_source:
        return {"labels": [], "series": []}

    dates = sorted({p["poll_date"] for polls in by_source.values() for p in polls})
    if limit_days:
        cutoff = max(_parse(d) for d in dates) - timedelta(days=limit_days)
        dates = [d for d in dates if _parse(d) >= cutoff]

    snapshots = []
    for d in dates:
        cur = _parse(d)
        totals, counts = {}, {}
        for polls in by_source.values():
            recent = [p for p in polls if p["poll_date"] <= d]
            if not recent:
                continue
            newest = recent[-1]
            if (cur - _parse(newest["poll_date"])).days > STALE_DAYS:
                continue
            for party, seats in _merge(newest["results"]).items():
                totals[party] = totals.get(party, 0.0) + seats
                counts[party] = counts.get(party, 0) + 1
        if totals:
            # מנרמלים כל נקודה על הציר בדיוק כמו את הטבלה, אחרת הגרף
            # והטבלה היו מציגים מספרים שונים לאותו יום
            avg = {p: totals[p] / counts[p] for p in totals}
            s = sum(avg.values())
            f = KNESSET_SEATS / s if s else 1.0
            snapshots.append({
                "poll_date": d,
                "results": {p: round(v * f, 2) for p, v in avg.items()},
            })

    return _series_from_polls(snapshots)


def source_status():
    """שורת מצב לכל מקור: הסקר האחרון, מתי נבדק, ומה קרה בבדיקה האחרונה."""
    out = []
    for key in sources.ORDER:
        meta = sources.meta(key)
        poll = db.latest_poll(key)
        log = db.last_refresh(key)
        total = sum(poll["results"].values()) if poll else None
        out.append({
            **meta,
            "poll_date": poll["poll_date"] if poll else None,
            "poll_title": poll["title"] if poll else None,
            "poll_url": poll["url"] if poll else None,
            "pollster": poll["pollster"] if poll else None,
            "total": round(total, 1) if total is not None else None,
            "n_parties": len([1 for v in poll["results"].values() if v]) if poll else 0,
            "n_polls": len(db.get_polls(source=key)),
            "last_check": log["ran_at"] if log else None,
            "last_status": log["status"] if log else None,
            "last_message": log["message"] if log else None,
        })
    return out
