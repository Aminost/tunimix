"""Rule-based Thermomix converter. No AI, no API key, no internet, fully deterministic.

How a normal recipe step becomes a Thermomix step:
  1. split the instructions into single actions ("…, then …", "…; …", sentences)
  2. detect the action with a multilingual lexicon (de / fr / en, basic Arabic):
       chop, grate, grind, sauté, toast, simmer/cook, boil, reduce, blend, mix, fold, knead,
       whip, steam, syrup, melt, heat, add  - or "off machine" (oven, deep-fry, rest, shape, serve …)
  3. find which ingredients the step talks about (from the ingredient list)
  4. pick proven Thermomix settings for that action + those ingredients
       e.g. chop onion -> 5 Sek./Stufe 5, herbs -> 3 Sek./Stufe 7 in a dry bowl,
            meat in sauce -> 100°C/Linkslauf/Sanftrührstufe, purée -> 1 Min./Stufe 10 …
     times written in the text ("20 minutes", "1 Std.", "15-20 min") are used when present
  5. write a Cookidoo-style step from a template in the recipe's language
  6. move "dry bowl" steps (herbs, nuts, spices) to the start, then the shared validator applies
     the hard limits (99-min timers, 2.2 L bowl, Linkslauf for pieces …)
Every step the rules are unsure about is listed under "Bitte prüfen".
"""
from __future__ import annotations

import re

from ..models import Ingredient, Recipe, Step, TMSetting
from .ingredients import detect_language, fold, ingredient_words, is_fat, parse_ingredient, token_match
from .rules import validate_and_fix

# ---------------- lexicon (folded = lowercase, no accents) ----------------
A = {
    "off": r"backofen|ofen\b|im ofen|backen|\bbake\b|\bbaking\b(?! soda| powder)|oven|four\b|enfourn|au four|\bgrill(?:en|er|ez)?\b|barbecue|frittier|deep.?fr|"
           r"friture|bain d.huile|huile chaude|hot oil|heissem ol|"
           r"ruhen|rest(?:ing)?\b|repos|marinier|marinate|mariner|kuhlschrank|refrigerat|frigo|refriger|over ?night|uber nacht|"
           r"forme?n\b|shape|faconn|ausroll|roll out|etaler|abaiss|with your hands|by hand|a la main|avec les mains|mit den handen|von hand|"
           r"in eine schussel|in a bowl|dans un saladier|pfanne mit deckel|abkuhlen|cool down|laisser refroidir|refroidir|"
           r"\bfr(y|ies)\b.*(?:until crisp|in batches)|portionsweise|en plusieurs fois|فرن|يقدم|قدم",
    "prep": r"einweich|soak|tremper|schal|peel|eplucher|wasch|wash|laver",
    "serve": r"servier|\bserve|servir|garnier|garnish|decor|anricht|dresser|يقدم|قدم",
    "blend": r"purier|purée|puree|mixen|fein mixen|blend|mixer|mouliner|reduire en puree|veloute|smooth|glatt|اخلط جيدا",
    "knead": r"knet|knead|petri|pétri|عجن|اعجن",
    "whip": r"steif schlag|schlagen.*(sahne|eiweiss|eiwei)|aufschlag|whip|whisk|fouett|monter en neige|chantilly|blancs en neige",
    "steam": r"dampf|dämpf|steam|vapeur|couscoussier|varoma|بخار|كسكاس",
    "syrup": r"sirup|syrup|sirop|karamell|caramel",
    "reduce": r"einkoch|reduzier|\breduce|reduire(?! en puree)|réduire(?! en purée)|eindick|thicken|epaissir",
    "boil": r"aufkoch|zum kochen bringen|bring to (a )?boil|\bboil\b|porter a ebullition|porter à ébullition|ebullition",
    "simmer": r"koch|kochen|koechel|kochel|garen|gar ziehen|stocken|laisser prendre|schmor|simmer|cook|stew|braise|cuire|cuisson|mijot|bouill|"
              r"laisser cuire|طيب|اطبخ|يطيب|اتركه يطيب",
    "saute": r"anbrat|anbraten|andunst|dunst|anschwitz|braten|brown|saute|sauté|\bfry\b|\bfried\b|sear|faire revenir|revenir|"
             r"rissol|dorer|faire suer|suer|اقلي|قلي|حمر",
    "toast": r"anrost|ohne fett rost|toast|torrefi|griller a sec|roast the spices|faire griller",
    "melt": r"schmelz|melt|fondre|ذوب",
    "heat": r"erhitz|erwarm|heat|warm up|chauff|rechauff|سخن",
    "grind": r"mahl|mahlen|grind|moudre|mixer finement en poudre|pulveris|puderzucker|طحن|اطحن",
    "grate": r"reib|raspel|grate|raper|râper|بشر",
    "chop": r"hack|zerklein|zerhack|chop|mince|hacher|emincer|émincer|ciseler|fein schneid|finely|crush|zerstoss|piler|قطع|افرم|فرم",
    "mash": r"zerdruck|zerdrück|mash|ecraser|écraser|هرس",
    "season": r"abschmeck|wurzen|würzen|season|taste and adjust|adjust the seasoning|assaisonn|rectifier|ملح حسب",
    "sprinkle": r"bestreu|daruber streu|darüber streu|streuen|sprinkle|garnish with|parsemer|saupoudrer|رش",
    "fold": r"unterheb|fold in|incorporer delicatement|delicatement",
    "mix": r"verruhr|vermeng|vermisch|untermisch|\bmix\b|combine|stir|melang|mélang|remuer|incorpor|homogen|خلط|اخلط",
    "add": r"zugeb|dazugeb|hinzufug|einfull|add\b|ajout|verser|pour|زيد|اضف|أضف",
}
ACTIONS = {k: re.compile(v) for k, v in A.items()}
MAIN_PRIORITY = ["blend", "knead", "whip", "steam", "syrup", "reduce", "boil", "simmer", "saute", "toast", "melt",
                 "heat", "grind", "grate", "mash", "fold", "mix"]

