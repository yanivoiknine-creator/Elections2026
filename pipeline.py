# -*- coding: utf-8 -*-
"""הצינור המלא שרץ ב-GitHub Actions: נתונים -> גרידה -> אתר סטטי.

    1. טוען את הסקרים ששמורים ב-data/polls.json (זיכרון הריצות הקודמות)
    2. משלים היסטוריה מהארכיונים הפתוחים, אם חסר משהו
    3. גורד את כל האתרים ומחפש סקרים חדשים
    4. שומר בחזרה ל-JSON ובונה את האתר הסטטי ל-docs/

הצינור בנוי כך שגם אם הכל נכשל, האתר עדיין נבנה מהנתונים ששמורים ב-JSON.
אתרי חדשות חוסמים לפעמים כתובות של שרתי ענן, ועדיף אתר עם נתונים מאתמול
מאשר בנייה שנכשלת.

הרצה מקומית:  python pipeline.py
"""
import sys
import traceback

import db
import seed
import refresh as refresher
import sources
import build_static


def _step(title, fn):
    print(f"\n--- {title} ---")
    try:
        return fn()
    except Exception as e:
        print(f"  נכשל: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)
        return None


def main():
    db.init()

    _step("טוען נתונים שמורים", lambda: print(f"  נטענו {db.import_json()} סקרים מ-JSON"))

    def do_seed():
        total = 0
        for key in sources.ORDER:
            try:
                total += seed.seed_source(key, verbose=False)
            except Exception as e:
                print(f"  {key}: {type(e).__name__}: {e}")
        print(f"  הושלמו {total} סקרים מהארכיונים")
    _step("משלים היסטוריה מהארכיונים", do_seed)

    def do_refresh():
        out = refresher.refresh_all()
        for r in out["results"]:
            print(f"  {r['source']:<7} {r['status']:<10} {r.get('message', '')}")
        print(f"  => {out['summary']}")
        return out
    out = _step("גורד את האתרים", do_refresh)

    _step("שומר ל-JSON", lambda: print(f"  נשמרו {db.export_json()} סקרים"))

    def do_build():
        path, files = build_static.build()
        print(f"  נבנו {files} קבצים")
    _step("בונה את האתר הסטטי", do_build)

    print("\n--- סיכום ---")
    total = 0
    for key in sources.ORDER:
        polls = db.get_polls(key)
        total += len(polls)
        last = polls[0]["poll_date"] if polls else "—"
        print(f"  {sources.SOURCES[key]['name']:<12} {len(polls):>3} סקרים | אחרון {last}")
    print(f"  סה\"כ {total} סקרים")

    # אם כל המקורות נכשלו, כנראה נחסמנו — מסמנים כישלון כדי שיהיה
    # אפשר לראות את זה ביומן, אבל האתר כבר נבנה מהנתונים השמורים.
    if out and len(out["errors"]) == len(sources.ORDER):
        print("\n  אזהרה: כל המקורות נכשלו. האתר נבנה מהנתונים השמורים.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
