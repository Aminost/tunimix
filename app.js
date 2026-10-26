import { cookidooPayload, freePrompt, ingredientLine, lx, parseAiJson, servingsLabel, slugify,
  stepText, toCopyPaste, toMarkdown, validateAndFix } from "./core.js";
import { PROVIDERS, convert, isReady, listModels, testConfig } from "./ai.js";
import { convertStructured, findRecipeNode, fromHtml, fromJsonLd, structureText } from "./rules.js";
import { readFile } from "./docs.js";
import { COUNTRIES, UI } from "./i18n.js";

// ---------- storage (everything stays in this browser) ----------
const store = {
  get(k, d) { try { const v = localStorage.getItem("tunimix." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tunimix." + k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem("tunimix." + k); } catch {} },
};
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const APP_URL = new URL("./", location.href).href;
const REPO = (() => {
  const m = location.hostname.match(/^([^.]+)\.github\.io$/);
  const seg = location.pathname.split("/").filter(Boolean)[0];
  return m && seg ? `${m[1]}/${seg}` : "Aminost/tunimix";
})();

let lang = store.get("ui", (navigator.language || "de").slice(0, 2));
if (!UI[lang]) lang = "de";
const t = (k, ...a) => { const v = UI[lang][k] ?? UI.de[k] ?? k; return typeof v === "function" ? v(...a) : v; };

let current = null;          // recipe being viewed
let currentSource = "";      // "mine" | "community"
let files = [];              // [{mime, base64, name}]
let community = [];

// ---------- i18n ----------
function applyI18n() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i]").forEach((el) => { el.textContent = t(el.dataset.i); });
  document.querySelectorAll("[data-iph]").forEach((el) => { el.placeholder = t(el.dataset.iph); });
  $("#uiLang").value = lang;
  renderQueueNote();
  if (current && !$("#v-recipe").hidden) renderRecipe();
  if (!$("#v-recipes").hidden) renderRecipes();
}

// ---------- routing ----------
const VIEWS = ["new", "recipe", "recipes", "button", "settings"];
function show(view, push = true) {
  VIEWS.forEach((v) => { $("#v-" + v).hidden = v !== view; });
  document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === view ? "page" : "false"));
  if (view === "recipes") renderRecipes();
  if (view === "button") renderBookmarklet();
  if (view === "new") refreshKeyUi();
  if (push && location.hash !== "#" + view && view !== "recipe") history.replaceState(null, "", "#" + view);
  window.scrollTo(0, 0);
}
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { el.hidden = true; }, 2600);
}
async function copy(text, okMsg = t("copied")) {
  try { await navigator.clipboard.writeText(text); toast(okMsg); return true; }
  catch {
    const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch {}
    ta.remove(); toast(ok ? okMsg : "⚠"); return ok;
  }
}

// ---------- options ----------
function opts() {
  return {
    language: $("#optLang").value, machine: $("#optMachine").value,
    servings: parseInt($("#optServings").value, 10) || null, wishes: $("#optWish").value.trim(),
    useReader: aiStore().useReader !== false,
  };
}

