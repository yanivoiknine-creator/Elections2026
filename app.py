# -*- coding: utf-8 -*-
"""מעקב סקרי הבחירות 2026 — שרת האפליקציה.

הרצה:  python app.py     ואז פתיחת http://127.0.0.1:8000
"""
import hashlib
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
import sources
import aggregate as agg
import refresh as refresher
import parties as P

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# בדיקה אוטומטית עם עליית האפליקציה. אפשר לכבות עם --no-refresh או
# ELECTIONS_NO_AUTO_REFRESH=1 (שימושי בפיתוח, כדי לא לפנות לאתרים בכל הרצה).
AUTO_REFRESH = ("--no-refresh" not in sys.argv
                and os.environ.get("ELECTIONS_NO_AUTO_REFRESH") != "1")

# מצב הבדיקה האוטומטית, לתצוגה בממשק
_auto = {"state": "idle", "summary": None, "new": 0, "changed": 0,
         "started_at": None, "finished_at": None}
_refresh_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_refresh(source=None):
    """מריץ ריענון תחת נעילה, כדי שבדיקה אוטומטית וידנית לא ירוצו יחד.

    אם בדיקה כבר רצה (למשל האוטומטית שעלתה עם האפליקציה), לא מפעילים
    שנייה במקביל — אין טעם לפנות לאתרים פעמיים, והממשק ממילא עוקב
    אחרי הבדיקה שכבר רצה.
    """
    if not _refresh_lock.acquire(blocking=False):
        return {"results": [], "new": [], "errors": [], "busy": True,
                "summary": "בדיקה כבר רצה כרגע — רגע אחד…"}
    _auto.update(state="running", summary=None, started_at=_now(),
                 finished_at=None)
    try:
        out = (refresher.refresh_all() if source is None
               else {"results": [refresher.refresh_source(source)]})
        results = out["results"]
        out.setdefault("new", [r for r in results if r["status"] == "new"])
        out.setdefault("errors", [r for r in results if r["status"] == "error"])
        out.setdefault("summary", results[0].get("message", ""))
        _auto.update(state="done", summary=out["summary"],
                     new=len(out["new"]),
                     changed=len([r for r in results
                                  if r["status"] in ("new", "updated")]))
        return out
    except Exception as e:                          # pragma: no cover
        msg = f"{type(e).__name__}: {e}"
        _auto.update(state="error", summary=msg, new=0, changed=0)
        return {"results": [], "new": [], "errors": [], "summary": msg,
                "error": msg}
    finally:
        _auto["finished_at"] = _now()
        _refresh_lock.release()


@asynccontextmanager
async def lifespan(_app):
    """בעליית השרת — בודקים סקרים חדשים ברקע.

    ברקע ולא בחסימה, כדי שהעמוד ייפתח מיד; הממשק מציג באנר בזמן הבדיקה
    ומרענן את עצמו אם נמצא סקר חדש.
    """
    if AUTO_REFRESH:
        _auto.update(state="running", started_at=_now())
        threading.Thread(target=_run_refresh, daemon=True,
                         name="auto-refresh").start()
    else:
        _auto["state"] = "off"
    yield


app = FastAPI(title="מעקב סקרים – בחירות 2026", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# מטמון התבניות של Jinja2 3.1.6 נשבר על Python 3.14 (TypeError במפתח המטמון).
# התבניות כאן קטנות, ולכן פשוט מכבים אותו — בונוס: עריכת תבנית נקלטת מיד.
templates.env.cache = None

db.init()


def _asset_version():
    """חתימה של קבצי ה-CSS/JS, לשבירת מטמון הדפדפן אחרי עדכון.

    בלי זה, דפדפן שכבר ביקר באפליקציה ממשיך להגיש גרסה ישנה של app.js
    ו-style.css, ושינויים בממשק פשוט לא מופיעים.
    """
    h = hashlib.md5()
    for name in ("static/app.js", "static/style.css"):
        path = os.path.join(BASE_DIR, name)
        try:
            h.update(str(os.path.getmtime(path)).encode())
        except OSError:
            pass
    return h.hexdigest()[:8]


def _ctx(**kw):
    """הקשר משותף לכל התבניות.

    auto_state הוא מצב הבדיקה האוטומטית *ברגע הרינדור*. אם היא כבר
    הסתיימה, העמוד ממילא נבנה מנתונים טריים ואין צורך לעקוב אחריה.
    """
    log = db.last_refresh()
    return {"sources": sources.all_meta(), "bloc_names": P.BLOC_NAMES,
            "auto_state": _auto["state"], "asset_v": _asset_version(),
            "base": "/", "static_mode": False,
            "last_check": log["ran_at"] if log else None, **kw}


# ---------------------------------------------------------------- עמודים

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", _ctx(
        avg=agg.average(),
        status=agg.source_status(),
        page="home",
    ))


