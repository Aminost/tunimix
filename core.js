// TuniMix core: recipe model, Thermomix rules, setting strings, Cookidoo payload.
// Plain ES module - used by the web app, the GitHub Action and the tests (Node).

export const SPEEDS = ["soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5",
  "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10"];
export const TEMPS = [37, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100, 105, 110, 115, 120];
export const MODES = ["dough", "browning", "turbo", "steaming", "blend", "warm_up", "rice_cooker"];
export const ACCESSORIES = ["Varoma", "SimmeringBasket", "VaromaAndSimmeringBasket"];
export const MACHINES = ["TM5", "TM6", "TM7"];
export const MAX_STEP_S = 99 * 60;
export const BOWL_ML = 2200;

export function slugify(text) {
  return (text || "recipe").normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase() || "recipe";
}

// ---------- normalisation (mirrors toolkit/tunimix/models.py) ----------
function normSpeed(v) {
  if (v === null || v === undefined || v === "") return null;
  let s = String(v).trim().toLowerCase().replace(",", ".");
  if (["sanft", "spoon", "stir", "doux", "mijotage", "soft speed"].includes(s)) s = "soft";
  if (s.endsWith(".0")) s = s.slice(0, -2);
  if (!SPEEDS.includes(s)) throw new Error(`invalid speed ${v}`);
  return s;
}

function normTemp(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "string") {
    const s = v.trim().toLowerCase().replace("°c", "").replace("°", "").trim();
    if (s === "varoma") return "varoma";
    v = parseFloat(s);
    if (Number.isNaN(v)) throw new Error(`invalid temperature`);
  }
  v = Math.round(v);
  if (v > 120) return "varoma";
  if (v < 37) throw new Error(`temperature ${v} below 37°C`);
  return TEMPS.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));
}

export function normSetting(st) {
  if (!st || typeof st !== "object") return null;
  const out = {
    time_s: st.time_s == null || st.time_s === "" ? null : Math.max(0, Math.round(Number(st.time_s))),
    temperature: normTemp(st.temperature),
    speed: normSpeed(st.speed),
    reverse: !!st.reverse,
    mode: MODES.includes(st.mode) ? st.mode : null,
    accessory: ACCESSORIES.includes(st.accessory) ? st.accessory : null,
    browning_power: ["Gentle", "Intense"].includes(st.browning_power) ? st.browning_power : null,
  };
  if (!out.time_s && out.temperature == null && !out.speed && !out.mode) return null;
  return out;
}

const str = (v, d = "") => (v === null || v === undefined ? d : String(v)).trim();

export function normRecipe(r) {
  if (!r || typeof r !== "object") throw new Error("recipe must be an object");
  if (!str(r.title)) throw new Error("title missing");
  const ingredients = (r.ingredients || []).map((i) =>
    typeof i === "string" ? { amount: "", unit: "", name: i, note: "", group: "" } :
      { amount: str(i.amount), unit: str(i.unit), name: str(i.name), note: str(i.note), group: str(i.group) })
    .filter((i) => i.name);
  const steps = (r.steps || []).map((s) => {
    if (typeof s === "string") return { text: s, setting: null, off_machine: false };
    const off = !!s.off_machine;
    return { text: str(s.text), setting: off ? null : normSetting(s.setting), off_machine: off };
  }).filter((s) => s.text);
  if (!ingredients.length) throw new Error("no ingredients");
  if (!steps.length) throw new Error("no steps");
  const prep = Math.max(0, Math.round(Number(r.prep_time_min) || 15));
  const total = Math.max(prep, Math.round(Number(r.total_time_min) || 45));
  return {
    title: str(r.title), original_title: str(r.original_title), description: str(r.description),
    language: str(r.language, "de").slice(0, 2) || "de",
    servings: Math.max(1, Math.round(Number(r.servings) || 4)),
    unit_text: str(r.unit_text, "portion") || "portion",
    prep_time_min: prep, total_time_min: total,
    machine: MACHINES.includes(r.machine) ? r.machine : "TM6",
    category: str(r.category), region: str(r.region), tags: (r.tags || []).map(String).slice(0, 12),
    ingredients, steps,
    hints: (r.hints || []).map(String).filter(Boolean),
    warnings: (r.warnings || []).map(String).filter(Boolean),
    source_url: str(r.source_url), author: str(r.author),
  };
}