// ---------- AI provider config (per provider, kept in this browser) ----------
function aiStore() {
  const a = store.get("ai", null);
  if (a) return a;
  const legacy = store.get("key", "");  // migrate the old Claude-only key
  return { provider: legacy ? "anthropic" : "ollama", useReader: true,
    configs: legacy ? { anthropic: { key: legacy, model: "claude-sonnet-5-5" } } : {} };
}
function cfg() {
  const a = aiStore(); const c = a.configs[a.provider] || {};
  return { provider: a.provider, base: c.base || PROVIDERS[a.provider].base, key: c.key || "", model: c.model || "" };
}
function saveCfgFromForm() {
  const a = aiStore(); const p = $("#provider").value;
  a.provider = p;
  a.configs[p] = { base: $("#baseUrl").value.trim(), key: $("#apiKey").value.trim(), model: $("#model").value.trim() };
  a.useReader = $("#useReader").checked;
  store.set("ai", a); refreshKeyUi();
}
function fillSettings() {
  const a = aiStore(), P = PROVIDERS[a.provider], c = a.configs[a.provider] || {};
  const sel = $("#provider");
  if (!sel.options.length) Object.entries(PROVIDERS).forEach(([k, v]) => sel.add(new Option(v.label, k)));
  sel.value = a.provider;
  $("#baseUrl").value = c.base || P.base;
  $("#baseUrl").placeholder = P.base || "https://…/v1";
  $("#apiKey").value = c.key || "";
  $("#keyRow").hidden = !P.key;
  $("#keyLink").hidden = !P.keyUrl; $("#keyLink").href = P.keyUrl || "#"; $("#keyLink").textContent = P.keyUrl ? new URL(P.keyUrl).hostname + " ↗" : "";
  $("#model").value = c.model || ""; $("#model").placeholder = P.hint || "";
  $("#useReader").checked = a.useReader !== false;
  const lh = $("#localHelp");
  lh.hidden = !P.local;
  if (P.local) lh.innerHTML = a.provider === "ollama" ? t("ollama_help", location.origin) : t("lmstudio_help");
  $("#keyStatus").textContent = "";
}
function loadDefaults() {
  const d = store.get("defaults", {});
  $("#optMachine").value = d.machine || "TM6";
  $("#optLang").value = d.language || (["de", "fr", "en", "ar"].includes(lang) ? lang : "de");
  fillSettings();
}
["#optMachine", "#optLang"].forEach((s) => $(s).addEventListener("change", () => {
  store.set("defaults", { machine: $("#optMachine").value, language: $("#optLang").value });
}));

function refreshKeyUi() {
  const c = cfg(), ready = isReady(c);
  $("#withKey").hidden = !ready; $("#noKey").hidden = ready;
  $("#viaNote").textContent = ready ? `${PROVIDERS[c.provider].label.replace(/ \(.*\)$/, "")} · ${c.model}` : "";
}
function aiErrorText(err) {
  const m = err.message;
  const map = { CORS_BLOCKED: "err_cors", LOCAL_UNREACHABLE: "err_local", LINK_NEEDS_READER: "err_link_reader",
    LINK_UNREADABLE: "err_link_unreadable", PDF_NO_TEXT: "err_pdf_no_text", NOT_CONFIGURED: "err_not_configured" };
  return map[m] ? t(map[m], location.origin) : m;
}

// ---------- input ----------
$("#files").addEventListener("change", async (e) => {
  files = await Promise.all([...e.target.files].slice(0, 5).map((f) => new Promise((res, rej) => {
    const rd = new FileReader();
    rd.onload = () => res({ name: f.name, mime: f.type || "image/jpeg", base64: String(rd.result).split(",")[1] });
    rd.onerror = rej; rd.readAsDataURL(f);
  })));
  $("#filesN").textContent = files.length ? t("files_n", files.length) : "";
});

function classify(value) {
  const v = value.trim();
  if (/^https?:\/\/\S+$/i.test(v)) return { url: v };
  if (v && !v.includes("\n") && v.split(/\s+/).length <= 8 && !files.length) return { dish: v };
  return { text: v };
}

function showErr(msg) { const e = $("#convertErr"); e.textContent = msg; e.hidden = !msg; }

