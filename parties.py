# -*- coding: utf-8 -*-
"""רשימת המפלגות הקנונית + זיהוי שמות חלופיים.

כל אתר קורא למפלגות בשם קצת אחר ("ישר!", "ישר! עם איזנקוט", "מפלגת ישר").
המודול הזה ממפה כל וריאציה למזהה קנוני אחד, כדי שהגרפים והממוצע יעבדו.
"""
import re

# key -> (שם תצוגה, צבע, גוש)
# גושים: 'bibi' = גוש נתניהו, 'change' = גוש השינוי, 'arab' = מפלגות ערביות
PARTIES = {
    "likud":        ("הליכוד",              "#2563eb", "bibi"),
    "shas":         ("ש\"ס",                "#0f766e", "bibi"),
    "yahadut":      ("יהדות התורה",         "#111827", "bibi"),
    "otzma":        ("עוצמה יהודית",        "#a16207", "bibi"),
    "tzionut":      ("הציונות הדתית",       "#ea580c", "bibi"),
    "winter":       ("עמך ישראל (וינטר)",   "#92400e", "bibi"),

    "yashar":       ("ישר! (איזנקוט)",      "#dc2626", "change"),
    "beyahad":      ("ביחד (בנט)",          "#7c3aed", "change"),
    "democrats":    ("הדמוקרטים",           "#db2777", "change"),
    "yisrael_beit": ("ישראל ביתנו",         "#0891b2", "change"),
    "kachol_lavan": ("כחול לבן",            "#1e3a8a", "change"),
    "bayit_tzioni": ("הבית הציוני (טרופר-הנדל)", "#65a30d", "change"),
    "ahdut":        ("האחדות (ארדן-אדלשטיין)",   "#78716c", "change"),
    "yesh_atid":    ("יש עתיד",             "#0284c7", "change"),

    "joint":        ("הרשימה המשותפת",      "#059669", "arab"),
    "hadash_taal":  ("חד\"ש-תע\"ל",          "#16a34a", "arab"),
    "balad":        ("בל\"ד",                "#4d7c0f", "arab"),
    "raam":         ("רע\"ם",                "#15803d", "arab"),
}

BLOC_NAMES = {"bibi": "גוש נתניהו", "change": "גוש השינוי", "arab": "המפלגות הערביות"}

# הביטויים נבדקים לפי הסדר — הספציפי לפני הכללי.
# חשוב: "הרשימה המשותפת" לפני "חד\"ש", ו-"בית ציוני" לפני "ציונות".
ALIASES = [
    # שלושת הרכיבים ברצף = הרשימה המאוחדת, לא שלוש מפלגות נפרדות
    ("joint",        [r'חד"?ש\s*[-–]\s*תע"?ל\s*[-–]\s*בל"?ד',
                      r"הרשימה\s+ה?ערבית\s+ה?משותפת",
                      r"הרשימה\s+המשותפת", r"\bהמשותפת\b"]),
    ("bayit_tzioni", [r"הבית\s+הציוני", r"בית\s+ציוני", r"המילואימניקים",
                      r"טרופר", r"הנדל"]),
    ("tzionut",      [r"הציונות\s+הדתית", r"ציונות\s+דתית", r"סמוטריץ"]),
    ("hadash_taal",  [r'חד"?ש\s*[-–]\s*תע"?ל', r'חד״ש\s*[-–]\s*תע״ל', r'\bחד"?ש\b', r"\bחד״ש\b"]),
    ("balad",        [r'\bבל"?ד\b', r"\bבל״ד\b"]),
    ("raam",         [r'\bרע"?[םמ]\b', r"\bרע״[םמ]\b", r"עבאס"]),
    ("yashar",       [r"ישר\s*!", r"\bישר\b", r"איזנקוט"]),
    ("beyahad",      [r"\bביחד\b", r"\bבנט\b"]),
    ("democrats",    [r"הדמוקרטים", r"\bגולן\b"]),
    ("yisrael_beit", [r"ישראל\s+ביתנו", r"ליברמן"]),
    ("kachol_lavan", [r"כחול[-–\s]+לבן", r"\bגנץ\b"]),
    ("ahdut",        [r"האחדות", r"\bארדן\b", r"אדלשטיין"]),
    ("yesh_atid",    [r"יש\s+עתיד", r"לפיד"]),
    ("otzma",        [r"עוצמה\s+יהודית", r"בן\s*גביר"]),
    ("yahadut",      [r"יהדות\s+התורה", r"\bדגל\b", r"אגודת\s+ישראל"]),
    ("shas",         [r'\bש"?ס\b', r"\bש״ס\b", r"\bדרעי\b"]),
    ("likud",        [r"הליכוד", r"\bליכוד\b", r"נתניהו"]),
    ("winter",       [r"עמך\s+ישראל", r"וינטר", r"\bימין\b"]),
]

_COMPILED = [(k, [re.compile(p) for p in pats]) for k, pats in ALIASES]

# גרשיים בעברית נכתבים בכמה תווים שונים, וכך גם גרש. בלי נרמול,
# צורות שונות של אותה מפלגה היו נראות כמפלגות שונות.
_NORM = str.maketrans({
    "״": '"', "″": '"', "”": '"', "“": '"',
    "„": '"', "‟": '"',
    "׳": "'", "′": "'", "’": "'", "‘": "'",
    "‏": "", "‎": "", " ": " ",
})


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_NORM)).strip()


def match_party(raw_name: str):
    """מחזיר מזהה קנוני לשם מפלגה כלשהו, או None אם לא זוהה."""
    t = normalize(raw_name)
    if not t:
        return None
    for key, pats in _COMPILED:
        for p in pats:
            if p.search(t):
                return key
    return None


def display(key: str) -> str:
    return PARTIES.get(key, (key, "", ""))[0]


def color(key: str) -> str:
    return PARTIES.get(key, (key, "#94a3b8", ""))[1]


def bloc(key: str) -> str:
    return PARTIES.get(key, (key, "", ""))[2]


def order_keys(keys):
    """סדר תצוגה קבוע: לפי הסדר שהוגדר ב-PARTIES."""
    idx = {k: i for i, k in enumerate(PARTIES)}
    return sorted(keys, key=lambda k: idx.get(k, 999))


def order_by_seats(results):
    """(מפתח, מנדטים) ממוין מהגבוה לנמוך.

    שוויון נשבר לפי סדר התצוגה הקבוע, כדי שמפלגות עם אותו מספר מנדטים
    יופיעו תמיד באותו סדר ולא יקפצו בין רענונים.
    """
    idx = {k: i for i, k in enumerate(PARTIES)}
    return sorted(results.items(), key=lambda kv: (-kv[1], idx.get(kv[0], 999)))
