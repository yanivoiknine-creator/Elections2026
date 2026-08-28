# -*- coding: utf-8 -*-
"""מכין תיקיית _upload/ להעלאה ידנית של הפרויקט ל-GitHub.

מעתיק רק את מה שצריך להיכנס למאגר — בלי docs/ שנבנה מחדש, בלי מסד
הנתונים הבינארי ובלי __pycache__. שני הקבצים ששמם מתחיל בנקודה מועתקים
לתיקייה נפרדת, כי גרירה של קבצים כאלה לאתר של GitHub לא עובדת ויש
ליצור אותם שם ידנית.

הרצה:  python make_upload.py
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "_upload")
SPECIAL = "_קבצים-מיוחדים"

ROOT_FILES = [
    "README.md", "requirements.txt", "run.bat", "run-lan.bat", "setup.bat",
    "app.py", "build_static.py", "pipeline.py", "make_upload.py",
    "save_chat.py", "preview.bat", "refresh-local.bat",
    "db.py", "parties.py", "sources.py", "aggregate.py", "refresh.py",
    "seed.py", "test_parser.py",
]
DIRS = ["scrapers", "static", "templates"]

NOTE = """שני הקבצים בתיקייה הזו לא נגררים ל-GitHub כמו השאר, כי שמם מתחיל בנקודה.
צריך ליצור אותם באתר של GitHub, דרך  Add file  ->  Create new file.


1) update.yml   — המשימה שמעדכנת את הסקרים ומפרסמת את האתר.  חובה.

   ב-Create new file, בשורת שם הקובץ הקלידו בדיוק:

       .github/workflows/update.yml

   (הקלדת הסלאש יוצרת את התיקיות אוטומטית)
   העתיקו לתוכו את כל התוכן של update.yml שכאן, ולחצו Commit changes.


2) gitignore.txt  — רשימת קבצים שלא נשמרים במאגר.  לא חובה, אבל מומלץ.

   Create new file, שם הקובץ:

       .gitignore

   (בלי סיומת txt!)
   העתיקו לתוכו את התוכן של gitignore.txt, ולחצו Commit changes.


את שאר הקבצים פשוט גוררים לחלון של  Add file -> Upload files.
אל תגררו את התיקייה הזו.
"""


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    for name in ROOT_FILES:
        src = os.path.join(BASE, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUT, name))

    for name in DIRS:
        shutil.copytree(os.path.join(BASE, name), os.path.join(OUT, name),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    polls = os.path.join(BASE, "data", "polls.json")
    if os.path.exists(polls):
        shutil.copy2(polls, os.path.join(OUT, "data", "polls.json"))

    sp = os.path.join(OUT, SPECIAL)
    os.makedirs(sp)
    shutil.copy2(os.path.join(BASE, ".gitignore"), os.path.join(sp, "gitignore.txt"))
    shutil.copy2(os.path.join(BASE, ".github", "workflows", "update.yml"),
                 os.path.join(sp, "update.yml"))
    with open(os.path.join(sp, "קרא-אותי.txt"), "w", encoding="utf-8") as f:
        f.write(NOTE)

    n = sum(len(f) for _r, _d, f in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _d, fs in os.walk(OUT) for f in fs)
    print(f"התיקייה _upload מוכנה: {n} קבצים, {size / 1024:.0f} KB")
    print(f"גררו את כל התוכן שלה ל-GitHub, חוץ מהתיקייה '{SPECIAL}'.")
    print(f"את שני הקבצים שבתוכה יוצרים ידנית — ההסבר בקובץ קרא-אותי.txt.")


if __name__ == "__main__":
    main()