OBJ = {
    "onion": r"zwiebel|knoblauch|schalott|chili|oignon|\bail\b|echalot|piment|onion|garlic|shallot|بصل|ثوم|فلفل حار",
    "herbs": r"petersil|koriander|minze|dill|schnittlauch|basilik|persil|coriandre|menthe|basilic|parsley|cilantro|mint|basil|fenchel|fenouil|fennel|معدنوس|قصبر|نعناع|بسباس",
    "nuts": r"nuss|nusse|mandel|haselnu|walnu|pistazi|amande|noix|noisette|pistache|almond|\bnuts?\b|walnut|hazelnut|pistachio|لوز|بندق|فستق",
    "bread": r"brot|paniermehl|semmel|pain|bread|chapelure|crumb|خبز",
    "cheese": r"parmesan|kase|käse|gruyere|emmental|fromage|cheese|جبن",
    "veg": r"karott|mohre|möhre|paprika|zucchin|tomat|sellerie|kurbis|kürbis|carott|poivron|courgett|celeri|potiron|citrouille|"
           r"carrot|pepper|tomato|celery|pumpkin|squash|gemuse|légume|legume|vegetable|خضر|طماطم|جزر|قرع",
    "chocolate": r"schokolad|kuvertur|chocolat|chocolate|شكلاط",
    "spices": r"kummel|kümmel|koriandersam|pfefferkorn|gewurz|gewürz|epice|épice|cumin|carvi|coriandre en grain|spice|seeds|graines|تابل|كمون|كروية",
    "sugar": r"zucker|sucre|sugar|سكر",
    "pieces": r"fleisch|hahnchen|hähnchen|huhn|lamm|rind|kalb|merguez|fisch|kichererbs|kartoffel|stuck|stück|wurfel|würfel|"
              r"chicken|lamb|beef|meat|fish|chickpea|potato|chunk|poulet|agneau|viande|poisson|pois chiche|pomme de terre|"
              r"morceau|lentil|linse|lentille|haricot|bohne|bean|لحم|دجاج|حمص|بطاطا|سمك|علوش",
    "meat": r"fleisch|hahnchen|hähnchen|huhn|lamm|rind|kalb|merguez|chicken|lamb|beef|meat|poulet|agneau|viande|لحم|دجاج|علوش",
    "eggs": r"\beier?\b|\begg|\boeufs?\b|œuf|بيض",
    "dough": r"teig|dough|pate\b|pâte|عجين",
}
OBJS = {k: re.compile(v) for k, v in OBJ.items()}
SOFT = re.compile(r"sanft|leicht|bei schwacher|niedriger hitze|doucement|feu doux|low heat|gently|simmer gently|frémi|fremi")

TIME_RE = re.compile(
    r"(\d+(?:[.,]\d+)?|½|¼|¾)\s*(?:(?:-|–|bis|à|a|to|ou|or|oder)\s*(\d+(?:[.,]\d+)?))?\s*"
    r"(stunden?|std\.?|h\b|hours?|hrs?|heures?|ساعة|ساعات|minuten|min\.?|minutes?|mins?|mn|دقيقة|دقائق|sek\.?|sekunden|secondes?|seconds?|sec\.?|s\b)",
    re.I)
TEMP_RE = re.compile(r"\b(3[7-9]|[4-9]\d|1[01]\d|120)\s*(?:°\s*c?\b|grad\b|degrees?\b|degres?\b|°)", re.I)
REST_RX = re.compile(r"ruhen|reposer|repos|\brest\b|let rest|marinier|mariner|marinate|abkuhl|refroidir|cool")
OVEN_TEMP = re.compile(r"\b(1[3-9]\d|2[0-5]\d)\s*°?\s*c\b|\bgas mark|\bthermostat|\bth\.?\s*\d", re.I)

