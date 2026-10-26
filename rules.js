// TuniMix rules engine - Thermomix conversion WITHOUT AI.
// Line-by-line port of toolkit/tunimix/convert/{ingredients,rulebased}.py and extract/documents.py
// (structure_text). tests/rules-parity.test.mjs checks that both give identical results.
import { validateAndFix } from "./core.js";

// ---------- helpers that mimic Python semantics ----------
const W = "[\\p{L}\\p{N}_]";
const B = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;        // Python's Unicode \b
const rx = (src, flags = "") => new RegExp(src.replaceAll("\\b", B).replaceAll("\\W", "[^\\p{L}\\p{N}_]"), flags + "u");
export const fold = (t) => String(t).toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replaceAll("ß", "ss");
const strip = (s, chars = " \t\n\r") => { let a = 0, b = s.length; while (a < b && chars.includes(s[a])) a++; while (b > a && chars.includes(s[b - 1])) b--; return s.slice(a, b); };
const lstrip = (s, chars) => { let a = 0; while (a < s.length && chars.includes(s[a])) a++; return s.slice(a); };
const isAlpha = (c) => /\p{L}/u.test(c);
const isDigit = (c) => /\p{Nd}/u.test(c);
function pyRound(x) { const f = Math.floor(x), d = x - f; if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1; return Math.round(x); }