// ---------- setting strings ----------
export const L10N = {
  de: { min: "Min.", sec: "Sek.", reverse: "Linkslauf", speed: "Stufe", soft: "Sanftrührstufe",
    modes: { dough: "Teigknetstufe", browning: "Anbraten", turbo: "Turbo", steaming: "Dampfgaren", blend: "Mixen", warm_up: "Aufwärmen", rice_cooker: "Reiskocher" },
    acc: { Varoma: "Varoma", SimmeringBasket: "Garkörbchen", VaromaAndSimmeringBasket: "Varoma + Garkörbchen" },
    cont: "Weitergaren {S}.", ing: "Zutaten", steps: "Zubereitung", hints: "Tipps", serv: "Portionen",
    prep: "Arbeitszeit", total: "Gesamtzeit", off: "außerhalb des Thermomix", src: "Quelle" },
  en: { min: "min", sec: "sec", reverse: "reverse", speed: "speed", soft: "speed soft",
    modes: { dough: "Dough", browning: "Browning", turbo: "Turbo", steaming: "Steaming", blend: "Blend", warm_up: "Warm up", rice_cooker: "Rice cooker" },
    acc: { Varoma: "Varoma", SimmeringBasket: "simmering basket", VaromaAndSimmeringBasket: "Varoma + simmering basket" },
    cont: "Continue cooking {S}.", ing: "Ingredients", steps: "Method", hints: "Tips", serv: "Servings",
    prep: "Active time", total: "Total time", off: "outside the Thermomix", src: "Source" },
  fr: { min: "min", sec: "sec", reverse: "sens inverse", speed: "vitesse", soft: "vitesse mijotage",
    modes: { dough: "Pétrin", browning: "Rissolage", turbo: "Turbo", steaming: "Cuisson vapeur", blend: "Mixage", warm_up: "Réchauffage", rice_cooker: "Cuiseur à riz" },
    acc: { Varoma: "Varoma", SimmeringBasket: "panier cuisson", VaromaAndSimmeringBasket: "Varoma + panier cuisson" },
    cont: "Poursuivre la cuisson {S}.", ing: "Ingrédients", steps: "Préparation", hints: "Astuces", serv: "Portions",
    prep: "Temps actif", total: "Temps total", off: "hors Thermomix", src: "Source" },
  ar: { min: "دقيقة", sec: "ثانية", reverse: "دوران عكسي", speed: "سرعة", soft: "سرعة التحريك الهادئ",
    modes: { dough: "وضع العجن", browning: "التحمير", turbo: "توربو", steaming: "الطهي بالبخار", blend: "خلط", warm_up: "تسخين", rice_cooker: "طهي الأرز" },
    acc: { Varoma: "فاروما", SimmeringBasket: "سلة الطهي", VaromaAndSimmeringBasket: "فاروما + سلة الطهي" },
    cont: "يُواصل الطهي {S}.", ing: "المكونات", steps: "طريقة التحضير", hints: "نصائح", serv: "حصص",
    prep: "وقت التحضير", total: "الوقت الكلي", off: "خارج الثرموميكس", src: "المصدر" },
};
export const lx = (lang) => L10N[(lang || "de").slice(0, 2)] || L10N.de;

export function formatTime(seconds, lang = "de") {
  const t = lx(lang);
  const m = Math.floor(seconds / 60), s = seconds % 60;
  if (m && s) return `${m} ${t.min} ${s} ${t.sec}`;
  return m ? `${m} ${t.min}` : `${s} ${t.sec}`;
}