$("#btnConvert").addEventListener("click", async () => {
  const value = $("#src").value.trim();
  if (!value && !files.length) return showErr(t("need_input"));
  showErr("");
  const btn = $("#btnConvert"); btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span> ${esc(t("converting"))}`;
  try {
    const input = { ...classify(value), files };
    if (input.text === "" && files.length) delete input.text;
    const r = await convert(cfg(), input, opts(), (s) => { $("#status").textContent = t(s); });
    saveMine(r); openRecipe(r, "mine");
  } catch (err) { showErr(aiErrorText(err)); }
  finally { btn.disabled = false; btn.innerHTML = `<span>${esc(t("convert"))}</span>`; $("#status").textContent = ""; }
});

// ---------- conversion WITHOUT AI (rules.js + docs.js) ----------
async function thumb(src, max = 900) {
  if (!src || !src.startsWith("data:")) return src || "";
  return new Promise((ok) => {
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      ok(c.toDataURL("image/jpeg", 0.8));
    };
    img.onerror = () => ok("");
    img.src = src;
  });
}
async function rulesData(value, status) {
  if (files.length) {
    status(t("reading_file"));
    let text = "", title = "", image = "";
    for (const f of files) {
      const r = await readFile(f, { uiLang: lang, onStatus: (k, p) => status(t(k, p)) });
      text += r.text + "\n"; title ||= r.title || ""; image ||= r.images?.[0] || "";
    }
    return { ...structureText(text, title), image: await thumb(image) };
  }
  if (lastCapture && value.startsWith(`SOURCE: ${lastCapture.url}`)) {
    if (lastCapture.data) return { ...lastCapture.data, image: lastCapture.data.image || lastCapture.image };
    return { ...structureText(value.split("\n").slice(1).join("\n")), url: lastCapture.url, image: lastCapture.image };
  }
  const kind = classify(value);
  if (kind.url) {
    if (aiStore().useReader === false) throw new Error(t("err_rules_link"));
    status(t("reading"));
    const res = await fetch("https://r.jina.ai/" + kind.url, { headers: { "X-Return-Format": "html" } }).catch(() => null);
    if (!res || !res.ok) throw new Error(t("err_link_unreadable"));
    return fromHtml(await res.text(), kind.url);
  }
  if (kind.dish) throw new Error(t("err_rules_dish"));
  return structureText(value);
}
$("#btnRules").addEventListener("click", async () => {
  const value = $("#src").value.trim();
  if (!value && !files.length) return showErr(t("need_input"));
  showErr("");
  const btn = $("#btnRules"); btn.disabled = true;
  const status = (m) => { $("#status").textContent = m; };
  btn.innerHTML = `<span class="spin"></span> ${esc(t("converting"))}`;
  try {
    const data = await rulesData(value, status);
    if (!data.ingredients?.length || !data.instructions?.length) throw new Error(t("err_rules_empty"));
    const o = opts();
    const r = convertStructured(data, { machine: o.machine, servings: o.servings });  // no translation without AI: keeps the source language
    r.image_url = data.image || "";
    saveMine(r); openRecipe(r, "mine");
  } catch (err) { showErr(err.message); }
  finally { btn.disabled = false; btn.innerHTML = `<span>${esc(t("convert_rules"))}</span>`; status(""); }
});

$("#btnCopyPrompt").addEventListener("click", async () => {
  const value = $("#src").value.trim();
  if (!value && !files.length) return showErr(t("need_input"));
  showErr("");
  const src = value || "(The recipe is in the photo/PDF I attached.)";
  if (await copy(freePrompt(src, opts()), t("free_1b"))) $("#btnCopyPrompt").textContent = t("free_1b");
});

$("#btnUseAnswer").addEventListener("click", () => {
  try {
    const o = opts();
    const data = parseAiJson($("#aiAnswer").value);
    const v = $("#src").value.trim();
    const r = validateAndFix({ ...data, language: o.language, machine: o.machine,
      source_url: data.source_url || (/^https?:\/\//.test(v) ? v : "") });
    saveMine(r); $("#aiAnswer").value = ""; openRecipe(r, "mine");
  } catch (err) { showErr(`${t("invalid")}: ${err.message}`); }
});
$("#btnGoKey").addEventListener("click", () => { show("settings"); $("#provider").focus(); });
$("#howBm").addEventListener("click", (e) => { e.preventDefault(); show("button"); });

// ---------- capture from the bookmarklet / share target ----------
function jsonldToText(j) {
  const flat = (n) => typeof n === "string" ? [n] : Array.isArray(n) ? n.flatMap(flat) :
    n && typeof n === "object" ? (n.itemListElement ? [n.name ? `## ${n.name}` : "", ...flat(n.itemListElement)] : flat(n.text || n.name || "")) : [];
  const y = Array.isArray(j.recipeYield) ? j.recipeYield[0] : j.recipeYield;
  return [j.name && `TITLE: ${j.name}`, y && `YIELD: ${y}`, j.totalTime && `TOTAL TIME: ${j.totalTime}`,
    "INGREDIENTS:", ...(j.recipeIngredient || []).map((i) => `- ${i}`),
    "INSTRUCTIONS:", ...flat(j.recipeInstructions || []).filter(Boolean)].filter(Boolean).join("\n");
}
window.addEventListener("message", (ev) => {
  const d = ev.data;
  if (!d || d.type !== "tunimix-capture" || typeof d.url !== "string") return;
  try { ev.source?.postMessage({ type: "tunimix-capture-ack" }, ev.origin); } catch {}
  if (capture._got === d.url) return;
  capture._got = d.url;
  capture(d);
});
let lastCapture = null;   // {url, data} from the TuniMix button (schema.org data or page text)
function capture(d) {
  lastCapture = { url: d.url, image: d.image || "" };
  try {
    const node = d.jsonld ? findRecipeNode(JSON.parse(d.jsonld)) : null;
    lastCapture.data = node ? fromJsonLd(node, d.url) : null;
  } catch { lastCapture.data = null; }
  let text = "";
  if (d.jsonld) { try { text = jsonldToText(JSON.parse(d.jsonld)); } catch { text = d.jsonld; } }
  else text = [d.title, d.description, String(d.text || "").slice(0, 30000)].filter(Boolean).join("\n\n");
  $("#src").value = `SOURCE: ${d.url}\n${text}`.slice(0, 50000);
  const host = (() => { try { return new URL(d.url).hostname; } catch { return "?"; } })();
  const n = $("#capturedNote"); n.textContent = t("captured", host); n.hidden = false;
  show("new");
}
function readShareTarget() {
  const p = new URLSearchParams(location.search);
  const shared = [p.get("url"), p.get("text"), p.get("title")].filter(Boolean);
  if (!shared.length) return;
  const url = shared.find((s) => /^https?:\/\//.test(s)) || (shared.join(" ").match(/https?:\/\/\S+/) || [])[0];
  $("#src").value = url || shared.join("\n");
  history.replaceState(null, "", location.pathname + "#new");
}

// ---------- my recipes ----------
function mine() { return store.get("mine", []); }
function saveMine(r) {
  r.id = r.id || `${slugify(r.title)}-${Date.now().toString(36)}`;
  const list = mine().filter((x) => x.id !== r.id);
  list.unshift(r);
  try { localStorage.setItem("tunimix.mine", JSON.stringify(list)); }
  catch {  // storage full: keep photos only for the newest recipes
    list.forEach((x, i) => { if (i > 5 && String(x.image_url).startsWith("data:")) x.image_url = ""; });
    store.set("mine", list);
  }
}

// ---------- recipe view ----------
function openRecipe(r, source) {
  current = r; currentSource = source;
  show("recipe", false);
  history.replaceState(null, "", source === "community" ? `#c-${r.slug || slugify(r.title)}` : `#r-${r.id}`);
  renderRecipe();
}
$("#btnBack").addEventListener("click", () => show(currentSource === "community" || currentSource === "mine-list" ? "recipes" : "recipes"));

function stepHtml(s, rl) {
  const [txt, set] = stepText(s, rl);
  let h = esc(txt);
  if (set) h = h.replace(esc(set), `<span class="chip">${esc(set)}</span>`);
  return `<li>${h}${s.off_machine ? ` <span class="offm">· ${esc(lx(rl).off)}</span>` : ""}</li>`;
}
function renderRecipe() {
  const r = current; if (!r) return;
  const L = lx(r.language);
  let ing = "", last = null;
  r.ingredients.forEach((i) => {
    if (i.group !== last) { ing += (last !== null ? "</ul>" : "") + (i.group ? `<div class="grp">${esc(i.group)}</div>` : "") + "<ul>"; last = i.group; }
    ing += `<li>${esc(ingredientLine(i))}</li>`;
  });
  ing += "</ul>";
  const isMine = currentSource === "mine";
  $("#recipeView").innerHTML = `
    ${/^(https:|data:image\/)/.test(r.image_url || "") ? `<img src="${esc(r.image_url)}" alt="" style="width:100%;max-height:320px;object-fit:cover;border-radius:12px;margin-bottom:12px" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
    ${r.category ? `<div class="eyebrow">${esc(r.category)}</div>` : ""}
    <h2>${esc(r.title)}</h2>
    ${r.original_title ? `<div class="muted">${esc(r.original_title)}</div>` : ""}
    ${r.description ? `<p>${esc(r.description)}</p>` : ""}
    <div class="meta">${esc(servingsLabel(r))} · ${esc(L.prep)} ${r.prep_time_min} · ${esc(L.total)} ${r.total_time_min} · ${esc(r.machine)}${r.author ? ` · ${esc(t("by"))} ${esc(r.author)}` : ""}${r.source_url ? ` · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(t("source"))}</a>` : ""}</div>
    <div class="btns" style="margin-top:16px">
      <button class="btn p" data-a="cookidoo">${esc(t("save_cookidoo"))}</button>
      <button class="btn" data-a="code">${esc(t("copy_code"))}</button>
      <button class="btn" data-a="text">${esc(t("copy_text"))}</button>
      ${isMine ? `<button class="btn" data-a="share">${esc(t("share"))}</button>` : ""}
    </div>
    <h3>${esc(L.ing)}</h3>${ing}
    <h3>${esc(L.steps)}</h3><ol class="steps">${r.steps.map((s) => stepHtml(s, r.language)).join("")}</ol>
    ${r.hints?.length ? `<h3>${esc(L.hints)}</h3><ul>${r.hints.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>` : ""}
    ${r.warnings?.length ? `<div class="warn" style="margin-top:18px"><b>${esc(t("check"))}:</b> ${r.warnings.map(esc).join(" · ")}</div>` : ""}
    <div class="btns" style="margin-top:18px">
      <button class="btn" data-a="json">${esc(t("download"))}</button>
      <button class="btn" data-a="md">Markdown</button>
      ${isMine ? `<button class="btn" data-a="edit">${esc(t("edit"))}</button><button class="btn d" data-a="del">${esc(t("del"))}</button>` : ""}
    </div>`;
  $("#recipeView").querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => ACTIONS[b.dataset.a]()));
}

function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
function dialog(html, bind) {
  $("#dlgIn").innerHTML = html;
  bind?.($("#dlgIn"));
  $("#dlg").showModal();
}
$("#dlg").addEventListener("click", (e) => { if (e.target.id === "dlg") $("#dlg").close(); });

function countrySite() {
  const loc = store.get("country", "de-DE");
  const c = COUNTRIES.find((x) => x[0] === loc) || COUNTRIES[0];
  return `https://${c[1]}/foundation/${c[0]}`;
}
const ACTIONS = {
  cookidoo() {
    const q = store.get("queue", []).filter((x) => x.id !== (current.id || current.slug));
    q.push({ id: current.id || current.slug || slugify(current.title), title: current.title, payload: cookidooPayload(current) });
    store.set("queue", q); renderQueueNote();
    dialog(`<h3>${esc(t("queued_title"))}</h3>
      <ol class="steps-list"><li>${esc(t("queued_1"))}<div style="margin-top:6px"><a class="btn p" href="${esc(countrySite())}" target="_blank" rel="noopener">${esc(t("queued_open"))} ↗</a></div></li>
      <li>${esc(t("queued_2"))}</li></ol>
      <a href="#button" data-x="bm">${esc(t("queued_nobm"))}</a>
      <div class="btns"><button class="btn" data-x="close">OK</button></div>`,
      (el) => {
        el.querySelector('[data-x="close"]').onclick = () => $("#dlg").close();
        el.querySelector('[data-x="bm"]').onclick = (e) => { e.preventDefault(); $("#dlg").close(); show("button"); };
      });
  },
  code() { copy(JSON.stringify([{ payload: cookidooPayload(current) }])); },
  text() { copy(toCopyPaste(current)); },
  json() { download(`${slugify(current.title)}.json`, JSON.stringify(current, null, 2), "application/json"); },
  md() { download(`${slugify(current.title)}.md`, toMarkdown(current), "text/markdown"); },
  share() {
    const clean = { ...current }; delete clean.id; delete clean.warnings;
    const json = JSON.stringify(clean, null, 2);
    const base = `https://github.com/${REPO}/issues/new?template=rezept.yml&title=${encodeURIComponent("Rezept: " + current.title)}`;
    const full = `${base}&recipe_json=${encodeURIComponent(json)}`;
    dialog(`<h3>${esc(t("share_title"))}</h3><p>${esc(t("share_body"))}</p>
      <div class="btns"><button class="btn p" data-x="go">${esc(t("share_go"))} ↗</button><button class="btn" data-x="close">${esc(t("no"))}</button></div>`,
      (el) => {
        el.querySelector('[data-x="close"]').onclick = () => $("#dlg").close();
        el.querySelector('[data-x="go"]').onclick = async () => {
          if (full.length > 7500) { await copy(json); toast(t("share_long")); window.open(base, "_blank", "noopener"); }
          else window.open(full, "_blank", "noopener");
          $("#dlg").close();
        };
      });
  },
  edit() {
    dialog(`<h3>${esc(t("edit"))}</h3><p class="muted small">${esc(t("edit_help"))}</p>
      <textarea id="editJson" style="min-height:50vh;font:13px ui-monospace,monospace" aria-label="JSON"></textarea><div id="editErr" class="err" hidden></div>
      <div class="btns"><button class="btn p" data-x="save">${esc(t("saved").replace(" ✓", ""))}</button><button class="btn" data-x="close">${esc(t("no"))}</button></div>`,
      (el) => {
        el.querySelector("#editJson").value = JSON.stringify(current, null, 2);
        el.querySelector('[data-x="close"]').onclick = () => $("#dlg").close();
        el.querySelector('[data-x="save"]').onclick = () => {
          try {
            const r = validateAndFix(JSON.parse(el.querySelector("#editJson").value));
            r.id = current.id; saveMine(r); current = r; $("#dlg").close(); renderRecipe(); toast(t("saved"));
          } catch (err) { const e = el.querySelector("#editErr"); e.textContent = `${t("invalid")}: ${err.message}`; e.hidden = false; }
        };
      });
  },
  del() {
    dialog(`<h3>${esc(t("confirm_del"))}</h3><div class="btns"><button class="btn d" data-x="yes">${esc(t("yes"))}</button><button class="btn" data-x="no">${esc(t("no"))}</button></div>`,
      (el) => {
        el.querySelector('[data-x="no"]').onclick = () => $("#dlg").close();
        el.querySelector('[data-x="yes"]').onclick = () => {
          store.set("mine", mine().filter((x) => x.id !== current.id)); $("#dlg").close(); current = null; show("recipes");
        };
      });
  },
};

function renderQueueNote() {
  const n = store.get("queue", []).length;
  const el = $("#queueNote");
  el.hidden = !n;
  if (n) el.innerHTML = `${esc(t("queued_n", n))} <a href="${esc(countrySite())}" target="_blank" rel="noopener">${esc(t("queued_open"))} ↗</a>`;
}
window.addEventListener("storage", (e) => { if (e.key === "tunimix.queue") renderQueueNote(); });
window.addEventListener("focus", renderQueueNote);

// ---------- recipe lists ----------
let cat = "";
function card(r, src) {
  const b = document.createElement("button");
  b.className = "rc";
  b.innerHTML = `${r.category ? `<span class="eyebrow">${esc(r.category)}</span>` : ""}<span class="t">${esc(r.title)}</span>
    ${r.original_title ? `<span class="o">${esc(r.original_title)}</span>` : ""}
    <span class="meta">${esc(servingsLabel(r))} · ${r.total_time_min} min · ${esc(r.machine)}</span>`;
  b.addEventListener("click", () => openRecipe(r, src));
  return b;
}
const match = (r, q) => !q || [r.title, r.original_title, r.category, ...(r.tags || []), ...r.ingredients.map((i) => i.name)].join(" ").toLowerCase().includes(q);
function renderRecipes() {
  const q = $("#q").value.trim().toLowerCase();
  const m = mine().filter((r) => match(r, q));
  const mg = $("#mineGrid"); mg.innerHTML = "";
  if (!m.length) mg.innerHTML = `<p class="muted">${esc(t("empty_mine"))}</p>`;
  m.forEach((r) => mg.appendChild(card(r, "mine")));
  const cats = [...new Set(community.map((r) => r.category).filter(Boolean))];
  $("#cats").innerHTML = "";
  [["", t("all")], ...cats.map((c) => [c, c])].forEach(([v, label]) => {
    const p = document.createElement("button"); p.className = "pill"; p.textContent = label;
    p.setAttribute("aria-pressed", String(cat === v));
    p.onclick = () => { cat = v; renderRecipes(); };
    $("#cats").appendChild(p);
  });
  const cg = $("#commGrid"); cg.innerHTML = community.length ? "" : `<p class="muted">${esc(t("loading"))}</p>`;
  community.filter((r) => (!cat || r.category === cat) && match(r, q)).forEach((r) => cg.appendChild(card(r, "community")));
}
$("#q").addEventListener("input", renderRecipes);
async function loadCommunity() {
  try {
    const idx = await (await fetch("recipes/index.json", { cache: "no-cache" })).json();
    community = idx.recipes.map((r) => ({ ...validateAndFix(r), slug: r.slug }));
  } catch { community = []; }
  if (!$("#v-recipes").hidden) renderRecipes();
  const h = location.hash.match(/^#c-(.+)$/);
  if (h) { const r = community.find((x) => x.slug === h[1]); if (r) openRecipe(r, "community"); }
}

// ---------- bookmarklet ----------
let bmCode = "";
async function renderBookmarklet() {
  const sel = $("#country");
  if (!sel.options.length) {
    COUNTRIES.forEach(([loc, host, name]) => sel.add(new Option(`${name} – ${host}`, loc)));
    sel.value = store.get("country", "de-DE");
    sel.onchange = () => { store.set("country", sel.value); renderQueueNote(); };
  }
  if (!bmCode) {
    const src = await (await fetch("bookmarklet.js")).text();
    bmCode = "javascript:" + encodeURIComponent(src.replaceAll("__APP__", APP_URL));
  }
  $("#bmLink").href = bmCode;
}
$("#bmLink").addEventListener("click", (e) => { e.preventDefault(); toast(t("bm_drag")); });
$("#btnCopyBm").addEventListener("click", async () => { await renderBookmarklet(); copy(bmCode); });

// ---------- settings ----------
$("#provider").addEventListener("change", () => {
  const a = aiStore(); a.provider = $("#provider").value; store.set("ai", a); fillSettings(); refreshKeyUi();
});
["#baseUrl", "#apiKey", "#model", "#useReader"].forEach((s) => $(s).addEventListener("change", saveCfgFromForm));
function keyStatus(text, ok) { const s = $("#keyStatus"); s.textContent = text; s.style.color = ok == null ? "" : ok ? "var(--ok)" : "var(--chili)"; }
$("#btnModels").addEventListener("click", async () => {
  saveCfgFromForm(); keyStatus("…");
  try {
    const models = await listModels(cfg());
    $("#modelList").innerHTML = models.map((m) => `<option value="${esc(m)}"></option>`).join("");
    if (!$("#model").value && models.length) { $("#model").value = models[0]; saveCfgFromForm(); }
    keyStatus(t("models_found", models.length), true);
  } catch (err) { keyStatus(aiErrorText(err), false); }
});
$("#btnTestKey").addEventListener("click", async () => {
  saveCfgFromForm();
  if (!isReady(cfg())) return keyStatus(t("err_not_configured"), false);
  keyStatus(t("testing"));
  try { const title = await testConfig(cfg()); keyStatus(t("set_ok") + ` („${title}“)`, true); }
  catch (err) { keyStatus(aiErrorText(err), false); }
});
$("#btnClearKey").addEventListener("click", () => {
  const a = aiStore(); delete a.configs[a.provider]; store.set("ai", a); fillSettings(); refreshKeyUi();
});
$("#btnExport").addEventListener("click", () => download("tunimix-rezepte.json", JSON.stringify(mine(), null, 2), "application/json"));
$("#importFile").addEventListener("change", async (e) => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const data = JSON.parse(await f.text());
    const arr = (Array.isArray(data) ? data : [data]).map((r) => { const v = validateAndFix(r); v.id = r.id; return v; });
    arr.forEach(saveMine); toast(`${arr.length} ✓`); show("recipes");
  } catch (err) { toast(`${t("invalid")}: ${err.message}`); }
});
$("#uiLang").addEventListener("change", () => { lang = $("#uiLang").value; store.set("ui", lang); applyI18n(); });

// ---------- start ----------
loadDefaults();
applyI18n();
readShareTarget();
const h = location.hash.slice(1);
if (h.startsWith("r-")) { const r = mine().find((x) => x.id === h.slice(2)); r ? openRecipe(r, "mine") : show("new"); }
else show(VIEWS.includes(h) && h !== "recipe" ? h : "new", false);
loadCommunity();
if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