@app.get("/source/{key}")
def source_page(request: Request, key: str):
    if key not in sources.SOURCES:
        raise HTTPException(404, "מקור לא קיים")
    polls = db.get_polls(source=key)
    return templates.TemplateResponse(request, "source.html", _ctx(
        src=sources.meta(key),
        polls=polls,
        latest=polls[0] if polls else None,
        page=key,
        order=P.order_keys,
        by_seats=P.order_by_seats,
        display=P.display,
        color=P.color,
    ))


# ---------------------------------------------------------------- API

@app.post("/api/refresh")
def api_refresh(source: str | None = None):
    """הכפתור: הולך לאתרים, מחפש סקר חדש, ומעדכן."""
    if source and source not in sources.SOURCES:
        raise HTTPException(404, "מקור לא קיים")
    return _run_refresh(source)


@app.get("/api/refresh-status")
def api_refresh_status():
    """מצב הבדיקה שרצה ברקע — הממשק שואל את זה בטעינת העמוד."""
    log = db.last_refresh()
    return {**_auto, "auto_enabled": AUTO_REFRESH,
            "last_check": log["ran_at"] if log else None}


@app.get("/api/average")
def api_average():
    return agg.average()


@app.get("/api/chart/average")
def api_chart_average(days: int | None = None):
    return agg.average_series(limit_days=days)


@app.get("/api/chart/{key}")
def api_chart_source(key: str, limit: int = 25):
    if key not in sources.SOURCES:
        raise HTTPException(404, "מקור לא קיים")
    return agg.source_series(key, limit=limit)


@app.get("/api/status")
def api_status():
    return {"sources": agg.source_status(), "log": db.recent_log(20)}


@app.exception_handler(Exception)
def on_error(request: Request, exc: Exception):
    return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


PORT = 8000

# --lan פותח את האפליקציה לשאר המכשירים ברשת המקומית (טלפון, טאבלט).
# ברירת המחדל היא מקומי בלבד, כי אין באפליקציה שום מנגנון הרשאות.
LAN = "--lan" in sys.argv


def _port_owner(port):
    """מי מאזין לפורט — או None אם הוא פנוי."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return None if s.connect_ex(("127.0.0.1", port)) else port


def _lan_ip():
    """כתובת ה-IP של המחשב ברשת המקומית.

    פותחים שקע UDP אל כתובת חיצונית (בלי לשלוח שום דבר) רק כדי שמערכת
    ההפעלה תבחר את הכרטיס הנכון — כך לא מתבלבלים בין Wi-Fi, כבל,
    ומתאמים וירטואליים של WSL או Docker.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _print_qr(url):
    """קוד QR בקונסולה, כדי לא להקליד כתובת IP בטלפון. לא חובה."""
    try:
        import qrcode
    except ImportError:
        return False
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    return True


def _open_browser(port):
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    import uvicorn

    # מופע ישן שנשאר תקוע על הפורט הוא מלכודת: uvicorn נכשל בשקט, הדפדפן
    # נפתח מול השרת הישן, והמשתמש רואה גרסה ישנה בלי להבין למה.
    if _port_owner(PORT):
        print("\n" + "=" * 62)
        print(f"  שגיאה: פורט {PORT} כבר תפוס — כנראה מופע קודם של האפליקציה.")
        print("  סגרו את החלון שבו הוא רץ, או הריצו:")
        print(f'      powershell -Command "Get-NetTCPConnection -LocalPort {PORT}'
              ' -State Listen | ForEach-Object'
              ' { Stop-Process -Id $_.OwningProcess -Force }"')
        print("=" * 62 + "\n")
        sys.exit(1)

    host = "0.0.0.0" if LAN else "127.0.0.1"
    if LAN:
        ip = _lan_ip()
        line = "=" * 62
        print("\n" + line)
        if ip:
            url = f"http://{ip}:{PORT}"
            print(f"  מהטלפון, באותה רשת Wi-Fi:   {url}")
            print(line)
            print("  אם הטלפון לא מתחבר — חומת האש של Windows חוסמת.")
            print("  פתחו PowerShell כמנהל והריצו פעם אחת:")
            print(f'    New-NetFirewallRule -DisplayName "Elections2026"'
                  f' -Direction Inbound -Protocol TCP -LocalPort {PORT} -Action Allow')
            print(line)
            if _print_qr(url):
                print("  סרקו את הקוד עם מצלמת הטלפון\n")
        else:
            print("  לא הצלחתי לזהות את כתובת הרשת המקומית של המחשב.")
            print("  הריצו ipconfig וחפשו IPv4 Address של מתאם ה-Wi-Fi,")
            print(f"  ואז גשו מהטלפון אל http://<הכתובת>:{PORT}")
            print(line + "\n")
        # ללא flush מפורש, הפלט נתקע במאגר כשההרצה מנותבת לקובץ או לצינור
        sys.stdout.flush()

    threading.Timer(1.2, _open_browser, args=(PORT,)).start()
    uvicorn.run(app, host=host, port=PORT, log_level="warning")
