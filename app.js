import { cookidooPayload, freePrompt, ingredientLine, lx, parseAiJson, servingsLabel, slugify,
  stepText, toCopyPaste, toMarkdown, validateAndFix } from "./core.js";
import { convertStructured, findRecipeNode, fromHtml, fromJsonLd, structureText } from "./rules.js";
import { readFile } from "./docs.js";
import { COUNTRIES, UI } from "./i18n.js";

// ---------- storage (everything stays in this browser) ----------
const store = {
  get(k, d) { try { const v = localStorage.getItem("tunimix." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tunimix." + k, JSON.stringify(v)); return true; } catch { return false; } },
  del(k) { try { localStorage.removeItem("tunimix." + k); } catch {} },
};
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const APP_URL = new URL("./", location.href).href;
// Ko-fi page for donations (change here to point a fork at your own page).
const KOFI = "https://ko-fi.com/aminoste";   // empty hides the Ko-fi links (for forks)
document.querySelectorAll(".kofiLink, .kofi").forEach((a) => { if (KOFI) { if (a.href !== undefined) a.href = KOFI; } else a.hidden = true; });
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
  };
}

function loadDefaults() {
  const d = store.get("defaults", {});
  $("#optMachine").value = d.machine || "TM6";
  $("#optLang").value = d.language || (["de", "fr", "en", "ar"].includes(lang) ? lang : "de");
  $("#useReader").checked = useReader();
}
// link reader (r.jina.ai) for links typed into the box; the TuniMix button doesn't need it
const useReader = () => store.get("reader", true) !== false;
$("#useReader").addEventListener("change", () => store.set("reader", $("#useReader").checked));
["#optMachine", "#optLang"].forEach((s) => $(s).addEventListener("change", () => {
  store.set("defaults", { machine: $("#optMachine").value, language: $("#optLang").value });
}));

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
    if (!useReader()) throw new Error(t("err_rules_link"));
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

const svg = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  people: svg('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 4.5a3 3 0 0 1 0 6M21 20c0-2.8-1.7-5-4-5.7"/>'),
  clock: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  machine: svg('<path d="M7 4h10l-1 4H8z"/><path d="M6 8h12v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z"/><circle cx="12" cy="14.5" r="2.5"/>'),
  user: svg('<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/>'),
};
function stepHtml(s, rl) {
  const [txt, set] = stepText(s, rl);
  let h = esc(txt);
  if (set) h = h.replace(esc(set), `<span class="chip">${esc(set)}</span>`);
  return `<li>${h}${s.off_machine ? ` <span class="offm">${esc(lx(rl).off)}</span>` : ""}</li>`;
}
function renderRecipe() {
  const r = current; if (!r) return;
  const L = lx(r.language);
  let ing = "", last = null;
  r.ingredients.forEach((i) => {
    if (i.group !== last) { ing += (last !== null ? "</ul>" : "") + (i.group ? `<div class="grp">${esc(i.group)}</div>` : "") + '<ul class="ing">'; last = i.group; }
    ing += `<li>${esc(ingredientLine(i))}</li>`;
  });
  ing += "</ul>";
  const isMine = currentSource === "mine";
  const photo = /^(https:|data:image\/)/.test(r.image_url || "")
    ? `<img class="photo" src="${esc(r.image_url)}" alt="" referrerpolicy="no-referrer" onerror="this.className='photo tile';this.removeAttribute('src')">`
    : `<div class="photo tile" aria-hidden="true"></div>`;
  const facts = [
    [ICON.people, servingsLabel(r)],
    [ICON.clock, `${L.total} ${r.total_time_min} min`],
    [ICON.machine, r.machine],
    ...(r.author ? [[ICON.user, `${t("by")} ${r.author}`]] : []),
  ].map(([i, x]) => `<li>${i}${esc(x)}</li>`).join("");
  $("#recipeView").innerHTML = `
    ${photo}
    <div class="body" lang="${esc(r.language || "")}" dir="${r.language === "ar" ? "rtl" : "ltr"}">
      <div>
        ${r.category ? `<div class="cat">${esc(r.category)}</div>` : ""}
        <h2>${esc(r.title)}</h2>
        ${r.original_title ? `<div class="muted">${esc(r.original_title)}</div>` : ""}
      </div>
      ${r.description ? `<p style="margin:0">${esc(r.description)}</p>` : ""}
      <ul class="facts">${facts}</ul>
      <button class="btn p big wide" data-a="cookidoo">${esc(t("save_cookidoo"))}</button>
      <div class="more">
        <button class="btn ghost" data-a="code">${esc(t("copy_code"))}</button>
        <button class="btn ghost" data-a="text">${esc(t("copy_text"))}</button>
        ${isMine ? `<button class="btn ghost" data-a="share">${esc(t("share"))}</button>` : ""}
        ${r.source_url ? `<a class="btn ghost" href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(t("source"))}</a>` : ""}
      </div>
      <section><h3>${esc(L.ing)}</h3>${ing}</section>
      <section><h3>${esc(L.steps)}</h3><ol class="steps">${r.steps.map((s) => stepHtml(s, r.language)).join("")}</ol></section>
      ${r.hints?.length ? `<section><h3>${esc(L.hints)}</h3><ul class="hints">${r.hints.map((h) => `<li>${esc(h)}</li>`).join("")}</ul></section>` : ""}
      ${r.warnings?.length ? `<div class="warn"><b>${esc(t("check"))}:</b> ${r.warnings.map(esc).join(" ")}</div>` : ""}
      <div class="more">
        <button class="btn ghost" data-a="json">${esc(t("download"))}</button>
        <button class="btn ghost" data-a="md">Markdown</button>
        ${isMine ? `<button class="btn ghost" data-a="edit">${esc(t("edit"))}</button><button class="btn ghost d" data-a="del">${esc(t("del"))}</button>` : ""}
      </div>
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
// The recipe photo travels with the recipe to Cookidoo as a small JPEG (data URI), because the
// Cookidoo page can't download pictures from other sites itself. Web pictures go through the
// open-source images.weserv.nl proxy, which allows browser downloads and shrinks the picture.
function blobToDataUrl(blob) {
  return new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(blob); });
}
function shrink(src, maxW) {
  return new Promise((ok) => {
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, maxW / img.naturalWidth), c = document.createElement("canvas");
      c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
      const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
      try { ok(c.toDataURL("image/jpeg", 0.82)); } catch { ok(""); }
    };
    img.onerror = () => ok("");
    img.src = src;
  });
}
async function recipePhoto(url, maxW = 1200) {
  if (!url) return "";
  if (url.startsWith("data:image/")) return shrink(url, maxW);
  if (!/^https?:/.test(url)) return "";
  const tries = [`https://images.weserv.nl/?url=${encodeURIComponent(url)}&w=${maxW}&output=jpg&q=82`, url];
  for (const u of tries) {
    try {
      const r = await fetch(u, { referrerPolicy: "no-referrer" });
      const b = r.ok ? await r.blob() : null;
      if (b && b.type.startsWith("image/") && b.size > 500) return shrink(await blobToDataUrl(b), maxW);
    } catch {}
  }
  return "";
}

