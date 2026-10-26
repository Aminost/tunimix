"""Rule-based ingredient parsing and language detection (German, French, English, Arabic).

"2 EL Olivenöl, extra vergine" -> Ingredient(amount="2", unit="EL", name="Olivenöl", note="extra vergine")
"1 cup flour (sifted)"          -> Ingredient(amount="120", unit="g", name="flour", note="sifted")
"3 gousses d'ail"               -> Ingredient(amount="3", unit="gousses", name="ail")
"""
from __future__ import annotations

import re
import unicodedata

from ..models import Ingredient

FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125}


def fold(text: str) -> str:
    """lowercase, accents removed - for matching only"""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("ß", "ss")


# ---------------- language ----------------
STOP = {
    "de": {"und", "der", "die", "das", "mit", "den", "dem", "ein", "eine", "geben", "minuten", "zugeben", "etwas",
           "oder", "auf", "für", "nach", "bis", "ist", "nicht", "zwiebel", "salz"},
    "fr": {"et", "le", "la", "les", "des", "du", "avec", "dans", "une", "un", "ajouter", "faire", "pour", "sur",
           "minutes", "puis", "jusqu", "au", "sel", "huile", "oignon"},
    "en": {"and", "the", "with", "add", "of", "to", "into", "until", "for", "minutes", "then", "a", "on", "salt",
           "oil", "onion", "cup", "cups"},
}
ARABIC = re.compile(r"[؀-ۿ]")


def detect_language(text: str) -> str:
    if not text:
        return "de"
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if ARABIC.match(c)) / len(letters) > 0.3:
        return "ar"
    words = re.findall(r"[a-zA-ZäöüÄÖÜßéèêàâçîïôûù']+", text.lower())
    score = {k: sum(1 for w in words if w in v) for k, v in STOP.items()}
    return max(score, key=score.get) if any(score.values()) else "de"