T = {
    "de": {"and": "und", "chop": "{ing} in den Mixtopf geben, {S} zerkleinern und mit dem Spatel nach unten schieben.",
           "chop_dry": "{ing} in den trockenen Mixtopf geben, {S} zerkleinern und umfüllen.",
           "saute": "{ing} zugeben und {S} dünsten.", "saute_none": "{S} dünsten.",
           "saute_meat": "{ing} zugeben und {S} anbraten.", "simmer": "{ing} zugeben und {S} garen.", "simmer_none": "{S} garen.",
           "boil": "{ing} zugeben und {S} aufkochen.", "boil_none": "{S} aufkochen.",
           "reduce": "{S} einkochen lassen, ohne Messbecher, Garkörbchen als Spritzschutz auf den Deckel stellen.",
           "blend": "{ing} zugeben und {S} pürieren, dabei die Stufe langsam von 5 auf 10 erhöhen.",
           "blend_none": "{S} pürieren, dabei die Stufe langsam von 5 auf 10 erhöhen.",
           "mix": "{ing} zugeben und {S} vermischen.", "mix_none": "{S} vermischen.",
           "fold": "{ing} zugeben und {S} unterheben.", "knead": "{ing} zugeben und {S} zu einem Teig verarbeiten.",
           "knead_none": "{S} zu einem Teig verarbeiten.",
           "whip": "Rühraufsatz einsetzen, {ing} in den Mixtopf geben und {S} aufschlagen. Rühraufsatz entfernen.",
           "steam": "{ing} in den Varoma legen, Varoma aufsetzen und {S} garen.",
           "steam_none": "Varoma aufsetzen und {S} garen.",
           "syrup": "{ing} in den Mixtopf geben und {S} kochen, ohne Messbecher.",
           "melt": "{ing} in den Mixtopf geben und {S} schmelzen.", "heat": "{ing} zugeben und {S} erhitzen.",
           "heat_none": "{S} erhitzen.", "grind": "{ing} in den trockenen Mixtopf geben und {S} mahlen.",
           "grate": "{ing} in den Mixtopf geben und {S} reiben.",
           "toast": "{ing} in den Mixtopf geben und {S} anrösten, ohne Messbecher.",
           "add": "{ing} zugeben.", "mash": "{ing} in den Mixtopf geben und {S} zerdrücken.",
           "season": "Mit {ing} abschmecken.", "season_none": "Abschmecken.", "sprinkle": "Zum Servieren mit {ing} bestreuen.",
           "water_steam": "{n} g Wasser in den Mixtopf geben (für den Varoma).",
           "cat": {"soup": "Suppe", "dessert": "Dessert", "starter": "Vorspeise", "basic": "Grundrezept", "bread": "Brot", "main": "Hauptgericht"},
           "w_none": "Schritt {n}: keine Thermomix-Einstellung erkannt – bitte prüfen oder manuell ergänzen.",
           "w_time": "Schritt {n}: Garzeit geschätzt ({t}).", "w_moved": "Trockene Zutaten zuerst zerkleinert (Mixtopf muss trocken sein).",
           "w_rules": "Automatisch mit Regeln umgewandelt (ohne KI) – Einstellungen vor dem Kochen prüfen.",
           "w_lang": "Rezeptsprache {src} beibehalten (Übersetzung: pip install argostranslate).", "min": "Min."},
    "fr": {"and": "et", "chop": "Mettre {ing} dans le bol, mixer {S} et racler les parois avec la spatule.",
           "chop_dry": "Mettre {ing} dans le bol sec, mixer {S} et réserver.",
           "saute": "Ajouter {ing} et faire revenir {S}.", "saute_none": "Faire revenir {S}.",
           "saute_meat": "Ajouter {ing} et faire dorer {S}.", "simmer": "Ajouter {ing} et cuire {S}.", "simmer_none": "Cuire {S}.",
           "boil": "Ajouter {ing} et porter à ébullition {S}.", "boil_none": "Porter à ébullition {S}.",
           "reduce": "Laisser réduire {S}, sans le gobelet doseur, panier de cuisson posé sur le couvercle.",
           "blend": "Ajouter {ing} et mixer {S} en augmentant progressivement de la vitesse 5 à 10.",
           "blend_none": "Mixer {S} en augmentant progressivement de la vitesse 5 à 10.",
           "mix": "Ajouter {ing} et mélanger {S}.", "mix_none": "Mélanger {S}.",
           "fold": "Ajouter {ing} et incorporer {S}.", "knead": "Ajouter {ing} et pétrir {S}.", "knead_none": "Pétrir {S}.",
           "whip": "Insérer le fouet, mettre {ing} dans le bol et fouetter {S}. Retirer le fouet.",
           "steam": "Mettre {ing} dans le Varoma, le mettre en place et cuire {S}.",
           "steam_none": "Mettre le Varoma en place et cuire {S}.",
           "syrup": "Mettre {ing} dans le bol et cuire {S}, sans le gobelet doseur.",
           "melt": "Mettre {ing} dans le bol et faire fondre {S}.", "heat": "Ajouter {ing} et chauffer {S}.",
           "heat_none": "Chauffer {S}.", "grind": "Mettre {ing} dans le bol sec et moudre {S}.",
           "grate": "Mettre {ing} dans le bol et râper {S}.",
           "toast": "Mettre {ing} dans le bol et torréfier {S}, sans le gobelet doseur.",
           "add": "Ajouter {ing}.", "mash": "Mettre {ing} dans le bol et écraser {S}.",
           "season": "Rectifier l'assaisonnement avec {ing}.", "season_none": "Rectifier l'assaisonnement.",
           "sprinkle": "Au moment de servir, parsemer de {ing}.", "water_steam": "Verser {n} g d'eau dans le bol (pour le Varoma).",
           "cat": {"soup": "Soupe", "dessert": "Dessert", "starter": "Entrée", "basic": "Base", "bread": "Pain", "main": "Plat principal"},
           "w_none": "Étape {n} : aucun réglage Thermomix reconnu – à vérifier ou compléter.",
           "w_time": "Étape {n} : temps de cuisson estimé ({t}).", "w_moved": "Ingrédients secs mixés en premier (bol sec).",
           "w_rules": "Converti automatiquement par règles (sans IA) – vérifier les réglages avant de cuisiner.",
           "w_lang": "Langue {src} conservée (traduction : pip install argostranslate).", "min": "min"},
    "en": {"and": "and", "chop": "Place {ing} in the mixing bowl, chop {S} and scrape down with the spatula.",
           "chop_dry": "Place {ing} in the dry mixing bowl, chop {S} and set aside.",
           "saute": "Add {ing} and sauté {S}.", "saute_none": "Sauté {S}.",
           "saute_meat": "Add {ing} and brown {S}.", "simmer": "Add {ing} and cook {S}.", "simmer_none": "Cook {S}.",
           "boil": "Add {ing} and bring to the boil {S}.", "boil_none": "Bring to the boil {S}.",
           "reduce": "Reduce {S} without the measuring cup, simmering basket on the lid as splash guard.",
           "blend": "Add {ing} and blend {S}, increasing gradually from speed 5 to 10.",
           "blend_none": "Blend {S}, increasing gradually from speed 5 to 10.",
           "mix": "Add {ing} and mix {S}.", "mix_none": "Mix {S}.",
           "fold": "Add {ing} and fold in {S}.", "knead": "Add {ing} and knead {S}.", "knead_none": "Knead {S}.",
           "whip": "Insert the butterfly whisk, place {ing} in the bowl and whip {S}. Remove the butterfly.",
           "steam": "Place {ing} in the Varoma, put it in position and steam {S}.",
           "steam_none": "Put the Varoma in position and steam {S}.",
           "syrup": "Place {ing} in the mixing bowl and cook {S} without the measuring cup.",
           "melt": "Place {ing} in the mixing bowl and melt {S}.", "heat": "Add {ing} and heat {S}.",
           "heat_none": "Heat {S}.", "grind": "Place {ing} in the dry mixing bowl and grind {S}.",
           "grate": "Place {ing} in the mixing bowl and grate {S}.",
           "toast": "Place {ing} in the mixing bowl and toast {S} without the measuring cup.",
           "add": "Add {ing}.", "mash": "Place {ing} in the mixing bowl and mash {S}.",
           "season": "Season to taste with {ing}.", "season_none": "Season to taste.",
           "sprinkle": "To serve, sprinkle with {ing}.", "water_steam": "Place {n} g water in the mixing bowl (for the Varoma).",
           "cat": {"soup": "Soup", "dessert": "Dessert", "starter": "Starter", "basic": "Basics", "bread": "Bread", "main": "Main dish"},
           "w_none": "Step {n}: no Thermomix setting recognised – please check or add manually.",
           "w_time": "Step {n}: cooking time estimated ({t}).", "w_moved": "Dry ingredients chopped first (bowl must be dry).",
           "w_rules": "Converted automatically with rules (no AI) – check the settings before cooking.",
           "w_lang": "Kept the recipe language {src} (translation: pip install argostranslate).", "min": "min"},
}
T["ar"] = dict(T["fr"])  # Arabic text stays as written; Thermomix settings are appended