export function formatSetting(st, lang = "de") {
  if (!st) return "";
  const t = lx(lang), parts = [];
  if (st.mode && !["steaming", "dough"].includes(st.mode))
    parts.push(t.modes[st.mode] + (st.mode === "browning" && st.browning_power ? ` (${st.browning_power})` : ""));
  if (st.time_s) parts.push(formatTime(st.time_s, lang));
  if (st.temperature != null) parts.push(st.temperature === "varoma" ? "Varoma" : `${st.temperature}°C`);
  if (st.reverse) parts.push(t.reverse);
  if (st.mode === "dough" || st.mode === "steaming") parts.push(t.modes[st.mode]);
  if (st.speed) parts.push(st.speed === "soft" ? t.soft : `${t.speed} ${st.speed}`);
  if (st.mode === "steaming" && st.accessory && !(st.accessory === "Varoma" && st.temperature === "varoma"))
    parts.push(t.acc[st.accessory]);
  return parts.join("/");
}

// returns [fullText, settingString]
export function stepText(step, lang = "de") {
  const st = step.off_machine ? null : step.setting;
  const s = formatSetting(st, lang);
  if (!s) return [step.text.replaceAll("{S}", "").replace(/\s{2,}/g, " ").trim(), ""];
  if (step.text.includes("{S}")) return [step.text.replace("{S}", s).replaceAll("{S}", ""), s];
  return [`${step.text.trim().replace(/\.$/, "")} ${s}.`, s];
}

// ---------- rules (mirrors toolkit/tunimix/convert/rules.py) ----------
const PIECES = /fleisch|hähnchen|huhn|lamm|rind|kalb|merguez|fisch|kichererbsen|kartoffel|stück|würfel|chicken|lamb|beef|meat|fish|chickpea|potato|chunk|poulet|agneau|viande|poisson|pois chiche|pomme de terre|morceau|لحم|دجاج|حمص|بطاطا|سمك/i;
const PUREE = /pürier|mix|purée|puree|blend|mixer|zerkleiner|chop|hach|mahl|grind|moudre|اخلط|اطحن/i;
const LIQ = { ml: 1, l: 1000, liter: 1000, cl: 10 };
const WARN = {
  de: { split: "Langer Garvorgang wurde in Schritte ≤ 99 Min. aufgeteilt.", rev: (n) => `Schritt ${n}: Linkslauf ergänzt (Stücke bleiben ganz).`,
    fast: (n, s, t) => `Schritt ${n}: hohe Stufe (${s}) bei ${t} °C – bitte prüfen.`, puree: (n) => `Schritt ${n}: heiß pürieren – Stufe langsam erhöhen.`,
    tm5: (n, m) => `Schritt ${n}: Modus „${m}“ gibt es am TM5 nicht – manuell einstellen.`, liquid: (ml) => `Flüssigkeit ≈ ${ml} ml > 2,2 L Mixtopf – Menge reduzieren.` },
  en: { split: "Long cooking split into steps of max. 99 min.", rev: (n) => `Step ${n}: reverse added (pieces stay whole).`,
    fast: (n, s, t) => `Step ${n}: high speed (${s}) at ${t} °C – please check.`, puree: (n) => `Step ${n}: hot blending – increase speed gradually.`,
    tm5: (n, m) => `Step ${n}: mode "${m}" doesn't exist on TM5 – set manually.`, liquid: (ml) => `Liquid ≈ ${ml} ml > 2.2 L bowl – reduce.` },
  fr: { split: "Cuisson longue découpée en étapes de 99 min max.", rev: (n) => `Étape ${n} : sens inverse ajouté (morceaux entiers).`,
    fast: (n, s, t) => `Étape ${n} : vitesse élevée (${s}) à ${t} °C – à vérifier.`, puree: (n) => `Étape ${n} : mixage à chaud – augmenter progressivement.`,
    tm5: (n, m) => `Étape ${n} : le mode « ${m} » n'existe pas sur TM5.`, liquid: (ml) => `Liquide ≈ ${ml} ml > bol de 2,2 L – réduire.` },
};
WARN.ar = WARN.fr;