# ---------------- units ----------------
# alias (folded) -> (canonical key, factor to the base unit)
UNIT_ALIASES = {
    "g": ("g", 1), "gr": ("g", 1), "gramm": ("g", 1), "gramme": ("g", 1), "grammes": ("g", 1), "grams": ("g", 1), "gram": ("g", 1),
    "kg": ("g", 1000), "kilo": ("g", 1000), "kilogramm": ("g", 1000), "kilogramme": ("g", 1000),
    "mg": ("g", 0.001),
    "ml": ("ml", 1), "milliliter": ("ml", 1), "millilitre": ("ml", 1), "millilitres": ("ml", 1),
    "cl": ("ml", 10), "dl": ("ml", 100), "l": ("ml", 1000), "liter": ("ml", 1000), "litre": ("ml", 1000),
    "litres": ("ml", 1000), "liters": ("ml", 1000),
    "oz": ("g", 28.35), "ounce": ("g", 28.35), "ounces": ("g", 28.35), "lb": ("g", 453.6), "lbs": ("g", 453.6),
    "pound": ("g", 453.6), "pounds": ("g", 453.6),
    "cup": ("cup", 1), "cups": ("cup", 1), "tasse": ("cup", 1), "tassen": ("cup", 1), "tasses": ("cup", 1),
    "verre": ("glass", 1), "verres": ("glass", 1), "glas": ("glass", 1), "glass": ("glass", 1),
    "el": ("tbsp", 1), "essloffel": ("tbsp", 1), "essloeffel": ("tbsp", 1), "tbsp": ("tbsp", 1), "tbs": ("tbsp", 1),
    "tablespoon": ("tbsp", 1), "tablespoons": ("tbsp", 1), "cas": ("tbsp", 1), "c.a.s.": ("tbsp", 1), "c.a.s": ("tbsp", 1),
    "c. a s.": ("tbsp", 1), "c. a s": ("tbsp", 1), "cuillere a soupe": ("tbsp", 1), "cuilleres a soupe": ("tbsp", 1),
    "c. a soupe": ("tbsp", 1), "cs": ("tbsp", 1),
    "tl": ("tsp", 1), "teeloffel": ("tsp", 1), "teeloeffel": ("tsp", 1), "tsp": ("tsp", 1), "teaspoon": ("tsp", 1),
    "teaspoons": ("tsp", 1), "cac": ("tsp", 1), "c.a.c.": ("tsp", 1), "c.a.c": ("tsp", 1), "c. a c.": ("tsp", 1),
    "c. a c": ("tsp", 1), "cuillere a cafe": ("tsp", 1), "cuilleres a cafe": ("tsp", 1), "c. a cafe": ("tsp", 1), "cc": ("tsp", 1),
    "prise": ("pinch", 1), "prisen": ("pinch", 1), "pinch": ("pinch", 1), "pincee": ("pinch", 1), "pincees": ("pinch", 1),
    "msp": ("knifetip", 1), "messerspitze": ("knifetip", 1),
    "bund": ("bunch", 1), "bunch": ("bunch", 1), "botte": ("bunch", 1), "bouquet": ("bunch", 1),
    "zehe": ("clove", 1), "zehen": ("clove", 1), "clove": ("clove", 1), "cloves": ("clove", 1),
    "gousse": ("clove", 1), "gousses": ("clove", 1),
    "dose": ("can", 1), "dosen": ("can", 1), "can": ("can", 1), "cans": ("can", 1), "tin": ("can", 1),
    "boite": ("can", 1), "boites": ("can", 1),
    "pck": ("pack", 1), "pck.": ("pack", 1), "packung": ("pack", 1), "packchen": ("pack", 1), "pack": ("pack", 1),
    "packet": ("pack", 1), "sachet": ("pack", 1), "sachets": ("pack", 1),
    "scheibe": ("slice", 1), "scheiben": ("slice", 1), "slice": ("slice", 1), "slices": ("slice", 1),
    "tranche": ("slice", 1), "tranches": ("slice", 1),
    "handvoll": ("handful", 1), "handful": ("handful", 1), "poignee": ("handful", 1),
    "stuck": ("piece", 1), "stk": ("piece", 1), "piece": ("piece", 1), "pieces": ("piece", 1),
    "wurfel": ("cube", 1), "cube": ("cube", 1), "cubes": ("cube", 1),
}
UNIT_NAMES = {
    "de": {"g": "g", "ml": "ml", "tbsp": "EL", "tsp": "TL", "pinch": "Prise", "knifetip": "Msp.", "bunch": "Bund",
           "clove": "Zehe(n)", "can": "Dose", "pack": "Pck.", "slice": "Scheibe(n)", "handful": "Handvoll", "piece": "Stück", "cube": "Würfel"},
    "fr": {"g": "g", "ml": "ml", "tbsp": "c. à s.", "tsp": "c. à c.", "pinch": "pincée", "knifetip": "pointe de couteau",
           "bunch": "botte", "clove": "gousse(s)", "can": "boîte", "pack": "sachet", "slice": "tranche(s)",
           "handful": "poignée", "piece": "pièce(s)", "cube": "cube"},
    "en": {"g": "g", "ml": "ml", "tbsp": "tbsp", "tsp": "tsp", "pinch": "pinch", "knifetip": "knife tip", "bunch": "bunch",
           "clove": "clove(s)", "can": "can", "pack": "packet", "slice": "slice(s)", "handful": "handful", "piece": "piece(s)", "cube": "cube"},
}
UNIT_NAMES["ar"] = UNIT_NAMES["fr"]
# grams per cup for dry goods (Thermomix weighs) - folded keyword -> g/cup
CUP_GRAMS = {"mehl": 120, "flour": 120, "farine": 120, "zucker": 200, "sugar": 200, "sucre": 200, "reis": 185,
             "rice": 185, "riz": 185, "couscous": 180, "griess": 170, "semolina": 170, "semoule": 170, "butter": 227,
             "beurre": 227, "haferflocken": 90, "oats": 90, "flocons": 90, "kakao": 100, "cocoa": 100, "cacao": 100,
             "puderzucker": 120, "icing": 120, "glace": 120, "nusse": 120, "nuts": 120, "noix": 120, "linsen": 190,
             "lentils": 190, "lentilles": 190, "kichererbsen": 180, "chickpeas": 180, "pois chiches": 180}
CUP_ML, GLASS_ML = 240, 200

AMOUNT = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?\s*[½¼¾⅓⅔⅛]?|[½¼¾⅓⅔⅛])"
LINE_RE = re.compile(rf"^\s*[-•*·–]?\s*(?P<amount>{AMOUNT}(?:\s*(?:-|–|bis|à|a|to|or|oder|ou)\s*{AMOUNT})?)?\s*(?P<rest>.*)$")


def to_number(s: str) -> float | None:
    s = s.strip().replace(",", ".")
    try:
        if " " in s and "/" in s:
            whole, frac = s.split()
            a, b = frac.split("/")
            return float(whole) + float(a) / float(b)
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        for f, v in FRACTIONS.items():
            if f in s:
                rest = s.replace(f, "").strip()
                return (float(rest) if rest else 0) + v
        return float(s)
    except (ValueError, ZeroDivisionError):
        return None


def fmt_number(x: float) -> str:
    if x >= 10:
        return str(int(round(x / 5) * 5)) if x >= 50 else str(int(round(x)))
    for f, v in FRACTIONS.items():
        if abs(x - int(x) - v) < 0.02 and v in (0.5, 0.25, 0.75):
            return f"{int(x)}{f}" if int(x) else f
    return f"{x:.1f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))


def _match_unit(rest: str) -> tuple[str | None, float, str]:
    f = fold(rest)
    # longest alias first so "cuillere a soupe" wins over "c"
    for alias in sorted(UNIT_ALIASES, key=len, reverse=True):
        if f.startswith(alias) and (len(f) == len(alias) or not f[len(alias)].isalpha()):
            key, factor = UNIT_ALIASES[alias]
            return key, factor, rest[len(alias):].lstrip(" .")
    return None, 1, rest