def _split_actions(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?;])\s+|\s*;\s*|,?\s+(?:then|dann|danach|anschließend|anschliessend|puis|ensuite|ثم)\s+", text)
    parts = [p.strip(" ,.") for p in parts if p and len(p.strip(" ,.")) > 2]
    split: list[str] = []
    for p in parts:
        clauses = [c.strip() for c in p.split(",")]
        if len(clauses) > 1 and any(REST_RX.search(fold(c)) for c in clauses[1:]):
            cur: list[str] = []
            for c in clauses:
                if REST_RX.search(fold(c)) and cur:
                    split.append(", ".join(cur))
                    cur = [c]
                else:
                    cur.append(c)
            split.append(", ".join(cur))
        else:
            split.append(p)
    parts = [p for p in split if len(p) > 2]
    merged: list[str] = []
    for p in parts:
        acts = _actions(p)
        if merged and not acts:
            merged[-1] = f"{merged[-1]}, {p}"          # "…, then the walnuts" belongs to the previous action
        elif merged and set(_actions(merged[-1])) <= {"add"} and acts and not set(acts) <= {"add"} \
                and not TIME_RE.search(merged[-1]) and len(p.split()) <= 8:
            merged[-1] = f"{merged[-1]}, {p}"          # "add the tomatoes, then simmer 15 min" -> one step
        else:
            merged.append(p)
    return merged