export function validateAndFix(input) {
  const r = normRecipe(input);
  const W = WARN[r.language] || WARN.de;
  const t = lx(r.language);
  const out = [];
  for (const s of r.steps) {
    const st = s.setting;
    if (st && st.time_s > MAX_STEP_S) {
      let rest = st.time_s, first = true;
      while (rest > 0) {
        const chunk = Math.min(rest, MAX_STEP_S);
        out.push({ text: first ? s.text : t.cont, setting: { ...st, time_s: chunk }, off_machine: false });
        rest -= chunk; first = false;
      }
      r.warnings.push(W.split);
    } else out.push(s);
  }
  r.steps = out;
  r.steps.forEach((s, i) => {
    const st = s.setting, n = i + 1;
    if (!st) return;
    const hot = st.temperature === "varoma" || (typeof st.temperature === "number" && st.temperature >= 60);
    const spd = st.speed && st.speed !== "soft" ? parseFloat(st.speed) : 0;
    if (hot && spd <= 2 && !st.reverse && !st.mode && PIECES.test(s.text)) { st.reverse = true; r.warnings.push(W.rev(n)); }
    if (hot && spd > 3 && !PUREE.test(s.text)) r.warnings.push(W.fast(n, st.speed, st.temperature));
    if (hot && spd >= 5 && PUREE.test(s.text)) r.warnings.push(W.puree(n));
    if (st.mode === "steaming" && !st.accessory) st.accessory = "Varoma";
    if (st.mode === "turbo") st.temperature = null;
    if (r.machine === "TM5" && ["browning", "rice_cooker", "steaming", "blend", "warm_up"].includes(st.mode)) r.warnings.push(W.tm5(n, st.mode));
  });
  let ml = 0;
  for (const i of r.ingredients) {
    const u = i.unit.toLowerCase().replace(".", "");
    if (LIQ[u]) { const a = parseFloat(i.amount.replace(",", ".").split("-").pop()); if (!Number.isNaN(a)) ml += a * LIQ[u]; }
  }
  if (ml > BOWL_ML) r.warnings.push(W.liquid(Math.round(ml)));
  r.warnings = [...new Set(r.warnings)];
  return r;
}

export const ingredientLine = (i) => [i.amount, i.unit, i.name].filter(Boolean).join(" ") + (i.note ? `, ${i.note}` : "");

// ---------- Cookidoo payload (same format as cookidoo-api's create/patch) ----------
export function cookidooPayload(r) {
  const lines = r.ingredients.map(ingredientLine);
  const instructions = r.steps.map((s) => {
    const [text, slot] = stepText(s, r.language);
    const step = { type: "STEP", text };
    if (slot && s.setting) {
      const st = s.setting;
      const data = {};
      if (st.time_s != null) data.time = st.time_s;
      if (st.temperature != null) data.temperature = st.temperature === "varoma" ? { value: "varoma" } : { value: String(st.temperature), unit: "C" };
      if (st.speed) data.speed = st.speed;
      if (st.reverse) data.direction = "CCW";
      const ann = { type: st.mode ? "MODE" : "TTS", data, position: { offset: text.indexOf(slot), length: slot.length } };
      if (st.mode) {
        ann.name = st.mode;
        if (st.browning_power) data.power = st.browning_power;
        if (st.accessory) data.accessory = st.accessory;
      }
      step.annotations = [ann];
    }
    return step;
  });
  const hints = [...r.hints];
  if (r.source_url) hints.push(`${lx(r.language).src}: ${r.source_url}`);
  return {
    name: r.title.slice(0, 120),
    image: null,
    isImageOwnedByUser: false,
    tools: [r.machine],
    yield: { value: r.servings, unitText: r.unit_text || "portion" },
    prepTime: r.prep_time_min * 60,
    cookTime: (r.total_time_min - r.prep_time_min) * 60,
    totalTime: r.total_time_min * 60,
    ingredients: lines.map((text) => ({ type: "INGREDIENT", text })),
    instructions,
    hints: hints.join("\n"),
    workStatus: "PRIVATE",
    recipeMetadata: { requiresAnnotationsCheck: false },
  };
}

