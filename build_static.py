# -*- coding: utf-8 -*-
"""בונה אתר סטטי מלא מתוך מסד הנתונים, לפרסום ב-GitHub Pages.

אותן תבניות שמשרתות את השרת המקומי מרונדרות כאן לקבצי HTML, והנתונים
שהגרפים מושכים נשמרים כקבצי JSON. התוצאה היא אתר שלא צריך שרת בכלל.

שני הבדלים מהגרסה המקומית:

* **כתובות יחסיות** — GitHub Pages מגיש מתת-נתיב (`user.github.io/repo/`),
  ולכן כתובת מוחלטת כמו `/static/style.css` הייתה נשברת. כל תבנית מקבלת
  `base` שמתאים לעומק שלה בעץ.
* **אין כפתור בדיקה** — באתר סטטי אין שרת שיגרד. במקומו מוצג מתי בוצעה
  הבדיקה האחרונה, והעדכון קורה במשימה המתוזמנת של GitHub Actions.

הרצה:  python build_static.py [תיקיית-יעד]
"""
import hashlib
import json
import os
import shutil
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

import db
import sources
import aggregate as agg
import parties as P

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "docs")
STATIC_FILES = ("style.css", "app.js", "chart.umd.min.js")

# טווחי הזמן שהכפתורים בגרף הממוצע מציעים
RANGES = {"60": 60, "120": 120, "all": None}


def _env():
    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
        autoescape=select_autoescape(["html"]),
    )
    env.cache = None
    return env


def _asset_version():
    h = hashlib.md5()
    for name in ("app.js", "style.css"):
        path = os.path.join(BASE_DIR, "static", name)
        try:
            h.update(str(os.path.getmtime(path)).encode())
        except OSError:
            pass
    return h.hexdigest()[:8]


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # LF תמיד, כדי שהפלט יהיה זהה בין חלונות לשרת של GitHub
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def build(out_dir=OUT_DIR):
    env = _env()
    log = db.last_refresh()
    common = {
        "sources": sources.all_meta(),
        "bloc_names": P.BLOC_NAMES,
        "asset_v": _asset_version(),
        "static_mode": True,
        "auto_state": "off",
        "last_check": log["ran_at"] if log else None,
    }

    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # --- קבצים סטטיים ---
    for name in STATIC_FILES:
        src = os.path.join(BASE_DIR, "static", name)
        if os.path.exists(src):
            os.makedirs(os.path.join(out_dir, "static"), exist_ok=True)
            shutil.copy2(src, os.path.join(out_dir, "static", name))

    # GitHub Pages מריץ Jekyll כברירת מחדל ומתעלם מתיקיות שמתחילות בקו
    # תחתון. הקובץ הזה מכבה את זה ומגיש את הקבצים כמו שהם.
    _write(os.path.join(out_dir, ".nojekyll"), "")

    # --- עמוד ראשי ---
    _write(os.path.join(out_dir, "index.html"),
           env.get_template("index.html").render(
               base="./", page="home",
               avg=agg.average(), status=agg.source_status(), **common))

    # --- עמוד לכל מקור ---
    for key in sources.ORDER:
        polls = db.get_polls(source=key)
        _write(os.path.join(out_dir, "source", key, "index.html"),
               env.get_template("source.html").render(
                   base="../../", page=key,
                   src=sources.meta(key), polls=polls,
                   latest=polls[0] if polls else None,
                   order=P.order_keys, by_seats=P.order_by_seats,
                   display=P.display, color=P.color, **common))

    # --- נתוני הגרפים ---
    api = os.path.join(out_dir, "api")
    for name, days in RANGES.items():
        _write_json(os.path.join(api, f"chart-average-{name}.json"),
                    agg.average_series(limit_days=days))
    for key in sources.ORDER:
        _write_json(os.path.join(api, f"chart-{key}-all.json"),
                    agg.source_series(key, limit=100))

    # --- נתונים גולמיים, למי שרוצה להשתמש בהם ---
    _write_json(os.path.join(api, "average.json"), agg.average())
    _write_json(os.path.join(api, "status.json"), agg.source_status())
    _write_json(os.path.join(api, "polls.json"),
                {"polls": db.get_polls(), "generated_at": log["ran_at"] if log else None})

    files = sum(len(f) for _r, _d, f in os.walk(out_dir))
    return out_dir, files


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT_DIR
    db.init()
    path, files = build(out)
    total = sum(len(db.get_polls(k)) for k in sources.ORDER)
    print(f"נבנה אתר סטטי ב-{os.path.relpath(path, BASE_DIR)}: "
          f"{files} קבצים, {len(sources.ORDER)} עמודי מקורות, {total} סקרים.")


if __name__ == "__main__":
    main()