def _seconds(text: str) -> int | None:
    m = TIME_RE.search(text)
    if not m:
        return None
    a = float(m.group(1).replace(",", ".").replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75"))
    b = float(m.group(2).replace(",", ".")) if m.group(2) else None
    val = max(a, b) if b else a
    unit = fold(m.group(3))
    if unit.startswith(("st", "h", "heure", "ساع")):
        return int(val * 3600)
    if unit.startswith(("se", "sek")) or unit == "s":
        return int(val)
    return int(val * 60)


def _actions(part: str) -> list[str]:
    f = fold(part)
    found = [k for k, rx in ACTIONS.items() if rx.search(f)]
    if "off" in found and ("saute" in found or "simmer" in found) and re.search(r"pfanne|pan\b|poele|poêle|topf|casserole|marmite|cocotte", f) \
            and not re.search(r"frittier|deep|friture|huile chaude|hot oil|heissem ol|ofen|oven|four", f):
        found.remove("off")  # pan/pot cooking -> the Thermomix does it
    if "prep" in found:   # wash / peel / soak: outside the Thermomix unless the phrase also does a Thermomix action
        found.remove("prep")
        if not any(a in found for a in MAIN_PRIORITY + ["chop", "mash"]) and "off" not in found:
            found.append("off")
    return found


def _objects(part: str, ings: list[Ingredient]) -> set[str]:
    text = fold(part) + " " + " ".join(fold(i.name) for i in ings)
    return {k for k, rx in OBJS.items() if rx.search(text)}


def _mentioned(part: str, ingredients: list[Ingredient]) -> list[Ingredient]:
    tokens = re.findall(r"[a-z\u0600-\u06FF]+", fold(part))
    hits: dict[int, set[int]] = {}
    for n, ing in enumerate(ingredients):
        words = ingredient_words(ing)
        idx = {i for i, t in enumerate(tokens) for w in words if token_match(t, w)}
        if idx:
            hits[n] = idx
    # drop an ingredient whose only hits sit inside another ingredient's longer name
    # ("tomate" inside "concentré de tomate", "Tomaten" vs "Tomatenmark")
    out = []
    for n, idx in hits.items():
        name_len = len(ingredient_words(ingredients[n]))
        own = ingredient_words(ingredients[n])
        covered = any(m != n and len(hits[m]) >= 2 and len(ingredient_words(ingredients[m])) > name_len
                      and idx <= hits[m] and max(hits[m]) - min(hits[m]) <= 3
                      and all(tokens[i] in ingredient_words(ingredients[m]) or tokens[i] not in own for i in idx)
                      for m in hits)
        exact = any(tokens[i] in ingredient_words(ingredients[n]) for i in idx)
        rival = any(m != n and idx & hits[m] and any(tokens[i] in ingredient_words(ingredients[m]) for i in idx & hits[m])
                    and not exact for m in hits)
        if not covered and not rival:
            out.append(ingredients[n])
    # "l'eau" matches both "eau" and "eau tiède": keep the one whose words are all in the text
    full = {id(i) for i in out if all(any(token_match(t, w) for t in tokens) for w in ingredient_words(i)[:2])}
    if full:
        out = [i for i in out if id(i) in full or not any(
            j is not i and id(j) in full and hits[ingredients.index(j)] & hits[ingredients.index(i)] for j in out)]
    return out


def _ing_text(ings: list[Ingredient], lang: str) -> str:
    names = [i.name for i in ings]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {T[lang]['and']} " + names[-1]


def _chop_setting(objs: set[str]) -> tuple[TMSetting, bool]:
    """(setting, needs_dry_bowl)"""
    if "herbs" in objs:
        return TMSetting(time_s=3, speed="7"), True
    if "nuts" in objs or "bread" in objs:
        return TMSetting(time_s=10, speed="7"), True
    if "cheese" in objs:
        return TMSetting(time_s=15, speed="10"), True
    if "onion" in objs:
        return TMSetting(time_s=5, speed="5"), False
    if "veg" in objs:
        return TMSetting(time_s=4, speed="4.5"), False
    return TMSetting(time_s=5, speed="5"), False


def _setting(action: str, objs: set[str], secs: int | None, soft: bool) -> tuple[TMSetting, bool]:
    """(setting, time_was_estimated)"""
    pieces = bool(objs & {"pieces", "meat", "eggs"})
    est = secs is None
    if action == "saute":
        t = secs or (300 if "meat" in objs else 180)
        return TMSetting(time_s=min(t, 900), temperature=120, speed="soft" if pieces else "1", reverse=pieces), False
    if action == "simmer":
        t = secs or 1200
        temp = 90 if "eggs_added" in objs or ("eggs" in objs and not ({"meat", "pieces"} & objs)) else (98 if soft else 100)
        return TMSetting(time_s=t, temperature=temp, speed="soft" if pieces else "1", reverse=pieces), est
    if action == "boil":
        return TMSetting(time_s=secs or 360, temperature=100, speed="1", reverse=pieces), False
    if action == "reduce":
        return TMSetting(time_s=secs or 600, temperature="varoma", speed="soft" if pieces else "1", reverse=pieces), est
    if action == "blend":
        return TMSetting(time_s=min(secs or 60, 120), speed="10"), False
    if action == "knead":
        return TMSetting(time_s=min(secs or 120, 300), mode="dough"), False
    if action == "whip":
        return TMSetting(time_s=secs or 240, speed="3.5"), False
    if action == "steam":
        return TMSetting(time_s=secs or 1200, temperature="varoma", speed="soft" if pieces else "1", reverse=pieces), est
    if action == "syrup":
        return TMSetting(time_s=secs or 600, temperature="varoma", speed="1"), est
    if action == "melt":
        temp = 50 if "chocolate" in objs else 60
        return TMSetting(time_s=secs if secs and secs < 900 else 180, temperature=temp, speed="2"), False
    if action == "heat":
        return TMSetting(time_s=secs if secs and secs < 1800 else 300, temperature=90, speed="2" if not pieces else "soft", reverse=pieces), False
    if action == "grind":
        return TMSetting(time_s=secs if secs and secs <= 120 else 30, speed="10"), False
    if action == "grate":
        return (TMSetting(time_s=15, speed="10") if "cheese" in objs else TMSetting(time_s=5, speed="5")), False
    if action == "toast":
        return TMSetting(time_s=secs or 300, temperature=120, speed="1"), False
    if action == "mash":
        return TMSetting(time_s=10, speed="4"), False
    if action == "fold":
        return TMSetting(time_s=15, speed="2", reverse=True), False
    if action == "mix":
        chunky = bool(objs & {"pieces", "meat"})
        return (TMSetting(time_s=20, speed="soft" if chunky else "3", reverse=chunky)), False
    raise ValueError(action)


def _template(key: str, lang: str, ings: list[Ingredient]) -> str:
    t = T[lang]
    text = _ing_text(ings, lang)
    if not text and f"{key}_none" in t:
        return t[f"{key}_none"]
    if not text:
        text = {"de": "Die Zutaten", "fr": "les ingrédients", "en": "the ingredients"}.get(lang, "")
        if key in ("chop", "chop_dry", "grind", "grate", "melt", "syrup", "toast", "whip", "steam"):
            text = {"de": "Zutaten", "fr": "les ingrédients", "en": "the ingredients"}.get(lang, "")
    out = t[key].replace("{ing}", text)
    return out[0].upper() + out[1:]


def convert_step(part: str, ingredients: list[Ingredient], lang: str, used_fat: list[bool],
                 in_bowl: set[int] | None = None, tail: list[Step] | None = None) -> tuple[list[tuple[Step, bool]], list[str]]:
    """One action phrase -> 0..2 (Thermomix step, needs_dry_bowl) (+ warning keys).
    in_bowl: ids of ingredients already added (not listed again); tail: steps for the very end."""
    in_bowl = in_bowl if in_bowl is not None else set()
    tail = tail if tail is not None else []
    acts = _actions(part)
    if "serve" in acts and not ({"chop", "sprinkle"} & set(acts)) and not (set(acts) & set(MAIN_PRIORITY)):
        acts.append("off")           # "serve hot with bread" -> outside the Thermomix
    mentioned = _mentioned(part, ingredients)
    ings = [i for i in mentioned if id(i) not in in_bowl]
    if "sprinkle" in acts and mentioned:
        tail.append(Step(text=_template("sprinkle", lang, mentioned) if lang in T and lang != "ar" else part, off_machine=True))
    season_ings = [i for i in ings if "season" in acts and not (_objects(i.name, [i]) & {"pieces", "meat", "veg"})] \
        if "season" in acts else []
    objs = _objects(part, ings)
    secs = _seconds(part)
    notes: list[str] = []
    if "off" in acts or OVEN_TEMP.search(part):
        return [(Step(text=_cap(part.rstrip(".")) + ".", off_machine=True), False)], notes
    main = next((a for a in MAIN_PRIORITY if a in acts), None)
    steps: list[Step] = []
    dry_flags: list[bool] = []
    use_template = lang in ("de", "fr", "en")

    if "chop" in acts and main not in ("blend", "grind", "grate"):
        chop_ings = [i for i in ings if _objects(i.name, [i]) & {"onion", "herbs", "nuts", "bread", "cheese", "veg"}] or ings
        st, dry = _chop_setting(_objects(" ".join(i.name for i in chop_ings) or part, chop_ings))
        if "sprinkle" in acts:
            dry = True  # chopped for garnish -> do it first in the dry bowl, sprinkle at the end
        text = _template("chop_dry" if dry else "chop", lang, chop_ings) if use_template else part + " {S}"
        steps.append(Step(text=text, setting=st))
        dry_flags.append(dry)
        if not dry:
            for i in chop_ings:
                in_bowl.add(id(i))
        ings = [i for i in ings if i not in chop_ings]

    def finish():
        for st_ in steps:
            pass
        if season_ings or ("season" in acts and main is not None):
            steps.append(Step(text=_template("season", lang, season_ings) if lang in ("de", "fr", "en") else part))
            dry_flags.append(False)
        for i in ings + season_ings + mentioned:
            in_bowl.add(id(i))

    if main is None:
        if season_ings or "season" in acts:
            finish()
            return list(zip(steps, dry_flags)), notes
        if "add" in acts and (ings or mentioned):
            steps.append(Step(text=_template("add", lang, ings or mentioned) if use_template else part))
            dry_flags.append(False)
            finish()
        elif "sprinkle" in acts:
            pass
        elif not steps:
            steps.append(Step(text=_cap(part.rstrip(".")) + "."))
            dry_flags.append(False)
            notes.append("none")
        return list(zip(steps, dry_flags)), notes

    ings = [i for i in ings if i not in season_ings]
    bowl_objs = set().union(*[_objects(i.name, [i]) for i in ingredients if id(i) in in_bowl]) if in_bowl else set()
    if main in ("simmer", "boil", "reduce", "steam", "heat"):
        if any(_objects(i.name, [i]) & {"eggs"} for i in ings):
            objs = objs | {"eggs_added"}   # eggs go in now -> let them set gently at 90 °C
        objs = objs | (bowl_objs & {"pieces", "meat"})
    st, estimated = _setting(main, objs, secs, bool(SOFT.search(fold(part))))
    tm = TEMP_RE.search(part)
    if tm and main in ("heat", "melt", "simmer") and st.temperature not in (None, "varoma"):
        st.temperature = int(tm.group(1))
        if st.temperature < 60:
            st.reverse, st.speed = False, "2"
    if main == "saute" and not used_fat[0]:
        if not any(is_fat(i) for i in ings):
            fats = [i for i in ingredients if is_fat(i) and i not in ings]
            ings = fats[:1] + ings
        used_fat[0] = True
    key = main
    if main == "saute" and "meat" in objs:
        key = "saute_meat"
    if main in ("grind", "grate"):
        ings = ings or [i for i in ingredients if _objects(i.name, [i]) & {"spices", "cheese", "sugar", "veg"}][:3]
    text = _template(key, lang, ings) if use_template else part + " {S}"
    steps.append(Step(text=text, setting=st))
    dry_flags.append(main == "grind")
    if estimated:
        notes.append("time")
    finish()
    return list(zip(steps, dry_flags)), notes


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _yield(text: str) -> int | None:
    m = re.search(r"(\d+)", str(text or ""))
    return int(m.group(1)) if m and 0 < int(m.group(1)) < 60 else None


def _category(title: str, lang: str) -> str:
    f = fold(title)
    c = T.get(lang, T["de"])["cat"]
    if re.search(r"supp|soup|soupe|chorba|shorba|lablabi|velout|brodo|حساء|شربة", f):
        return c["soup"]
    if re.search(r"kuchen|torte|cake|gateau|dessert|makroud|biscuit|keks|cookie|baklaw|bambal|zlabia|creme|mousse|tarte|حلو", f):
        return c["dessert"]
    if re.search(r"salat|salad|salade|slata|mechouia|سلطة", f):
        return c["starter"]
    if re.search(r"harissa|tabil|sauce|sosse|soße|paste|pesto|dressing|gewurz|epice|spice|هريسة|تابل", f):
        return c["basic"]
    if re.search(r"brot|bread|pain|khobz|tabouna|mlawi|chapati|خبز", f):
        return c["bread"]
    return c["main"]


def _maybe_translate(texts: list[str], src: str, dst: str) -> list[str] | None:
    try:
        import argostranslate.translate as tr  # optional, offline, open source
    except Exception:
        return None
    try:
        return [tr.translate(t, src, dst) if t else t for t in texts]
    except Exception:
        return None


def convert_structured(data: dict, language: str | None = None, machine: str = "TM6",
                       servings: int | None = None) -> Recipe:
    """data: {title, ingredients: [str], instructions: [str], yields, total_time, prep_time, url, image, description}"""
    title = (data.get("title") or "Rezept").strip()
    raw_ings = [i for i in (data.get("ingredients") or []) if str(i).strip()]
    raw_steps = [s for s in (data.get("instructions") or []) if str(s).strip()]
    src = detect_language(" ".join([title] + raw_ings + raw_steps))
    lang = src
    warnings: list[str] = []
    if language and language[:2] != src:
        tr = _maybe_translate([title] + raw_ings + raw_steps, src, language[:2])
        if tr:
            title, raw_ings, raw_steps = tr[0], tr[1:1 + len(raw_ings)], tr[1 + len(raw_ings):]
            lang = language[:2]
    if lang not in T:
        lang = "de"
    L = T[lang]
    if language and language[:2] != lang:
        warnings.append(L["w_lang"].format(src=src))

    group = ""
    ingredients: list[Ingredient] = []
    for line in raw_ings:
        line = str(line).strip()
        if line.startswith("## ") or (line.endswith(":") and len(line) < 50):
            group = line.lstrip("# ").rstrip(":")
            continue
        ing = parse_ingredient(line, lang, group)
        if ing:
            ingredients.append(ing)

    pairs: list[tuple[Step, bool]] = []
    notes: list[tuple[int, str]] = []
    used_fat = [False]
    in_bowl: set[int] = set()
    tail: list[Step] = []
    for raw in raw_steps:
        raw = str(raw).strip()
        if raw.startswith("## "):
            continue
        for part in _split_actions(raw):
            new, ns = convert_step(part, ingredients, lang, used_fat, in_bowl, tail)
            pairs += new
            for kind in ns:
                notes.append((id(new[-1][0]), kind))

    # dry-bowl steps (herbs, nuts, spices) must happen before anything wet
    first_wet = next((i for i, (s, d) in enumerate(pairs) if s.setting and not d), len(pairs))
    late_dry = [p for i, p in enumerate(pairs) if p[1] and i > first_wet]
    if late_dry:
        pairs = late_dry + [p for p in pairs if p not in late_dry]
        warnings.append(L["w_moved"])
    steps = [s for s, _ in pairs] + tail

    # steaming needs water in the bowl when nothing else is cooking underneath
    for i, s in enumerate(steps):
        if s.setting and s.setting.temperature == "varoma" and "Varoma" in s.text and \
                not any(p.setting and p.setting.temperature in (98, 100) for p in steps[:i]):
            steps.insert(i, Step(text=L["water_steam"].format(n=500)))
            break

    pos = {id(s): i + 1 for i, s in enumerate(steps)}
    for sid, kind in notes:
        n = pos.get(sid)
        if not n:
            continue
        if kind == "none":
            warnings.append(L["w_none"].format(n=n))
        elif kind == "time":
            t = steps[n - 1].setting.time_s if steps[n - 1].setting else 0
            warnings.append(L["w_time"].format(n=n, t=f"{t // 60} {L['min']}"))
    warnings.insert(0, L["w_rules"])

    cooked = (sum(s.setting.time_s or 0 for s in steps if s.setting)
              + sum(_seconds(s.text) or 0 for s in steps if s.off_machine and not re.search(r"über nacht|overnight|nuit", s.text, re.I))) // 60
    total = data.get("total_time") or max(cooked + 15, 20)
    prep = data.get("prep_time") or min(int(total), 20)
    recipe = Recipe(
        title=title, description=str(data.get("description") or "")[:400], language=lang,
        servings=servings or _yield(data.get("yields")) or 4, prep_time_min=int(prep), total_time_min=int(total),
        machine=machine, category=_category(title, lang), ingredients=ingredients or [Ingredient(name="?")],
        steps=steps or [Step(text="?")], warnings=warnings, source_url=data.get("url", "") or "",
        image_url=data.get("image", "") or "", source_type="rules")
    return validate_and_fix(recipe)