// ---------- text exports ----------
export function servingsLabel(r) {
  return `${r.servings} ${r.unit_text && r.unit_text !== "portion" ? r.unit_text : lx(r.language).serv}`;
}

export function toCopyPaste(r) {
  const t = lx(r.language);
  return [r.title, "", `${servingsLabel(r)} · ${t.prep} ${r.prep_time_min} · ${t.total} ${r.total_time_min} · ${r.machine}`, "",
    t.ing.toUpperCase() + ":", ...r.ingredients.map(ingredientLine), "",
    t.steps.toUpperCase() + ":", ...r.steps.map((s) => stepText(s, r.language)[0]),
    ...(r.hints.length ? ["", t.hints.toUpperCase() + ":", ...r.hints] : []),
    ...(r.source_url ? ["", `${t.src}: ${r.source_url}`] : [])].join("\n");
}

export function toMarkdown(r) {
  const t = lx(r.language);
  let groups = "", last = null;
  for (const i of r.ingredients) {
    if (i.group !== last) { if (i.group) groups += `\n**${i.group}**\n`; last = i.group; }
    groups += `- ${ingredientLine(i)}\n`;
  }
  const steps = r.steps.map((s, n) => {
    const [txt, set] = stepText(s, r.language);
    return `${n + 1}. ${set ? txt.replace(set, `**${set}**`) : txt}${s.off_machine ? ` *(${t.off})*` : ""}`;
  }).join("\n");
  return `# ${r.title}\n${r.original_title ? `*${r.original_title}*\n` : ""}\n${r.description}\n\n` +
    `${servingsLabel(r)} · ${t.prep} ${r.prep_time_min} · ${t.total} ${r.total_time_min} · ${r.machine}\n\n` +
    `## ${t.ing}\n${groups}\n## ${t.steps}\n${steps}\n` +
    (r.hints.length ? `\n## ${t.hints}\n${r.hints.map((h) => `- ${h}`).join("\n")}\n` : "") +
    (r.source_url ? `\n${t.src}: ${r.source_url}\n` : "");
}

// ---------- JSON schema + prompt for the AI ----------
export const RECIPE_SCHEMA = {
  type: "object",
  required: ["title", "servings", "prep_time_min", "total_time_min", "ingredients", "steps"],
  properties: {
    title: { type: "string" },
    original_title: { type: "string", description: "Name in Tounsi/Arabic/French, e.g. 'Ojja Merguez · عجة مرقاز'" },
    description: { type: "string" },
    servings: { type: "integer", minimum: 1 },
    unit_text: { type: "string", description: "'portion' or e.g. 'Stück', 'Glas'" },
    prep_time_min: { type: "integer" },
    total_time_min: { type: "integer" },
    category: { type: "string" },
    tags: { type: "array", items: { type: "string" } },
    ingredients: { type: "array", items: { type: "object", required: ["name"], properties: {
      amount: { type: "string" }, unit: { type: "string" }, name: { type: "string" },
      note: { type: "string" }, group: { type: "string", description: "sub-heading, e.g. 'Für die Soße'" } } } },
    steps: { type: "array", items: { type: "object", required: ["text"], properties: {
      text: { type: "string", description: "Instruction with the literal placeholder {S} where the setting goes" },
      off_machine: { type: "boolean", description: "true for oven/frying/pan/hand steps" },
      setting: { type: "object", properties: {
        time_s: { type: "integer", description: "seconds" },
        temperature: { description: "37-120 or 'varoma'", anyOf: [{ type: "integer" }, { type: "string", enum: ["varoma"] }] },
        speed: { type: "string", enum: SPEEDS },
        reverse: { type: "boolean" },
        mode: { type: "string", enum: MODES },
        accessory: { type: "string", enum: ACCESSORIES } } } } } },
    hints: { type: "array", items: { type: "string" } },
    warnings: { type: "array", items: { type: "string" }, description: "uncertainties, scaled amounts" },
    source_url: { type: "string" },
  },
};