const ACTIONS = {
  async cookidoo() {
    const id = current.id || current.slug || slugify(current.title);
    const q = store.get("queue", []).filter((x) => x.id !== id);
    toast(t("preparing"));
    const item = { id, title: current.title, payload: cookidooPayload(current), image: await recipePhoto(current.image_url) };
    q.push(item);
    if (!store.set("queue", q)) { item.image = ""; store.set("queue", q); }   // storage full: send without photo
    renderQueueNote();
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
  async code() { copy(JSON.stringify([{ payload: cookidooPayload(current), image: await recipePhoto(current.image_url, 800) }])); },
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
  const pic = /^(https:|data:image\/)/.test(r.image_url || "")
    ? `<img class="pic" src="${esc(r.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=&quot;pic tile&quot;></span>'">`
    : `<span class="pic tile" aria-hidden="true"></span>`;
  b.innerHTML = `${pic}<span class="in">${r.category ? `<span class="cat">${esc(r.category)}</span>` : ""}<span class="t">${esc(r.title)}</span>
    ${r.original_title ? `<span class="o">${esc(r.original_title)}</span>` : ""}
    <span class="m">${esc(servingsLabel(r))}, ${r.total_time_min} min, ${esc(r.machine)}</span></span>`;
  b.addEventListener("click", () => openRecipe(r, src));
  return b;
}
const match = (r, q) => !q || [r.title, r.original_title, r.category, ...(r.tags || []), ...r.ingredients.map((i) => i.name)].join(" ").toLowerCase().includes(q);
function renderRecipes() {
  const q = $("#q").value.trim().toLowerCase();
  const m = mine().filter((r) => match(r, q));
  const mg = $("#mineGrid"); mg.innerHTML = "";
  if (!m.length) mg.innerHTML = `<p class="empty" style="grid-column:1/-1">${esc(t("empty_mine"))}</p>`;
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
// Short code for phones: phone browsers often lose or cut the long code, so this one loads it from the site.
const shortBm = (app) => "javascript:(function(){var s=document.createElement('script');s.charset='utf-8';s.src='" + app +
  "bookmarklet.js?v='+Date.now();s.onerror=function(){alert('TuniMix: Laden fehlgeschlagen / could not load – langen Code nutzen.')};document.body.appendChild(s)})()";
$("#bmShort").textContent = shortBm(APP_URL);
$("#btnCopyShort").addEventListener("click", () => copy(shortBm(APP_URL)));

// ---------- settings ----------
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
