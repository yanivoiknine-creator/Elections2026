# -*- coding: utf-8 -*-
"""החדשות 12 (N12).

מתחם הבחירות של N12 (special.n12.co.il/elections2026) הוא אפליקציית JS,
אבל גרף הסקרים שבתוכו נטען מ-widget חיצוני שחושף API פתוח:
    https://mako_elections.devdinocdn.com/Home/GetSurveysData

ה-API מחזיר את כל הסקרים ההיסטוריים של *כל* הערוצים, מסומנים לפי מכון/גוף
המפרסם. אנחנו לוקחים מכאן את סקרי החדשות 12 בלבד; שאר הגופים משמשים
לזריעת היסטוריה ראשונית (ראו seed.py).

לכן אין כאן צורך "לחפש את הכתבה החדשה ביותר" — ה-API תמיד מחזיר את המצב
המעודכן, וזה גם המקור האמין ביותר מבין הארבעה.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parties as P
from scrapers.base import get_json

API = "https://mako_elections.devdinocdn.com/Home/GetSurveysData"
SITE_URL = "https://special.n12.co.il/elections2026"

# מזהי הגופים המפרסמים ב-API של N12
CREATOR_N12 = 1
CREATOR_13 = 2
CREATOR_KAN = 3
CREATOR_MAARIV = 7
CREATOR_ISRAEL_HAYOM = 9
CREATOR_ZMAN = 10

_cache = {}


def fetch_api(force=False):
    """מוריד את מאגר הסקרים המלא (ומחזיק אותו בזיכרון לריענון הנוכחי)."""
    if force or "data" not in _cache:
        payload = get_json(API)
        if not payload.get("result"):
            raise RuntimeError(f"ה-API של N12 החזיר שגיאה: {payload.get('error')}")
        _cache["data"] = payload["data"]
    return _cache["data"]


def clear_cache():
    _cache.pop("data", None)


def _party_map(data):
    """id של מפלגה ב-API -> מזהה קנוני אצלנו."""
    out = {}
    for p in data.get("parties", []):
        key = P.match_party(p.get("name", ""))
        if key:
            out[p["id"]] = key
    return out


def surveys_by_creator(data, creator_id):
    """כל הסקרים של גוף מסוים, ממוינים מהישן לחדש."""
    pmap = _party_map(data)
    out = []
    for s in data.get("surveys", []):
        if s.get("surveyCreatorId") != creator_id:
            continue
        results = {}
        for r in s.get("surveyResults", []):
            key = pmap.get(r.get("partyId"))
            val = r.get("result")
            if key and val is not None:
                # מפלגות שהתפצלו/התאחדו עלולות להופיע פעמיים באותו סקר
                results[key] = results.get(key, 0) + float(val)
        if not results:
            continue
        out.append({
            "date": (s.get("surveyDate") or "")[:10],
            "results": results,
            "api_id": s.get("id"),
        })
    out.sort(key=lambda x: x["date"])
    return out


def latest():
    """הסקר האחרון של החדשות 12."""
    data = fetch_api()
    polls = surveys_by_creator(data, CREATOR_N12)
    if not polls:
        raise RuntimeError("לא נמצאו סקרים של החדשות 12 ב-API")
    p = polls[-1]
    return {
        "poll_date": p["date"],
        "results": p["results"],
        "title": f"סקר החדשות 12 – {p['date']}",
        "url": SITE_URL,
        "pollster": None,
        "raw": {"api_id": p["api_id"], "source": "devdino GetSurveysData"},
    }