const LANG_NAME = { de: "German", en: "English", fr: "French", ar: "Arabic" };

export function systemPrompt(lang = "de", machine = "TM6") {
  return `You are a Thermomix recipe developer and an expert in home cooking, especially Tunisian and Maghreb cuisine.
You convert recipes (web pages, video transcripts, photos of handwritten family recipes, scans, plain text) into precise Thermomix ${machine} guided-cooking recipes.

OUTPUT LANGUAGE: ${LANG_NAME[lang] || lang} for title, description, ingredients, steps, hints. Keep traditional dish names (put Latin + Arabic script in original_title when known). Special ingredients keep their name with a short explanation (e.g. "Tabil (Tunisian spice mix)").

THERMOMIX FACTS
- Bowl 2.2 L total, max ~800 g meat. Bigger recipes: reduce servings, scale everything, add a warning.
- Temperatures 37-120 °C (37,40,45...95,98,100,105,110,115,120) or "varoma". Speeds "soft", "0.5" ... "10".
- One timer max 99 min (5940 s): split longer cooking into several steps.
- reverse: true whenever pieces must stay whole (meat, chicken, chickpeas, potatoes, vegetable chunks, fish, eggs).
- High speed on hot food only for puréeing soups (increase gradually).
- Deep-frying, oven, grill, pan, shaping by hand: off_machine: true and no setting.
- Weigh into the bowl: g and ml, plus tbsp/tsp/pinch in the output language's usual abbreviations.

PROVEN SETTINGS
onion/garlic chop 3-5 s/speed 5 · herbs 3 s/speed 7 · sauté in oil 3-5 min/120 °C/speed 1 · fry tomato paste+harissa+spices 3 min/120 °C/reverse/speed 1 · meat in sauce 100 °C/reverse/soft 30-60 min · purée 1 min/speed 5-10 gradually · dough: mode "dough" 2-3 min · grind spices 30 s-1 min/speed 10 · sugar syrup 10 min/varoma/speed 1 without measuring cup · eggs in ojja 4 min/90 °C/reverse/soft · couscous: sauce in the bowl, hydrated couscous steamed in the Varoma on a damp cloth 15 min/varoma · soaked chickpeas 60-90 min/100 °C/reverse/soft.

STEPS
- One action per step, imperative, Cookidoo style. Put the literal placeholder {S} where the setting string belongs (the app renders it like "5 Min./100°C/Linkslauf/Stufe 1"). Never write the setting values in the text yourself.
- setting.time_s is in SECONDS.
- Useful hints: serving, storage, variations, TM5 differences. Warnings for anything uncertain.
- Respect the original dish; don't modernise it.`;
}

export function freePrompt(source, opts = {}) {
  const lang = opts.language || "de", machine = opts.machine || "TM6";
  return `${systemPrompt(lang, machine)}

TASK: Convert the recipe below${opts.servings ? ` for ${opts.servings} servings` : ""}${opts.wishes ? ` (wishes: ${opts.wishes})` : ""}.
If it is a link, open it and read the recipe. If it is only a dish name, find an authentic recipe on the web (local/traditional sources first) and put its URL in source_url.

Reply with ONLY one JSON object (in a \`\`\`json code block) that follows this JSON schema:
${JSON.stringify(RECIPE_SCHEMA)}

RECIPE:
${source}`;
}

export function parseAiJson(text) {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  let raw = fenced ? fenced[1] : text;
  const a = raw.indexOf("{"), b = raw.lastIndexOf("}");
  if (a < 0 || b < a) throw new Error("No JSON object found");
  raw = raw.slice(a, b + 1);
  try { return JSON.parse(raw); } catch {
    return JSON.parse(raw.replace(/,\s*([}\]])/g, "$1").replace(/[“”]/g, '"'));
  }
}
