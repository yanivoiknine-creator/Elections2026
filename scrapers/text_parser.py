# -*- coding: utf-8 -*-
"""חילוץ מנדטים לכל מפלגה מתוך טקסט עברי חופשי של כתבת סקר.

הכתבות מנוסחות כפרוזה, למשל:
    "המפלגה השנייה בגודלה היא הליכוד ... ומתייצבת על 23 מנדטים"
    "עוצמה יהודית ויהדות התורה, שמקבלות 8 מנדטים כל אחת"
    "הדמוקרטים של יאיר גולן עם 11, ישראל ביתנו עם 9"

העיבוד הוא **משפט-משפט**. זה חשוב משתי סיבות:

1. משפטי תרחיש היפותטי ("ומה קורה בתרחיש האיחודים? איחוד של איזנקוט, בנט
   וטרופר עם 36 מנדטים") מדלגים בשלמותם. בלי זה הם מזהמים את התוצאות.
2. מספר "יחף" בלי המילה מנדטים ("הדמוקרטים עם 11,") מתקבל רק במשפט שמדבר
   על מנדטים, כך ש-"46%" או "2,685 משיבים" לא נחשבים בטעות.

בתוך משפט, כל מספר משויך למפלגות שהוזכרו מאז המספר הקודם — מה שמטפל נכון
גם ב-"X, Y ו-Z ... 8 מנדטים כל אחת".

האתגר הנוסף הוא להבחין בין תוצאה ("מקבלת 9 מנדטים") לבין שינוי לעומת הסקר
הקודם ("עלייה של שלושה מנדטים") או סכום גוש ("גוש נתניהו על 51 מנדטים").
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parties as P

# "23 מנדטים". דורש ספרה, ולכן "מאבדת מנדט" לא נתפס.
SEATS_RE = re.compile(r"(\d{1,2})\s+מנדט(?:ים)?\b")

# מספר בלי המילה "מנדטים" אחרי "עם"/"על" — "הדמוקרטים עם 11, ישראל ביתנו עם 9".
# מותר רק במשפט שמדבר על מנדטים. השלילה חוסמת אחוזים ומספרים ארוכים
# ("2,685 משיבים", "3.4%") אבל לא פסיק או נקודה שהם סימני פיסוק ("עם 9,").
BARE_SEATS_RE = re.compile(r"\b(?:עם|על)\s+(\d{1,2})(?!\d|[,.]\d|\s*%)")

# מספר צמוד לשם מפלגה, בלי פועל ובלי המילה מנדטים — "ישראל ביתנו 6, רע"ם 5".
# הצמידות היא מה שהופך את זה לבטוח: מרשים רק רווח או מקף מפריד.
ADJACENT_SEATS_RE = re.compile(r"^[\s\-–—:]{0,3}(\d{1,2})(?!\d|[,.]\d|\s*%)")

# המספר הוא סכום גוש, לא תוצאה של מפלגה בודדת
BLOCK_MARK = re.compile(r"(גוש|הגוש|בסך\s+הכול|סך\s+הכל|בלוק|המחנה|רוב\s+של|קואליציה|אופוזיציה)")

# המספר הוא התוצאה של המפלגה
RESULT_MARK = re.compile(
    r"(מקבל\w*|תקבל\w*|יקבל\w*|קיבל\w*|זוכ\w*|מסתפק\w*|רושמ\w*|משיג\w*|"
    r"עומד\w*\s+(?:\w+\s+){0,2}על|"
    r"מתייצב\w*\s+(?:\w+\s+){0,2}על|"
    r"נשאר\w*\s+(?:\w+\s+){0,2}(?:עם|על)|"
    r"נותר\w*\s+(?:\w+\s+){0,2}(?:עם|על)|"
    r"מגיע\w*\s+ל|תרד\s+ל|תעלה\s+ל|יורד\w*\s+ל|עולה\s+ל|"
    r"צונח\w*\s+ל|מזנק\w*\s+ל|מטפס\w*\s+ל|נופל\w*\s+ל|"
    r"\bעם\b|\bעל\b)"
)

# המספר הוא שינוי לעומת סקר קודם, לא תוצאה
DELTA_MARK = re.compile(
    r"(עלייה|עליה|ירידה|מאבד\w*|מוסיפ\w*|צניחה|זינוק|גדל\w*|קטן\w*|"
    r"נחלש\w*|מתחזק\w*|התחזק\w*|מתרסק\w*|"
    r"לעומת|בהשוואה|פחות\s+מ|יותר\s+מ|עולה\s+ב|יורד\w*\s+ב|"
    r"בסקר\s+הקודם|בשבוע\s+שעבר|שבשבוע|בפעם\s+הקודמת)"
)

# הפניה מפורשת לסקר קודם. "שבשבוע שעבר קיבלה 4 מנדטים" הוא ערך היסטורי גם
# אם יש אחריו פועל תוצאה, ולכן סימן כזה גובר על הכלל של הקרוב-מנצח.
PAST_REF = re.compile(
    r"(בשבוע\s+שעבר|בסקר\s+הקודם|בסקר\s+האחרון\s+שלנו|לפני\s+שבוע|"
    r"בפעם\s+הקודמת|שבשבוע\s+שעבר)")

# "יורדת ל-7 מנדטים" — הצורה "ל-N" תמיד מציינת את הערך החדש, ולכן היא
# סימן תוצאה חזק שגובר על פועל שינוי שקדם לו ("מאבדת מנדט אחד ויורדת ל-7").
TO_VALUE = re.compile(r"\bל-\s*$")

# משפט שמתאר תרחיש היפותטי ולא את תוצאת הסקר בפועל
SCENARIO_MARK = re.compile(
    r"(תרחיש|במצב\s+הזה|במקרה\s+כזה|לו\s+היו\s+מתאחד|"
    r"איחוד\s+(?:\S+\s+){0,2}(?:של|בין)|"      # "איחוד של", "איחוד גדול של"
    r"אם\s+יתאחד|אם\s+ירוצ|אם\s+ירוץ|ריצה\s+משותפת|בריצה\s+משותפת|"
    r"אלא\s+אם|היה\s+רץ|יהיה\s+שונה)")

# "הציונות הדתית ... עם 5 מנדטים, וכך גם רע"ם" — המפלגה שאחרי הקישור
# מקבלת את אותו ערך, למרות שהיא מוזכרת אחרי המספר.
SAME_AS_PREV = re.compile(r"^[,;\s]*(?:ו?כך\s+גם|כמו\s+גם|וכן\s+גם|כמו\s+כן)\b")

# "8 מנדטים כל אחת" / "7 מנדטים לכל רשימה" — כל המפלגות בקבוצה מקבלות
# את אותו מספר, ולא רק האחרונה שהוזכרה.
SHARE_ALL = re.compile(r"\s*(?:מנדטים\s+)?ל?כל\s+(?:אח[תד]|רשימה|מפלגה)")

# חלון החיפוש לאחור מהמספר
WINDOW = 70

# רשימה מאוחדת "בולעת" את רכיביה: "הרשימה הערבית המשותפת של חד"ש, תע"ל
# ובל"ד" היא מפלגה אחת, לא שלוש. בלי זה המספר היה נצמד לרכיב האחרון.
COMPONENTS = {"joint": {"hadash_taal", "balad"}}
ABSORB_WINDOW = 70

# הנקודה שבין ספרות היא נקודה עשרונית ("2.1%"), לא סוף משפט. בלי החריגה
# הזו, משפט רשימת המפלגות שמתחת לאחוז החסימה מתפרק לרסיסים.
_SENT_SPLIT = re.compile(r"(?<!\d)\.(?!\d)|[?!●]|\n")


def _sentences(text):
    """פיצול גס למשפטים. מספיק טוב לכתבות חדשות."""
    out, start = [], 0
    for m in _SENT_SPLIT.finditer(text):
        seg = text[start:m.start()].strip()
        if seg:
            out.append(seg)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _party_mentions(text):
    """כל אזכורי המפלגות בטקסט, כרשימת (מיקום, אורך, מזהה)."""
    out = []
    for key, pats in P._COMPILED:
        for p in pats:
            for m in p.finditer(text):
                out.append((m.start(), m.end() - m.start(), key))
    # מסירים חפיפות: בהתאמות שמתחילות באותו מקום, שומרים את הארוכה יותר
    out.sort(key=lambda x: (x[0], -x[1]))
    kept, last_end = [], -1
    for start, length, key in out:
        if start >= last_end:
            kept.append((start, length, key))
            last_end = start + length

    # בליעת רכיבים של רשימה מאוחדת שהוזכרו מיד אחריה
    absorbed, block_until, block_set = [], -1, set()
    for start, length, key in kept:
        if start < block_until and key in block_set:
            continue
        absorbed.append((start, length, key))
        if key in COMPONENTS:
            block_until = start + ABSORB_WINDOW
            block_set = COMPONENTS[key]
    return absorbed


def _classify(sent, num_start):
    """מסווג מספר מנדטים: 'result' / 'delta' / 'bloc' / 'unknown'.

    כשגם סימן-תוצאה וגם סימן-שינוי מופיעים לפני המספר, מנצח הקרוב יותר אליו.
    כך "שעולה במנדט לעומת השבוע שעבר ומקבלת 13 מנדטים" נקרא נכון.
    """
    win = sent[max(0, num_start - WINDOW):num_start]
    if BLOCK_MARK.search(win):
        return "bloc"
    if TO_VALUE.search(win):
        return "result"
    for m in PAST_REF.finditer(win):
        if not re.search(r"[,;:]", win[m.end():]):
            return "delta"
    res = [m.end() for m in RESULT_MARK.finditer(win)]
    dlt = [m.end() for m in DELTA_MARK.finditer(win)]
    last_res = max(res) if res else -1
    last_dlt = max(dlt) if dlt else -1
    if last_res > last_dlt:
        return "result"
    if last_dlt >= 0:
        return "delta"
    return "unknown"   # בלי סימן ברור — לא מנחשים


def _seat_numbers(sent, mentions=()):
    """(ערך, התחלה, סוף) לכל מספר מנדטים במשפט, לפי סדר הופעה.

    הצורות ללא המילה "מנדטים" מותרות רק במשפט שמדבר על מנדטים, כדי
    ש-"46%" או "2,685 משיבים" לא ייחשבו בטעות.
    """
    found = {}
    for m in SEATS_RE.finditer(sent):
        found[m.start(1)] = (int(m.group(1)), m.start(1), m.end())
    if "מנדט" not in sent:
        return [found[k] for k in sorted(found)]

    for m in BARE_SEATS_RE.finditer(sent):
        if m.start(1) not in found and int(m.group(1)) <= 60:
            found[m.start(1)] = (int(m.group(1)), m.start(1), m.end())
    for pos, length, _key in mentions:
        m = ADJACENT_SEATS_RE.match(sent[pos + length:])
        if not m:
            continue
        start = pos + length + m.start(1)
        if start not in found and int(m.group(1)) <= 60:
            found[start] = (int(m.group(1)), start, pos + length + m.end())
    return [found[k] for k in sorted(found)]


def _parse_sentence(sent, results):
    mentions = _party_mentions(sent)
    if not mentions:
        return
    consumed = 0
    last_value = last_end = None
    for seats, start, end in _seat_numbers(sent, mentions):
        if seats > 120:
            continue
        kind = _classify(sent, start)
        if kind != "result":
            # סכום גוש "צורך" את אזכורי המפלגות שלפניו — הם כבר טופלו.
            # שינוי ("עלייה של 3 מנדטים") משאיר את המפלגה ממתינה לתוצאה שלה.
            if kind == "bloc":
                consumed = sum(1 for x in mentions if x[0] < start)
            continue

        group = [k for (pos, _l, k) in mentions[consumed:] if pos < start]
        consumed += len(group)
        if not group:
            continue
        # "כל אחת" / "לכל אחת" => כל המפלגות בקבוצה מקבלות את אותו מספר.
        # אחרת — רק המפלגה האחרונה שהוזכרה היא הנושא של המספר.
        share_all = bool(SHARE_ALL.match(sent[end:end + 30]))
        for k in (group if share_all else group[-1:]):
            results.setdefault(k, float(seats))
        last_value, last_end = float(seats), end

    # "... עם 5 מנדטים, וכך גם רע"ם" — מפלגה שמוזכרת אחרי המספר ומקושרת אליו
    if last_value is not None and consumed < len(mentions):
        rest = mentions[consumed:]
        if SAME_AS_PREV.match(sent[last_end:rest[0][0]]):
            for _pos, _l, k in rest:
                results.setdefault(k, last_value)


def parse_seats(text, include_zeros=True):
    """טקסט כתבה -> {party_key: seats}. מחזיר רק מה שזוהה בוודאות."""
    text = P.normalize(text)
    if not text:
        return {}

    results = {}
    for sent in _sentences(text):
        if SCENARIO_MARK.search(sent):
            continue          # תרחיש היפותטי — לא תוצאת הסקר
        _parse_sentence(sent, results)

    if include_zeros:
        for k, v in parse_below_threshold(text).items():
            results.setdefault(k, v)
    return results


def parse_below_threshold(text):
    """מפלגות שנאמר עליהן במפורש שאינן עוברות את אחוז החסימה -> 0 מנדטים."""
    out = {}
    for sent in _sentences(P.normalize(text)):
        if "אחוז החסימה" not in sent:
            continue
        if not re.search(r"(לא\s+עובר|לא\s+עבר|אינן?\s+עובר|נופל|מתחת)", sent):
            continue
        # מתעלמים ממשפט תנאי ("אך אם ירוץ עם X - יעבור")
        if SCENARIO_MARK.search(sent):
            continue
        for _pos, _l, key in _party_mentions(sent):
            out.setdefault(key, 0.0)
    return out