def parse_ingredient(line: str, lang: str = "de", group: str = "") -> Ingredient | None:
    line = re.sub(r"\s+", " ", line).strip().strip("-•*· ")
    if not line or len(line) > 200:
        return None
    m = LINE_RE.match(line)
    amount_txt = (m.group("amount") or "").strip()
    rest = m.group("rest").strip()
    unit_key, factor, rest = _match_unit(rest)
    rest = re.sub(r"^(de |d'|d’|of |von )", "", rest, flags=re.I)
    note = ""
    paren = re.search(r"\(([^)]*)\)", rest)
    if paren:
        note = paren.group(1).strip()
        rest = (rest[:paren.start()] + rest[paren.end():]).strip()
    if "," in rest and (amount_txt or unit_key):
        rest, extra = rest.split(",", 1)
        note = ", ".join(x for x in (note, extra.strip()) if x)
    name = rest.strip(" ,;:")
    if not name:
        return None
    amount, unit = amount_txt, ""
    nums = re.findall(AMOUNT, amount_txt)
    values = [to_number(n) for n in nums]
    if unit_key in ("cup", "glass") and values and all(v is not None for v in values):
        per = next((g for k, g in CUP_GRAMS.items() if k in fold(name)), None)
        if unit_key == "glass" or per is None:
            ml = CUP_ML if unit_key == "cup" else GLASS_ML
            amount, unit = "-".join(fmt_number(v * ml) for v in values), "ml"
        else:
            amount, unit = "-".join(fmt_number(v * per) for v in values), "g"
    elif unit_key in ("g", "ml") and values and all(v is not None for v in values):
        amount, unit = "-".join(fmt_number(v * factor) for v in values), unit_key
    elif unit_key:
        amount = amount_txt.replace(" ", "")
        unit = UNIT_NAMES.get(lang, UNIT_NAMES["de"])[unit_key]
    return Ingredient(amount=amount, unit=unit, name=name, note=note, group=group)


DESCRIPTORS = {"frisch", "frische", "frischer", "fresh", "frais", "fraiche", "gehackt", "gehackte", "chopped",
               "gros", "grosse", "grand", "grande", "klein", "kleine", "small", "large", "big", "rot", "rote", "roter",
               "red", "rouge", "rouges", "grun", "grune", "green", "vert", "verte", "verts", "getrocknet", "getrocknete",
               "dried", "sec", "seche", "moulu", "moulue", "gemahlen", "gemahlener", "ground", "fein", "feine", "fine",
               "extra", "natives", "olive", "huile", "d", "de", "du", "la", "le", "les", "of", "the", "a", "un", "une"}


COMPOUND_HEADS = ("zehen", "zehe", "fleisch", "brust", "schenkel", "pulver", "stangen", "stange", "blatter",
                  "blatt", "wurfel", "scheiben", "filet", "filets")


def ingredient_words(ing: Ingredient) -> list[str]:
    """Significant folded words of an ingredient name, plus compound bases ('knoblauchzehen' -> 'knoblauch')."""
    words = [w for w in re.findall(r"[a-z\u0600-\u06FF]+", fold(ing.name)) if len(w) >= 3]
    keys = [w for w in words if w not in DESCRIPTORS] or words
    out = []
    for w in keys[:3]:
        out.append(w)
        for head in COMPOUND_HEADS:
            if w.endswith(head) and len(w) - len(head) >= 3:
                out.append(w[:-len(head)])
    return out


def token_match(t: str, w: str) -> bool:
    """Does text token t refer to ingredient word w? Handles plurals and compounds."""
    if t == w:
        return True
    if len(t) < 3 or len(w) < 3:
        return False
    common = 0
    for x, y in zip(t, w):
        if x != y:
            break
        common += 1
    short = min(len(t), len(w))
    if common >= max(3, short - 2) and abs(len(t) - len(w)) <= 3:
        return True          # zwiebel/zwiebeln, tomate/tomates, oeuf/oeufs
    if len(t) >= 5 and w.endswith(t) and len(w) - len(t) >= 3:
        return True          # bruhe -> gemusebruhe
    if len(w) >= 4 and len(t) - len(w) >= 3 and (t.endswith(w) or (len(w) >= 6 and t.startswith(w))):
        return True          # zitronensaft -> saft / zitrone, knoblauchzehe -> knoblauch
    return False


def ingredient_keys(ing: Ingredient) -> list[str]:  # kept for backwards compatibility
    return ingredient_words(ing)


OIL_RE = re.compile(r"\b(ol|oel|oil|huile|زيت)\b|olivenol|sonnenblumenol|rapsol|\bbutter\b|\bbeurre\b|\bsmen\b", re.I)


def is_fat(ing: Ingredient) -> bool:
    return bool(OIL_RE.search(fold(ing.name)))