// ======================= ingredients.py =======================
const FRACTIONS = [["½", 0.5], ["¼", 0.25], ["¾", 0.75], ["⅓", 1 / 3], ["⅔", 2 / 3], ["⅛", 0.125]];
const STOP = {
  de: new Set(["und", "der", "die", "das", "mit", "den", "dem", "ein", "eine", "geben", "minuten", "zugeben", "etwas", "oder", "auf", "für", "nach", "bis", "ist", "nicht", "zwiebel", "salz"]),
  fr: new Set(["et", "le", "la", "les", "des", "du", "avec", "dans", "une", "un", "ajouter", "faire", "pour", "sur", "minutes", "puis", "jusqu", "au", "sel", "huile", "oignon"]),
  en: new Set(["and", "the", "with", "add", "of", "to", "into", "until", "for", "minutes", "then", "a", "on", "salt", "oil", "onion", "cup", "cups"]),
};
export function detectLanguage(text) {
  if (!text) return "de";
  const letters = [...text].filter(isAlpha);
  if (letters.length && letters.filter((c) => /[؀-ۿ]/.test(c)).length / letters.length > 0.3) return "ar";
  const words = text.toLowerCase().match(/[a-zA-ZäöüÄÖÜßéèêàâçîïôûù']+/g) || [];
  let best = "de", bestScore = -1, any = false;
  for (const [k, set] of Object.entries(STOP)) {
    const s = words.filter((w) => set.has(w)).length;
    if (s) any = true;
    if (s > bestScore) { best = k; bestScore = s; }
  }
  return any ? best : "de";
}

const UNIT_ALIASES = {
  g: ["g", 1], gr: ["g", 1], gramm: ["g", 1], gramme: ["g", 1], grammes: ["g", 1], grams: ["g", 1], gram: ["g", 1],
  kg: ["g", 1000], kilo: ["g", 1000], kilogramm: ["g", 1000], kilogramme: ["g", 1000], mg: ["g", 0.001],
  ml: ["ml", 1], milliliter: ["ml", 1], millilitre: ["ml", 1], millilitres: ["ml", 1],
  cl: ["ml", 10], dl: ["ml", 100], l: ["ml", 1000], liter: ["ml", 1000], litre: ["ml", 1000], litres: ["ml", 1000], liters: ["ml", 1000],
  oz: ["g", 28.35], ounce: ["g", 28.35], ounces: ["g", 28.35], lb: ["g", 453.6], lbs: ["g", 453.6], pound: ["g", 453.6], pounds: ["g", 453.6],
  cup: ["cup", 1], cups: ["cup", 1], tasse: ["cup", 1], tassen: ["cup", 1], tasses: ["cup", 1],
  verre: ["glass", 1], verres: ["glass", 1], glas: ["glass", 1], glass: ["glass", 1],
  el: ["tbsp", 1], essloffel: ["tbsp", 1], essloeffel: ["tbsp", 1], tbsp: ["tbsp", 1], tbs: ["tbsp", 1], tablespoon: ["tbsp", 1],
  tablespoons: ["tbsp", 1], cas: ["tbsp", 1], "c.a.s.": ["tbsp", 1], "c.a.s": ["tbsp", 1], "c. a s.": ["tbsp", 1], "c. a s": ["tbsp", 1],
  "cuillere a soupe": ["tbsp", 1], "cuilleres a soupe": ["tbsp", 1], "c. a soupe": ["tbsp", 1], cs: ["tbsp", 1],
  tl: ["tsp", 1], teeloffel: ["tsp", 1], teeloeffel: ["tsp", 1], tsp: ["tsp", 1], teaspoon: ["tsp", 1], teaspoons: ["tsp", 1],
  cac: ["tsp", 1], "c.a.c.": ["tsp", 1], "c.a.c": ["tsp", 1], "c. a c.": ["tsp", 1], "c. a c": ["tsp", 1], "cuillere a cafe": ["tsp", 1],
  "cuilleres a cafe": ["tsp", 1], "c. a cafe": ["tsp", 1], cc: ["tsp", 1],
  prise: ["pinch", 1], prisen: ["pinch", 1], pinch: ["pinch", 1], pincee: ["pinch", 1], pincees: ["pinch", 1],
  msp: ["knifetip", 1], messerspitze: ["knifetip", 1],
  bund: ["bunch", 1], bunch: ["bunch", 1], botte: ["bunch", 1], bouquet: ["bunch", 1],
  zehe: ["clove", 1], zehen: ["clove", 1], clove: ["clove", 1], cloves: ["clove", 1], gousse: ["clove", 1], gousses: ["clove", 1],
  dose: ["can", 1], dosen: ["can", 1], can: ["can", 1], cans: ["can", 1], tin: ["can", 1], boite: ["can", 1], boites: ["can", 1],
  pck: ["pack", 1], "pck.": ["pack", 1], packung: ["pack", 1], packchen: ["pack", 1], pack: ["pack", 1], packet: ["pack", 1],
  sachet: ["pack", 1], sachets: ["pack", 1],
  scheibe: ["slice", 1], scheiben: ["slice", 1], slice: ["slice", 1], slices: ["slice", 1], tranche: ["slice", 1], tranches: ["slice", 1],
  handvoll: ["handful", 1], handful: ["handful", 1], poignee: ["handful", 1],
  stuck: ["piece", 1], stk: ["piece", 1], piece: ["piece", 1], pieces: ["piece", 1],
  wurfel: ["cube", 1], cube: ["cube", 1], cubes: ["cube", 1],
};
const ALIASES_BY_LEN = Object.keys(UNIT_ALIASES).sort((a, b) => b.length - a.length);
const UNIT_NAMES = {
  de: { g: "g", ml: "ml", tbsp: "EL", tsp: "TL", pinch: "Prise", knifetip: "Msp.", bunch: "Bund", clove: "Zehe(n)", can: "Dose", pack: "Pck.", slice: "Scheibe(n)", handful: "Handvoll", piece: "Stück", cube: "Würfel" },
  fr: { g: "g", ml: "ml", tbsp: "c. à s.", tsp: "c. à c.", pinch: "pincée", knifetip: "pointe de couteau", bunch: "botte", clove: "gousse(s)", can: "boîte", pack: "sachet", slice: "tranche(s)", handful: "poignée", piece: "pièce(s)", cube: "cube" },
  en: { g: "g", ml: "ml", tbsp: "tbsp", tsp: "tsp", pinch: "pinch", knifetip: "knife tip", bunch: "bunch", clove: "clove(s)", can: "can", pack: "packet", slice: "slice(s)", handful: "handful", piece: "piece(s)", cube: "cube" },
};
UNIT_NAMES.ar = UNIT_NAMES.fr;
const CUP_GRAMS = [["mehl", 120], ["flour", 120], ["farine", 120], ["zucker", 200], ["sugar", 200], ["sucre", 200], ["reis", 185], ["rice", 185], ["riz", 185],
  ["couscous", 180], ["griess", 170], ["semolina", 170], ["semoule", 170], ["butter", 227], ["beurre", 227], ["haferflocken", 90], ["oats", 90],
  ["flocons", 90], ["kakao", 100], ["cocoa", 100], ["cacao", 100], ["puderzucker", 120], ["icing", 120], ["glace", 120], ["nusse", 120],
  ["nuts", 120], ["noix", 120], ["linsen", 190], ["lentils", 190], ["lentilles", 190], ["kichererbsen", 180], ["chickpeas", 180], ["pois chiches", 180]];
const CUP_ML = 240, GLASS_ML = 200;
const AMOUNT = "(?:\\d+\\s+\\d+/\\d+|\\d+/\\d+|\\d+(?:[.,]\\d+)?\\s*[½¼¾⅓⅔⅛]?|[½¼¾⅓⅔⅛])";
const LINE_RE = rx(`^\\s*[-•*·–]?\\s*(?<amount>${AMOUNT}(?:\\s*(?:-|–|bis|à|a|to|or|oder|ou)\\s*${AMOUNT})?)?\\s*(?<rest>.*)$`);
const AMOUNT_G = rx(AMOUNT, "g");

function toNumber(s) {
  s = strip(s).replace(",", ".");
  if (s.includes(" ") && s.includes("/")) {
    const [whole, frac] = s.split(/\s+/); const [a, b] = frac.split("/");
    const v = Number(whole) + Number(a) / Number(b); return Number.isFinite(v) ? v : null;
  }
  if (s.includes("/")) { const [a, b] = s.split("/"); const v = Number(a) / Number(b); return Number.isFinite(v) ? v : null; }
  for (const [f, v] of FRACTIONS) if (s.includes(f)) { const rest = strip(s.replace(f, "")); return (rest ? Number(rest) : 0) + v; }
  const v = Number(s); return s !== "" && Number.isFinite(v) ? v : null;
}
function pyFixed1(x) { return (Math.round(x * 10 + Number.EPSILON * 10) / 10).toFixed(1); }
function fmtNumber(x) {
  if (x >= 10) return x >= 50 ? String(Math.trunc(pyRound(x / 5) * 5)) : String(Math.trunc(pyRound(x)));
  for (const [f, v] of FRACTIONS) {
    if (Math.abs(x - Math.trunc(x) - v) < 0.02 && [0.5, 0.25, 0.75].includes(v)) return Math.trunc(x) ? `${Math.trunc(x)}${f}` : f;
  }
  return x !== Math.trunc(x) ? pyFixed1(x).replace(/0+$/, "").replace(/\.$/, "") : String(Math.trunc(x));
}
function matchUnit(rest) {
  const f = fold(rest);
  for (const alias of ALIASES_BY_LEN) {
    if (f.startsWith(alias) && (f.length === alias.length || !isAlpha(f[alias.length]))) {
      const [key, factor] = UNIT_ALIASES[alias];
      return [key, factor, lstrip(rest.slice(alias.length), " .")];
    }
  }
  return [null, 1, rest];
}

export function parseIngredient(line, lang = "de", group = "") {
  line = strip(strip(String(line).replace(/\s+/g, " ")), "-•*· ");
  if (!line || line.length > 200) return null;
  const m = line.match(LINE_RE);
  const amountTxt = strip(m.groups.amount || "");
  let rest = strip(m.groups.rest);
  let [unitKey, factor, r2] = matchUnit(rest);
  rest = r2.replace(/^(de |d'|d’|of |von )/i, "");
  let note = "";
  const paren = rest.match(/\(([^)]*)\)/);
  if (paren) { note = strip(paren[1]); rest = strip(rest.slice(0, paren.index) + rest.slice(paren.index + paren[0].length)); }
  if (rest.includes(",") && (amountTxt || unitKey)) {
    const k = rest.indexOf(","); const extra = rest.slice(k + 1); rest = rest.slice(0, k);
    note = [note, strip(extra)].filter(Boolean).join(", ");
  }
  const name = strip(rest, " ,;:");
  if (!name) return null;
  let amount = amountTxt, unit = "";
  const values = [...amountTxt.matchAll(AMOUNT_G)].map((x) => toNumber(x[0]));
  const allOk = values.length && values.every((v) => v !== null);
  if ((unitKey === "cup" || unitKey === "glass") && allOk) {
    const per = (CUP_GRAMS.find(([k]) => fold(name).includes(k)) || [])[1];
    if (unitKey === "glass" || per == null) { const ml = unitKey === "cup" ? CUP_ML : GLASS_ML; amount = values.map((v) => fmtNumber(v * ml)).join("-"); unit = "ml"; }
    else { amount = values.map((v) => fmtNumber(v * per)).join("-"); unit = "g"; }
  } else if ((unitKey === "g" || unitKey === "ml") && allOk) {
    amount = values.map((v) => fmtNumber(v * factor)).join("-"); unit = unitKey;
  } else if (unitKey) {
    amount = amountTxt.replaceAll(" ", ""); unit = (UNIT_NAMES[lang] || UNIT_NAMES.de)[unitKey];
  }
  return { amount, unit, name, note, group };
}

const DESCRIPTORS = new Set(["frisch", "frische", "frischer", "fresh", "frais", "fraiche", "gehackt", "gehackte", "chopped", "gros", "grosse", "grand", "grande",
  "klein", "kleine", "small", "large", "big", "rot", "rote", "roter", "red", "rouge", "rouges", "grun", "grune", "green", "vert", "verte", "verts", "getrocknet",
  "getrocknete", "dried", "sec", "seche", "moulu", "moulue", "gemahlen", "gemahlener", "ground", "fein", "feine", "fine", "extra", "natives", "olive", "huile",
  "d", "de", "du", "la", "le", "les", "of", "the", "a", "un", "une"]);
const COMPOUND_HEADS = ["zehen", "zehe", "fleisch", "brust", "schenkel", "pulver", "stangen", "stange", "blatter", "blatt", "wurfel", "scheiben", "filet", "filets"];
const TOKENS = /[a-z؀-ۿ]+/g;
const wordsCache = new WeakMap();
export function ingredientWords(ing) {
  if (wordsCache.has(ing)) return wordsCache.get(ing);
  const words = (fold(ing.name).match(TOKENS) || []).filter((w) => w.length >= 3);
  let keys = words.filter((w) => !DESCRIPTORS.has(w));
  if (!keys.length) keys = words;
  const out = [];
  for (const w of keys.slice(0, 3)) {
    out.push(w);
    for (const h of COMPOUND_HEADS) if (w.endsWith(h) && w.length - h.length >= 3) out.push(w.slice(0, -h.length));
  }
  wordsCache.set(ing, out);
  return out;
}
export function tokenMatch(t, w) {
  if (t === w) return true;
  if (t.length < 3 || w.length < 3) return false;
  let common = 0;
  for (let i = 0; i < Math.min(t.length, w.length) && t[i] === w[i]; i++) common++;
  const short = Math.min(t.length, w.length);
  if (common >= Math.max(3, short - 2) && Math.abs(t.length - w.length) <= 3) return true;
  if (t.length >= 5 && w.endsWith(t) && w.length - t.length >= 3) return true;
  if (w.length >= 4 && t.length - w.length >= 3 && (t.endsWith(w) || (w.length >= 6 && t.startsWith(w)))) return true;
  return false;
}
const OIL_RE = rx("\\b(ol|oel|oil|huile|زيت)\\b|olivenol|sonnenblumenol|rapsol|\\bbutter\\b|\\bbeurre\\b|\\bsmen\\b", "i");
const isFat = (ing) => OIL_RE.test(fold(ing.name));

// ======================= rulebased.py =======================
const A = {
  off: "backofen|ofen\\b|im ofen|backen|\\bbake\\b|\\bbaking\\b(?! soda| powder)|oven|four\\b|enfourn|au four|\\bgrill(?:en|er|ez)?\\b|barbecue|frittier|deep.?fr|" +
    "friture|bain d.huile|huile chaude|hot oil|heissem ol|" +
    "ruhen|rest(?:ing)?\\b|repos|marinier|marinate|mariner|kuhlschrank|refrigerat|frigo|refriger|over ?night|uber nacht|" +
    "forme?n\\b|shape|faconn|ausroll|roll out|etaler|abaiss|with your hands|by hand|a la main|avec les mains|mit den handen|von hand|" +
    "in eine schussel|in a bowl|dans un saladier|pfanne mit deckel|abkuhlen|cool down|laisser refroidir|refroidir|" +
    "\\bfr(y|ies)\\b.*(?:until crisp|in batches)|portionsweise|en plusieurs fois|فرن|يقدم|قدم",
  prep: "einweich|soak|tremper|schal|peel|eplucher|wasch|wash|laver",
  serve: "servier|\\bserve|servir|garnier|garnish|decor|anricht|dresser|يقدم|قدم",
  blend: "purier|purée|puree|mixen|fein mixen|blend|mixer|mouliner|reduire en puree|veloute|smooth|glatt|اخلط جيدا",
  knead: "knet|knead|petri|pétri|عجن|اعجن",
  whip: "steif schlag|schlagen.*(sahne|eiweiss|eiwei)|aufschlag|whip|whisk|fouett|monter en neige|chantilly|blancs en neige",
  steam: "dampf|dämpf|steam|vapeur|couscoussier|varoma|بخار|كسكاس",
  syrup: "sirup|syrup|sirop|karamell|caramel",
  reduce: "einkoch|reduzier|\\breduce|reduire(?! en puree)|réduire(?! en purée)|eindick|thicken|epaissir",
  boil: "aufkoch|zum kochen bringen|bring to (a )?boil|\\bboil\\b|porter a ebullition|porter à ébullition|ebullition",
  simmer: "koch|kochen|koechel|kochel|garen|gar ziehen|stocken|laisser prendre|schmor|simmer|cook|stew|braise|cuire|cuisson|mijot|bouill|laisser cuire|طيب|اطبخ|يطيب|اتركه يطيب",
  saute: "anbrat|anbraten|andunst|dunst|anschwitz|braten|brown|saute|sauté|\\bfry\\b|\\bfried\\b|sear|faire revenir|revenir|rissol|dorer|faire suer|suer|اقلي|قلي|حمر",
  toast: "anrost|ohne fett rost|toast|torrefi|griller a sec|roast the spices|faire griller",
  melt: "schmelz|melt|fondre|ذوب",
  heat: "erhitz|erwarm|heat|warm up|chauff|rechauff|سخن",
  grind: "mahl|mahlen|grind|moudre|mixer finement en poudre|pulveris|puderzucker|طحن|اطحن",
  grate: "reib|raspel|grate|raper|râper|بشر",
  chop: "hack|zerklein|zerhack|chop|mince|hacher|emincer|émincer|ciseler|fein schneid|finely|crush|zerstoss|piler|قطع|افرم|فرم",
  mash: "zerdruck|zerdrück|mash|ecraser|écraser|هرس",
  season: "abschmeck|wurzen|würzen|season|taste and adjust|adjust the seasoning|assaisonn|rectifier|ملح حسب",
  sprinkle: "bestreu|daruber streu|darüber streu|streuen|sprinkle|garnish with|parsemer|saupoudrer|رش",
  fold: "unterheb|fold in|incorporer delicatement|delicatement",
  mix: "verruhr|vermeng|vermisch|untermisch|\\bmix\\b|combine|stir|melang|mélang|remuer|incorpor|homogen|خلط|اخلط",
  add: "zugeb|dazugeb|hinzufug|einfull|add\\b|ajout|verser|pour|زيد|اضف|أضف",
};
const ACTIONS = Object.entries(A).map(([k, v]) => [k, rx(v)]);
const MAIN_PRIORITY = ["blend", "knead", "whip", "steam", "syrup", "reduce", "boil", "simmer", "saute", "toast", "melt", "heat", "grind", "grate", "mash", "fold", "mix"];
const OBJ = {
  onion: "zwiebel|knoblauch|schalott|chili|oignon|\\bail\\b|echalot|piment|onion|garlic|shallot|بصل|ثوم|فلفل حار",
  herbs: "petersil|koriander|minze|dill|schnittlauch|basilik|persil|coriandre|menthe|basilic|parsley|cilantro|mint|basil|fenchel|fenouil|fennel|معدنوس|قصبر|نعناع|بسباس",
  nuts: "nuss|nusse|mandel|haselnu|walnu|pistazi|amande|noix|noisette|pistache|almond|\\bnuts?\\b|walnut|hazelnut|pistachio|لوز|بندق|فستق",
  bread: "brot|paniermehl|semmel|pain|bread|chapelure|crumb|خبز",
  cheese: "parmesan|kase|käse|gruyere|emmental|fromage|cheese|جبن",
  veg: "karott|mohre|möhre|paprika|zucchin|tomat|sellerie|kurbis|kürbis|carott|poivron|courgett|celeri|potiron|citrouille|" +
    "carrot|pepper|tomato|celery|pumpkin|squash|gemuse|légume|legume|vegetable|خضر|طماطم|جزر|قرع",
  chocolate: "schokolad|kuvertur|chocolat|chocolate|شكلاط",
  spices: "kummel|kümmel|koriandersam|pfefferkorn|gewurz|gewürz|epice|épice|cumin|carvi|coriandre en grain|spice|seeds|graines|تابل|كمون|كروية",
  sugar: "zucker|sucre|sugar|سكر",
  pieces: "fleisch|hahnchen|hähnchen|huhn|lamm|rind|kalb|merguez|fisch|kichererbs|kartoffel|stuck|stück|wurfel|würfel|" +
    "chicken|lamb|beef|meat|fish|chickpea|potato|chunk|poulet|agneau|viande|poisson|pois chiche|pomme de terre|" +
    "morceau|lentil|linse|lentille|haricot|bohne|bean|لحم|دجاج|حمص|بطاطا|سمك|علوش",
  meat: "fleisch|hahnchen|hähnchen|huhn|lamm|rind|kalb|merguez|chicken|lamb|beef|meat|poulet|agneau|viande|لحم|دجاج|علوش",
  eggs: "\\beier?\\b|\\begg|\\boeufs?\\b|œuf|بيض",
  dough: "teig|dough|pate\\b|pâte|عجين",
};
const OBJS = Object.entries(OBJ).map(([k, v]) => [k, rx(v)]);
const SOFT = rx("sanft|leicht|bei schwacher|niedriger hitze|doucement|feu doux|low heat|gently|simmer gently|frémi|fremi");
const TIME_RE = rx("(\\d+(?:[.,]\\d+)?|½|¼|¾)\\s*(?:(?:-|–|bis|à|a|to|ou|or|oder)\\s*(\\d+(?:[.,]\\d+)?))?\\s*" +
  "(stunden?|std\\.?|h\\b|hours?|hrs?|heures?|ساعة|ساعات|minuten|min\\.?|minutes?|mins?|mn|دقيقة|دقائق|sek\\.?|sekunden|secondes?|seconds?|sec\\.?|s\\b)", "i");
const TEMP_RE = rx("\\b(3[7-9]|[4-9]\\d|1[01]\\d|120)\\s*(?:°\\s*c?\\b|grad\\b|degrees?\\b|degres?\\b|°)", "i");
const REST_RX = rx("ruhen|reposer|repos|\\brest\\b|let rest|marinier|mariner|marinate|abkuhl|refroidir|cool");
const OVEN_TEMP = rx("\\b(1[3-9]\\d|2[0-5]\\d)\\s*°?\\s*c\\b|\\bgas mark|\\bthermostat|\\bth\\.?\\s*\\d", "i");

const T = {
  de: { and: "und", chop: "{ing} in den Mixtopf geben, {S} zerkleinern und mit dem Spatel nach unten schieben.",
    chop_dry: "{ing} in den trockenen Mixtopf geben, {S} zerkleinern und umfüllen.",
    saute: "{ing} zugeben und {S} dünsten.", saute_none: "{S} dünsten.",
    saute_meat: "{ing} zugeben und {S} anbraten.", simmer: "{ing} zugeben und {S} garen.", simmer_none: "{S} garen.",
    boil: "{ing} zugeben und {S} aufkochen.", boil_none: "{S} aufkochen.",
    reduce: "{S} einkochen lassen, ohne Messbecher, Garkörbchen als Spritzschutz auf den Deckel stellen.",
    blend: "{ing} zugeben und {S} pürieren, dabei die Stufe langsam von 5 auf 10 erhöhen.",
    blend_none: "{S} pürieren, dabei die Stufe langsam von 5 auf 10 erhöhen.",
    mix: "{ing} zugeben und {S} vermischen.", mix_none: "{S} vermischen.",
    fold: "{ing} zugeben und {S} unterheben.", knead: "{ing} zugeben und {S} zu einem Teig verarbeiten.",
    knead_none: "{S} zu einem Teig verarbeiten.",
    whip: "Rühraufsatz einsetzen, {ing} in den Mixtopf geben und {S} aufschlagen. Rühraufsatz entfernen.",
    steam: "{ing} in den Varoma legen, Varoma aufsetzen und {S} garen.", steam_none: "Varoma aufsetzen und {S} garen.",
    syrup: "{ing} in den Mixtopf geben und {S} kochen, ohne Messbecher.",
    melt: "{ing} in den Mixtopf geben und {S} schmelzen.", heat: "{ing} zugeben und {S} erhitzen.",
    heat_none: "{S} erhitzen.", grind: "{ing} in den trockenen Mixtopf geben und {S} mahlen.",
    grate: "{ing} in den Mixtopf geben und {S} reiben.", toast: "{ing} in den Mixtopf geben und {S} anrösten, ohne Messbecher.",
    add: "{ing} zugeben.", mash: "{ing} in den Mixtopf geben und {S} zerdrücken.",
    season: "Mit {ing} abschmecken.", season_none: "Abschmecken.", sprinkle: "Zum Servieren mit {ing} bestreuen.",
    water_steam: "{n} g Wasser in den Mixtopf geben (für den Varoma).",
    cat: { soup: "Suppe", dessert: "Dessert", starter: "Vorspeise", basic: "Grundrezept", bread: "Brot", main: "Hauptgericht" },
    w_none: "Schritt {n}: keine Thermomix-Einstellung erkannt – bitte prüfen oder manuell ergänzen.",
    w_time: "Schritt {n}: Garzeit geschätzt ({t}).", w_moved: "Trockene Zutaten zuerst zerkleinert (Mixtopf muss trocken sein).",
    w_rules: "Automatisch mit Regeln umgewandelt (ohne KI) – Einstellungen vor dem Kochen prüfen.",
    w_lang: "Rezeptsprache {src} beibehalten (Übersetzung: pip install argostranslate).", min: "Min." },
  fr: { and: "et", chop: "Mettre {ing} dans le bol, mixer {S} et racler les parois avec la spatule.",
    chop_dry: "Mettre {ing} dans le bol sec, mixer {S} et réserver.",
    saute: "Ajouter {ing} et faire revenir {S}.", saute_none: "Faire revenir {S}.",
    saute_meat: "Ajouter {ing} et faire dorer {S}.", simmer: "Ajouter {ing} et cuire {S}.", simmer_none: "Cuire {S}.",
    boil: "Ajouter {ing} et porter à ébullition {S}.", boil_none: "Porter à ébullition {S}.",
    reduce: "Laisser réduire {S}, sans le gobelet doseur, panier de cuisson posé sur le couvercle.",
    blend: "Ajouter {ing} et mixer {S} en augmentant progressivement de la vitesse 5 à 10.",
    blend_none: "Mixer {S} en augmentant progressivement de la vitesse 5 à 10.",
    mix: "Ajouter {ing} et mélanger {S}.", mix_none: "Mélanger {S}.",
    fold: "Ajouter {ing} et incorporer {S}.", knead: "Ajouter {ing} et pétrir {S}.", knead_none: "Pétrir {S}.",
    whip: "Insérer le fouet, mettre {ing} dans le bol et fouetter {S}. Retirer le fouet.",
    steam: "Mettre {ing} dans le Varoma, le mettre en place et cuire {S}.", steam_none: "Mettre le Varoma en place et cuire {S}.",
    syrup: "Mettre {ing} dans le bol et cuire {S}, sans le gobelet doseur.",
    melt: "Mettre {ing} dans le bol et faire fondre {S}.", heat: "Ajouter {ing} et chauffer {S}.",
    heat_none: "Chauffer {S}.", grind: "Mettre {ing} dans le bol sec et moudre {S}.",
    grate: "Mettre {ing} dans le bol et râper {S}.", toast: "Mettre {ing} dans le bol et torréfier {S}, sans le gobelet doseur.",
    add: "Ajouter {ing}.", mash: "Mettre {ing} dans le bol et écraser {S}.",
    season: "Rectifier l'assaisonnement avec {ing}.", season_none: "Rectifier l'assaisonnement.",
    sprinkle: "Au moment de servir, parsemer de {ing}.", water_steam: "Verser {n} g d'eau dans le bol (pour le Varoma).",
    cat: { soup: "Soupe", dessert: "Dessert", starter: "Entrée", basic: "Base", bread: "Pain", main: "Plat principal" },
    w_none: "Étape {n} : aucun réglage Thermomix reconnu – à vérifier ou compléter.",
    w_time: "Étape {n} : temps de cuisson estimé ({t}).", w_moved: "Ingrédients secs mixés en premier (bol sec).",
    w_rules: "Converti automatiquement par règles (sans IA) – vérifier les réglages avant de cuisiner.",
    w_lang: "Langue {src} conservée (traduction : pip install argostranslate).", min: "min" },
  en: { and: "and", chop: "Place {ing} in the mixing bowl, chop {S} and scrape down with the spatula.",
    chop_dry: "Place {ing} in the dry mixing bowl, chop {S} and set aside.",
    saute: "Add {ing} and sauté {S}.", saute_none: "Sauté {S}.",
    saute_meat: "Add {ing} and brown {S}.", simmer: "Add {ing} and cook {S}.", simmer_none: "Cook {S}.",
    boil: "Add {ing} and bring to the boil {S}.", boil_none: "Bring to the boil {S}.",
    reduce: "Reduce {S} without the measuring cup, simmering basket on the lid as splash guard.",
    blend: "Add {ing} and blend {S}, increasing gradually from speed 5 to 10.",
    blend_none: "Blend {S}, increasing gradually from speed 5 to 10.",
    mix: "Add {ing} and mix {S}.", mix_none: "Mix {S}.",
    fold: "Add {ing} and fold in {S}.", knead: "Add {ing} and knead {S}.", knead_none: "Knead {S}.",
    whip: "Insert the butterfly whisk, place {ing} in the bowl and whip {S}. Remove the butterfly.",
    steam: "Place {ing} in the Varoma, put it in position and steam {S}.", steam_none: "Put the Varoma in position and steam {S}.",
    syrup: "Place {ing} in the mixing bowl and cook {S} without the measuring cup.",
    melt: "Place {ing} in the mixing bowl and melt {S}.", heat: "Add {ing} and heat {S}.",
    heat_none: "Heat {S}.", grind: "Place {ing} in the dry mixing bowl and grind {S}.",
    grate: "Place {ing} in the mixing bowl and grate {S}.", toast: "Place {ing} in the mixing bowl and toast {S} without the measuring cup.",
    add: "Add {ing}.", mash: "Place {ing} in the mixing bowl and mash {S}.",
    season: "Season to taste with {ing}.", season_none: "Season to taste.",
    sprinkle: "To serve, sprinkle with {ing}.", water_steam: "Place {n} g water in the mixing bowl (for the Varoma).",
    cat: { soup: "Soup", dessert: "Dessert", starter: "Starter", basic: "Basics", bread: "Bread", main: "Main dish" },
    w_none: "Step {n}: no Thermomix setting recognised – please check or add manually.",
    w_time: "Step {n}: cooking time estimated ({t}).", w_moved: "Dry ingredients chopped first (bowl must be dry).",
    w_rules: "Converted automatically with rules (no AI) – check the settings before cooking.",
    w_lang: "Kept the recipe language {src} (translation: pip install argostranslate).", min: "min" },
};
T.ar = { ...T.fr };
const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => (k in o ? o[k] : m));

const actionsOf = (part) => {
  const f = fold(part);
  const found = ACTIONS.filter(([, r]) => r.test(f)).map(([k]) => k);
  if (found.includes("off") && (found.includes("saute") || found.includes("simmer")) && rx("pfanne|pan\\b|poele|poêle|topf|casserole|marmite|cocotte").test(f)
    && !/frittier|deep|friture|huile chaude|hot oil|heissem ol|ofen|oven|four/.test(f)) found.splice(found.indexOf("off"), 1);
  if (found.includes("prep")) {   // wash / peel / soak: outside unless the phrase also does a Thermomix action
    found.splice(found.indexOf("prep"), 1);
    if (!found.some((a) => [...MAIN_PRIORITY, "chop", "mash"].includes(a)) && !found.includes("off")) found.push("off");
  }
  return found;
};
const subset = (a, b) => a.every((x) => b.includes(x));

function splitActions(text) {
  text = strip(text.replace(/\s+/g, " "));
  let parts = text.split(/(?<=[.!?;])\s+|\s*;\s*|,?\s+(?:then|dann|danach|anschließend|anschliessend|puis|ensuite|ثم)\s+/u);
  parts = parts.filter((p) => p && strip(p, " ,.").length > 2).map((p) => strip(p, " ,."));
  const split = [];
  for (const p of parts) {
    const clauses = p.split(",").map((c) => strip(c));
    if (clauses.length > 1 && clauses.slice(1).some((c) => REST_RX.test(fold(c)))) {
      let cur = [];
      for (const c of clauses) {
        if (REST_RX.test(fold(c)) && cur.length) { split.push(cur.join(", ")); cur = [c]; }
        else cur.push(c);
      }
      split.push(cur.join(", "));
    } else split.push(p);
  }
  parts = split.filter((p) => p.length > 2);
  const merged = [];
  for (const p of parts) {
    const acts = actionsOf(p);
    if (merged.length && !acts.length) merged[merged.length - 1] = `${merged.at(-1)}, ${p}`;
    else if (merged.length && subset(actionsOf(merged.at(-1)), ["add"]) && acts.length && !subset(acts, ["add"])
      && !TIME_RE.test(merged.at(-1)) && p.split(/\s+/).filter(Boolean).length <= 8) merged[merged.length - 1] = `${merged.at(-1)}, ${p}`;
    else merged.push(p);
  }
  return merged;
}

function seconds(text) {
  const m = text.match(TIME_RE);
  if (!m) return null;
  const a = parseFloat(m[1].replace(",", ".").replace("½", "0.5").replace("¼", "0.25").replace("¾", "0.75"));
  const b = m[2] ? parseFloat(m[2].replace(",", ".")) : null;
  const val = b ? Math.max(a, b) : a;
  const unit = fold(m[3]);
  if (["st", "h", "heure", "ساع"].some((p) => unit.startsWith(p))) return Math.trunc(val * 3600);
  if (unit.startsWith("se") || unit.startsWith("sek") || unit === "s") return Math.trunc(val);
  return Math.trunc(val * 60);
}

function objectsOf(part, ings) {
  const text = fold(part) + " " + ings.map((i) => fold(i.name)).join(" ");
  return new Set(OBJS.filter(([, r]) => r.test(text)).map(([k]) => k));
}

function mentioned(part, ingredients) {
  const tokens = fold(part).match(TOKENS) || [];
  const hits = new Map();
  ingredients.forEach((ing, n) => {
    const words = ingredientWords(ing);
    const idx = new Set();
    tokens.forEach((t, i) => { if (words.some((w) => tokenMatch(t, w))) idx.add(i); });
    if (idx.size) hits.set(n, idx);
  });
  const isSub = (a, b) => [...a].every((x) => b.has(x));
  const out = [];
  for (const [n, idx] of hits) {
    const nameLen = ingredientWords(ingredients[n]).length;
    const own = ingredientWords(ingredients[n]);
    const covered = [...hits].some(([m, h]) => m !== n && h.size >= 2 && ingredientWords(ingredients[m]).length > nameLen
      && isSub(idx, h) && Math.max(...h) - Math.min(...h) <= 3
      && [...idx].every((i) => ingredientWords(ingredients[m]).includes(tokens[i]) || !own.includes(tokens[i])));
    const exact = [...idx].some((i) => ingredientWords(ingredients[n]).includes(tokens[i]));
    const rival = [...hits].some(([m, h]) => {
      if (m === n) return false;
      const inter = [...idx].filter((i) => h.has(i));
      return inter.length && inter.some((i) => ingredientWords(ingredients[m]).includes(tokens[i])) && !exact;
    });
    if (!covered && !rival) out.push(ingredients[n]);
  }
  const full = new Set(out.filter((i) => ingredientWords(i).slice(0, 2).every((w) => tokens.some((t) => tokenMatch(t, w)))));
  if (full.size) {
    const hitOf = (i) => hits.get(ingredients.indexOf(i));
    return out.filter((i) => full.has(i) || !out.some((j) => j !== i && full.has(j) && [...hitOf(j)].some((x) => hitOf(i).has(x))));
  }
  return out;
}

function ingText(ings, lang) {
  const names = ings.map((i) => i.name);
  if (!names.length) return "";
  if (names.length === 1) return names[0];
  return names.slice(0, -1).join(", ") + ` ${T[lang].and} ` + names.at(-1);
}
const S = (time_s, speed, extra = {}) => ({ time_s, speed, temperature: null, reverse: false, mode: null, accessory: null, ...extra });
function chopSetting(objs) {
  if (objs.has("herbs")) return [S(3, "7"), true];
  if (objs.has("nuts") || objs.has("bread")) return [S(10, "7"), true];
  if (objs.has("cheese")) return [S(15, "10"), true];
  if (objs.has("onion")) return [S(5, "5"), false];
  if (objs.has("veg")) return [S(4, "4.5"), false];
  return [S(5, "5"), false];
}
function settingFor(action, objs, secs, soft) {
  const pieces = ["pieces", "meat", "eggs"].some((k) => objs.has(k));
  const est = secs == null;
  const sp = pieces ? "soft" : "1";
  switch (action) {
    case "saute": return [S(Math.min(secs || (objs.has("meat") ? 300 : 180), 900), sp, { temperature: 120, reverse: pieces }), false];
    case "simmer": {
      const temp = objs.has("eggs_added") || (objs.has("eggs") && !objs.has("meat") && !objs.has("pieces")) ? 90 : (soft ? 98 : 100);
      return [S(secs || 1200, sp, { temperature: temp, reverse: pieces }), est];
    }
    case "boil": return [S(secs || 360, "1", { temperature: 100, reverse: pieces }), false];
    case "reduce": return [S(secs || 600, sp, { temperature: "varoma", reverse: pieces }), est];
    case "blend": return [S(Math.min(secs || 60, 120), "10"), false];
    case "knead": return [S(Math.min(secs || 120, 300), null, { mode: "dough" }), false];
    case "whip": return [S(secs || 240, "3.5"), false];
    case "steam": return [S(secs || 1200, sp, { temperature: "varoma", reverse: pieces }), est];
    case "syrup": return [S(secs || 600, "1", { temperature: "varoma" }), est];
    case "melt": return [S(secs && secs < 900 ? secs : 180, "2", { temperature: objs.has("chocolate") ? 50 : 60 }), false];
    case "heat": return [S(secs && secs < 1800 ? secs : 300, pieces ? "soft" : "2", { temperature: 90, reverse: pieces }), false];
    case "grind": return [S(secs && secs <= 120 ? secs : 30, "10"), false];
    case "grate": return [objs.has("cheese") ? S(15, "10") : S(5, "5"), false];
    case "toast": return [S(secs || 300, "1", { temperature: 120 }), false];
    case "mash": return [S(10, "4"), false];
    case "fold": return [S(15, "2", { reverse: true }), false];
    case "mix": { const chunky = objs.has("pieces") || objs.has("meat"); return [S(20, chunky ? "soft" : "3", { reverse: chunky }), false]; }
    default: throw new Error(action);
  }
}
function template(key, lang, ings) {
  const t = T[lang];
  let text = ingText(ings, lang);
  if (!text && t[`${key}_none`]) return t[`${key}_none`];
  if (!text) {
    text = { de: "Die Zutaten", fr: "les ingrédients", en: "the ingredients" }[lang] || "";
    if (["chop", "chop_dry", "grind", "grate", "melt", "syrup", "toast", "whip", "steam"].includes(key))
      text = { de: "Zutaten", fr: "les ingrédients", en: "the ingredients" }[lang] || "";
  }
  const out = t[key].replace("{ing}", text);
  return out[0].toUpperCase() + out.slice(1);
}
const step = (text, setting = null, off = false) => ({ text, setting, off_machine: off });
const cap = (t) => t.slice(0, 1).toUpperCase() + t.slice(1);

function convertStep(part, ingredients, lang, usedFat, inBowl, tail) {
  const acts = actionsOf(part);
  if (acts.includes("serve") && !acts.some((a) => a === "chop" || a === "sprinkle") && !acts.some((a) => MAIN_PRIORITY.includes(a))) acts.push("off");
  const ment = mentioned(part, ingredients);
  let ings = ment.filter((i) => !inBowl.has(i));
  if (acts.includes("sprinkle") && ment.length)
    tail.push(step(T[lang] && lang !== "ar" ? template("sprinkle", lang, ment) : part, null, true));
  const seasonIngs = acts.includes("season") ? ings.filter((i) => !["pieces", "meat", "veg"].some((k) => objectsOf(i.name, [i]).has(k))) : [];
  let objs = objectsOf(part, ings);
  const secs = seconds(part);
  const notes = [];
  if (acts.includes("off") || OVEN_TEMP.test(part)) return [[[step(cap(part.replace(/\.+$/, "")) + ".", null, true), false]], notes];
  const main = MAIN_PRIORITY.find((a) => acts.includes(a)) || null;
  const steps = [], dry = [];
  const useTemplate = ["de", "fr", "en"].includes(lang);
  if (acts.includes("chop") && !["blend", "grind", "grate"].includes(main)) {
    let chopIngs = ings.filter((i) => ["onion", "herbs", "nuts", "bread", "cheese", "veg"].some((k) => objectsOf(i.name, [i]).has(k)));
    if (!chopIngs.length) chopIngs = ings;
    let [st, isDry] = chopSetting(objectsOf(chopIngs.map((i) => i.name).join(" ") || part, chopIngs));
    if (acts.includes("sprinkle")) isDry = true;
    steps.push(step(useTemplate ? template(isDry ? "chop_dry" : "chop", lang, chopIngs) : part + " {S}", st));
    dry.push(isDry);
    if (!isDry) chopIngs.forEach((i) => inBowl.add(i));
    ings = ings.filter((i) => !chopIngs.includes(i));
  }
  const finish = () => {
    if (seasonIngs.length || (acts.includes("season") && main !== null)) {
      steps.push(step(useTemplate ? template("season", lang, seasonIngs) : part)); dry.push(false);
    }
    [...ings, ...seasonIngs, ...ment].forEach((i) => inBowl.add(i));
  };
  const pairs = () => steps.map((s, i) => [s, dry[i]]);
  if (main === null) {
    if (seasonIngs.length || acts.includes("season")) { finish(); return [pairs(), notes]; }
    if (acts.includes("add") && (ings.length || ment.length)) { steps.push(step(useTemplate ? template("add", lang, ings.length ? ings : ment) : part)); dry.push(false); finish(); }
    else if (acts.includes("sprinkle")) { /* nothing */ }
    else if (!steps.length) { steps.push(step(cap(part.replace(/\.+$/, "")) + ".")); dry.push(false); notes.push("none"); }
    return [pairs(), notes];
  }
  ings = ings.filter((i) => !seasonIngs.includes(i));
  const bowlObjs = new Set();
  ingredients.filter((i) => inBowl.has(i)).forEach((i) => objectsOf(i.name, [i]).forEach((k) => bowlObjs.add(k)));
  if (["simmer", "boil", "reduce", "steam", "heat"].includes(main)) {
    objs = new Set(objs);
    if (ings.some((i) => objectsOf(i.name, [i]).has("eggs"))) objs.add("eggs_added");
    ["pieces", "meat"].forEach((k) => { if (bowlObjs.has(k)) objs.add(k); });
  }
  const [st, estimated] = settingFor(main, objs, secs, SOFT.test(fold(part)));
  const tm = part.match(TEMP_RE);
  if (tm && ["heat", "melt", "simmer"].includes(main) && st.temperature !== null && st.temperature !== "varoma") {
    st.temperature = parseInt(tm[1], 10);
    if (st.temperature < 60) { st.reverse = false; st.speed = "2"; }
  }
  if (main === "saute" && !usedFat[0]) {
    if (!ings.some(isFat)) {
      const fats = ingredients.filter((i) => isFat(i) && !ings.includes(i));
      ings = [...fats.slice(0, 1), ...ings];
    }
    usedFat[0] = true;
  }
  let key = main;
  if (main === "saute" && objs.has("meat")) key = "saute_meat";
  if ((main === "grind" || main === "grate") && !ings.length)
    ings = ingredients.filter((i) => ["spices", "cheese", "sugar", "veg"].some((k) => objectsOf(i.name, [i]).has(k))).slice(0, 3);
  steps.push(step(useTemplate ? template(key, lang, ings) : part + " {S}", st));
  dry.push(main === "grind");
  if (estimated) notes.push("time");
  finish();
  return [pairs(), notes];
}

function yieldOf(text) { const m = String(text || "").match(/(\d+)/); const v = m ? parseInt(m[1], 10) : 0; return v > 0 && v < 60 ? v : null; }
function category(title, lang) {
  const f = fold(title), c = (T[lang] || T.de).cat;
  if (/supp|soup|soupe|chorba|shorba|lablabi|velout|brodo|حساء|شربة/.test(f)) return c.soup;
  if (/kuchen|torte|cake|gateau|dessert|makroud|biscuit|keks|cookie|baklaw|bambal|zlabia|creme|mousse|tarte|حلو/.test(f)) return c.dessert;
  if (/salat|salad|salade|slata|mechouia|سلطة/.test(f)) return c.starter;
  if (/harissa|tabil|sauce|sosse|soße|paste|pesto|dressing|gewurz|epice|spice|هريسة|تابل/.test(f)) return c.basic;
  if (/brot|bread|pain|khobz|tabouna|mlawi|chapati|خبز/.test(f)) return c.bread;
  return c.main;
}

/** data: {title, ingredients:[str], instructions:[str], yields, total_time, prep_time, url, image, description} */
export function convertStructured(data, { language = null, machine = "TM6", servings = null } = {}) {
  const title = strip(data.title || "Rezept");
  const rawIngs = (data.ingredients || []).filter((i) => strip(String(i)));
  const rawSteps = (data.instructions || []).filter((s) => strip(String(s)));
  const src = detectLanguage([title, ...rawIngs, ...rawSteps].join(" "));
  let lang = src;
  const warnings = [];
  if (!T[lang]) lang = "de";
  const L = T[lang];
  if (language && language.slice(0, 2) !== lang) warnings.push(fmt(L.w_lang, { src }));

  let group = "";
  const ingredients = [];
  for (let line of rawIngs) {
    line = strip(String(line));
    if (line.startsWith("## ") || (line.endsWith(":") && line.length < 50)) { group = lstrip(line, "# ").replace(/:+$/, ""); continue; }
    const ing = parseIngredient(line, lang, group);
    if (ing) ingredients.push(ing);
  }
  let pairs = [];
  const notes = [];
  const usedFat = [false], inBowl = new Set(), tail = [];
  for (let raw of rawSteps) {
    raw = strip(String(raw));
    if (raw.startsWith("## ")) continue;
    for (const part of splitActions(raw)) {
      const [nw, ns] = convertStep(part, ingredients, lang, usedFat, inBowl, tail);
      pairs = pairs.concat(nw);
      for (const kind of ns) notes.push([nw.at(-1)[0], kind]);
    }
  }
  const firstWet = (() => { const i = pairs.findIndex(([s, d]) => s.setting && !d); return i < 0 ? pairs.length : i; })();
  const lateDry = pairs.filter((p, i) => p[1] && i > firstWet);
  if (lateDry.length) { pairs = [...lateDry, ...pairs.filter((p) => !lateDry.includes(p))]; warnings.push(L.w_moved); }
  const steps = [...pairs.map(([s]) => s), ...tail];
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (s.setting && s.setting.temperature === "varoma" && s.text.includes("Varoma")
      && !steps.slice(0, i).some((p) => p.setting && [98, 100].includes(p.setting.temperature))) {
      steps.splice(i, 0, step(fmt(L.water_steam, { n: 500 })));
      break;
    }
  }
  const pos = new Map(steps.map((s, i) => [s, i + 1]));
  for (const [s, kind] of notes) {
    const n = pos.get(s);
    if (!n) continue;
    if (kind === "none") warnings.push(fmt(L.w_none, { n }));
    else if (kind === "time") { const t = steps[n - 1].setting ? steps[n - 1].setting.time_s : 0; warnings.push(fmt(L.w_time, { n, t: `${Math.floor(t / 60)} ${L.min}` })); }
  }
  warnings.unshift(L.w_rules);
  const cooked = Math.floor((steps.filter((s) => s.setting).reduce((a, s) => a + (s.setting.time_s || 0), 0)
    + steps.filter((s) => s.off_machine && !/über nacht|overnight|nuit/i.test(s.text)).reduce((a, s) => a + (seconds(s.text) || 0), 0)) / 60);
  const total = data.total_time || Math.max(cooked + 15, 20);
  const prep = data.prep_time || Math.min(Math.trunc(total), 20);
  return validateAndFix({
    title, description: String(data.description || "").slice(0, 400), language: lang,
    servings: servings || yieldOf(data.yields) || 4, prep_time_min: Math.trunc(prep), total_time_min: Math.trunc(total),
    machine, category: category(title, lang), ingredients: ingredients.length ? ingredients : [{ name: "?" }],
    steps: steps.length ? steps : [step("?")], warnings, source_url: data.url || "", image_url: data.image || "",
  });
}

// ======================= documents.py: structure_text =======================
const H_ING = rx("^\\W*(zutaten|ingredients?|ingrédients|ingredientes|المكونات|المقادير|مقادير)\\b.{0,40}$", "i");
const H_STEPS = rx("^\\W*(zubereitung|anleitung|so geht'?s|instructions?|method|methode|directions|preparation|préparation|étapes|etapes|recette|طريقة التحضير|التحضير|الطريقة|طريقة)\\b.{0,30}$", "i");
const H_LEADIN = rx("(you need|you will need|you'll need|what you need|ingredients needed|il vous faut|il faut|" +
  "vous aurez besoin|pour realiser|pour réaliser|ihr braucht|du brauchst|man braucht|wir brauchen|" +
  "benötigt|benotigt|تحتاج|ستحتاج)\\b[^:]{0,40}:\\s*(?<rest>.*)$", "i");
const H_OTHER = rx("^\\W*(tipps?|tips?|notes?|astuces?|conseils?|nährwerte|nutrition|serving|à savoir|نصائح)\\b.{0,30}$", "i");
const H_GROUP = rx("^(für (den|die|das)\\b.{2,40}|pour (la|le|les|l')\\b.{2,40}|for the\\b.{2,40}|.{2,40}:)$", "i");
const NUMBERED = rx("^\\s*(?:\\d{1,2}|[a-z])\\s*[.)\\-:]\\s+|^\\s*(?:schritt|étape|step)\\s*\\d+\\s*[:.)-]?\\s*", "i");
const YIELD = rx("(?:für|pour|serves|for|makes|ergibt|portionen?:?|personnes?:?|servings?:?)\\s*(\\d{1,2})" +
  "(?!\\d|[.,]\\d|\\s*(?:min|std|stunde|h\\b|hour|hrs?\\b|heure|sek|sec|s\\b|°|grad|degr|g\\b|kg|ml|cl|l\\b|cm|mm))\\s*(?:personen|portionen|personnes|people|persons|servings|portions|stück|pieces|parts)?", "i");
const YIELD2 = rx("(\\d{1,2})\\s*(?:personen|portionen|personnes|people|servings|portions|أشخاص|اشخاص)", "i");
const QTY_START = rx(`^\\s*[-•*·–]?\\s*(${AMOUNT})`, "i");
const VERBISH = rx("\\b(geben|zugeben|kochen|garen|rühren|schneiden|hacken|mixen|backen|braten|waschen|lassen|add|cook|stir|mix|" +
  "bake|chop|boil|simmer|wash|put|soak|fry|serve|heat|pour|let|place|ajouter|cuire|mélanger|melanger|" +
  "couper|faire|laisser|mettre|verser|laver|servir)\\b", "i");
const BULLET = /^\s*(?:[-•*·–▪◦]\s*)+/u;
function splitCommas(line) {
  const items = []; let depth = 0, cur = "";
  [...line].forEach((ch, k, arr) => {
    if (ch === "(") depth++;
    if (ch === ")" && depth > 0) depth--;
    const decimal = ch === "," && k > 0 && k < arr.length - 1 && isDigit(arr[k - 1]) && isDigit(arr[k + 1]);
    if ((ch === "," || ch === ";") && depth === 0 && !decimal) { items.push(cur); cur = ""; } else cur += ch;
  });
  items.push(cur);
  return items.filter((i) => strip(i, " .")).map((i) => strip(i, " ."));
}
function isIngredientPara(line) {
  const n = splitCommas(line).length;
  return n >= 3 && !VERBISH.test(line) && !NUMBERED.test(line) && !BULLET.test(line) && line.length / n < 60;
}
const bulleted = (ln) => BULLET.test(ln) || NUMBERED.test(ln);
function cutTrailing(lines) {
  if (lines.filter(bulleted).length < 2) return lines;
  const start = lines.findIndex(bulleted);
  const out = [];
  for (const ln of lines.slice(start)) {
    if (bulleted(ln) || (out.length && !/[.!?:]$/.test(out.at(-1)))) out.push(ln);
    else break;
  }
  return out;
}
export function cleanTitle(title) {
  const parts = String(title || "").split(/\s+[|—–]\s+|\s+-\s+(?=[^-]{2,30}$)/u);
  return parts.length && strip(parts[0]) ? strip(parts[0]) : strip(String(title || ""));
}

function isIngredientLine(line) {
  if (line.length > 90 || (line.endsWith(".") && line.length > 40)) return false;
  if (QTY_START.test(line)) return true;
  const f = fold(line);
  if (/^[-•*·–]\s*\S/u.test(line) && line.length < 60 && !VERBISH.test(line)) return true;
  if (["prise", "pincee", "pinch", "etwas", "un peu", "some", "sel", "salz", "salt"].some((u) => f.startsWith(u + " "))) return true;
  return false;
}
function joinWrapped(lines) {
  const out = [];
  for (const ln of lines) {
    if (out.length && !NUMBERED.test(ln) && !/[.!?:]$/.test(out.at(-1)) && !isDigit(ln.slice(0, 1) || "x")) out[out.length - 1] = `${out.at(-1)} ${ln}`;
    else out.push(ln);
  }
  return out.filter((x) => strip(x)).map((x) => strip(x.replace(NUMBERED, "").replace(BULLET, "")));
}
export function structureText(text, title = "") {
  let lines = String(text).replaceAll("\r", "").split("\n").map((ln) => strip(ln.replace(/\s+/g, " ")));
  lines = lines.filter((ln) => ln && !/^[^\p{L}\p{N}]+$/u.test(ln));
  const data = { title: cleanTitle(title), ingredients: [], instructions: [], yields: "", description: "" };
  for (let i = 0; i < lines.length; i++) {
    const lm = lines[i].match(H_LEADIN);
    if (lm && lines[i].length - lm.groups.rest.length <= 90) {
      lines.splice(i, 1, "Ingredients", ...(strip(lm.groups.rest) ? [lm.groups.rest] : []));
      break;
    }
  }
  const m = text.match(YIELD) || text.match(YIELD2);
  if (m) data.yields = m[1];
  let iIng = lines.findIndex((ln) => H_ING.test(ln)); if (iIng < 0) iIng = null;
  let iStp = lines.findIndex((ln, i) => H_STEPS.test(ln) && (iIng === null || i > iIng)); if (iStp < 0) iStp = null;
  if (!data.title) {
    for (const ln of lines.slice(0, iIng !== null ? iIng : 6)) {
      if (ln.length > 2 && ln.length < 80 && !H_ING.test(ln) && !isIngredientLine(ln) && !YIELD2.test(ln)) { data.title = strip(ln, "#* "); break; }
    }
  }
  let block, stepsBlock;
  if (iIng !== null) {
    const end = iStp !== null ? iStp : lines.length;
    block = lines.slice(iIng + 1, end);
    stepsBlock = iStp !== null ? lines.slice(iStp + 1) : [];
    if (iStp === null) {
      let k = block.findIndex((ln) => !isIngredientLine(ln) && !isIngredientPara(ln) && !H_GROUP.test(ln)
        && (ln.length > 40 || bulleted(ln) || VERBISH.test(ln)));
      if (k < 0) k = block.length;
      stepsBlock = block.slice(k); block = block.slice(0, k);
    }
  } else {
    block = lines.filter((ln) => isIngredientLine(ln) || isIngredientPara(ln));
    stepsBlock = lines.filter((ln) => !isIngredientLine(ln) && !isIngredientPara(ln) && ln !== data.title && (NUMBERED.test(ln) || ln.length > 35));
  }
  for (const ln of block) {
    if (H_OTHER.test(ln)) break;
    const items = splitCommas(ln);
    if (H_GROUP.test(ln) && !QTY_START.test(ln)) data.ingredients.push("## " + ln.replace(/:+$/, ""));
    else if (isIngredientPara(ln) || (items.length >= 3 && ln.length > 60)
      || (items.length >= 2 && !VERBISH.test(ln) && items.slice(1).every((it) => /\d/.test(it)))) data.ingredients.push(...splitCommas(lstrip(ln, "-•*·– ")));
    else data.ingredients.push(strip(lstrip(ln, "-•*·– ")));
  }
  const steps = [];
  for (const ln of stepsBlock) {
    if (H_OTHER.test(ln)) break;
    if (!H_GROUP.test(ln) || ln.length > 40) steps.push(ln);
  }
  data.instructions = joinWrapped(cutTrailing(steps));
  return data;
}

// ======================= schema.org JSON-LD (from the TuniMix button or a fetched page) =======================
function flatten(node) {
  if (typeof node === "string") return node.split(/\n+/).map((s) => strip(s)).filter(Boolean);
  if (Array.isArray(node)) return node.flatMap(flatten);
  if (node && typeof node === "object") {
    if (node["@type"] === "HowToSection") return [...(node.name ? [`## ${node.name}`] : []), ...flatten(node.itemListElement || [])];
    return flatten(node.text || node.name || "");
  }
  return [];
}
const isoMin = (v) => { if (typeof v === "number") return v; const m = String(v || "").match(/P(?:T)?(?:(\d+)H)?(?:(\d+)M)?/); const t = m ? (+m[1] || 0) * 60 + (+m[2] || 0) : 0; return t || null; };
const htmlText = (s) => String(s ?? "").replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, " ").trim();
export function findRecipeNode(data) {
  if (Array.isArray(data)) { for (const d of data) { const f = findRecipeNode(d); if (f) return f; } return null; }
  if (data && typeof data === "object") {
    const t = data["@type"]; if ((Array.isArray(t) ? t : [t]).includes("Recipe")) return data;
    return findRecipeNode(data["@graph"]) || findRecipeNode(data.mainEntity) || null;
  }
  return null;
}
export function fromJsonLd(node, url = "") {
  let img = node.image; if (Array.isArray(img)) img = img[0]; if (img && typeof img === "object") img = img.url;
  let y = node.recipeYield; if (Array.isArray(y)) y = y[0];
  return { title: htmlText(node.name), ingredients: (node.recipeIngredient || node.ingredients || []).map(htmlText),
    instructions: flatten(node.recipeInstructions || []).map(htmlText), yields: y || "", total_time: isoMin(node.totalTime),
    prep_time: isoMin(node.prepTime), description: htmlText(node.description).slice(0, 400), url, image: img || "" };
}
export function fromHtml(html, url = "") {
  const doc = new DOMParser().parseFromString(html, "text/html");
  for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
    try { const n = findRecipeNode(JSON.parse(s.textContent)); if (n) { const d = fromJsonLd(n, url); if (d.ingredients.length && d.instructions.length) return d; } } catch {}
  }
  const og = doc.querySelector('meta[property="og:image"]')?.content || "";
  doc.querySelectorAll("script,style,nav,footer,header,aside,form,iframe,svg,noscript,button").forEach((e) => e.remove());
  const CANDIDATES = [".wprm-recipe-container", ".tasty-recipes", ".mv-create-card", "[itemtype*=Recipe]", ".recipe-card",
    ".PostFull__body", ".entry-content", ".post-content", ".article-content", ".post-body", "article", "main", "[role=main]"];
  let main = null;
  for (const sel of CANDIDATES) {
    const el = doc.querySelector(sel);
    if (el && el.textContent.trim().length > 300) { main = el; break; }
  }
  main = main || doc.body;
  const d = structureText(htmlToText(main), doc.querySelector("h1")?.textContent?.trim() || doc.title || "");
  return { ...d, url, image: og };
}

// DOM -> text with real line breaks (DOMParser documents have no layout, so innerText can't be used)
const BLOCK = new Set(["P", "DIV", "LI", "BR", "H1", "H2", "H3", "H4", "H5", "H6", "TR", "SECTION", "ARTICLE", "UL", "OL",
  "BLOCKQUOTE", "PRE", "TABLE", "DD", "DT", "FIGCAPTION", "HEADER", "FOOTER"]);
export function htmlToText(root) {
  let out = "";
  const walk = (node) => {
    if (node.nodeType === 3) { out += node.nodeValue.replace(/\s+/g, " "); return; }
    if (node.nodeType !== 1) return;
    const tag = node.tagName;
    if (BLOCK.has(tag)) out += "\n";
    if (tag === "LI") out += "- ";
    if (tag === "TD" || tag === "TH") out += " ";
    node.childNodes.forEach(walk);
    if (BLOCK.has(tag)) out += "\n";
  };
  walk(root);
  return out.split("\n").map((l) => l.trim()).filter(Boolean).join("\n");
}
