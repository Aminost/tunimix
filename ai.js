// AI providers, all called straight from the browser with the user's own key or local server.
// Keys stay on the user's device and are only sent to the chosen provider.
//
//  anthropic  – native Messages API; can fetch links and search dish names itself
//  ollama     – native /api/chat with JSON-schema constrained output (local, free)
//  everything else – OpenAI-compatible /chat/completions (OpenAI, Gemini, OpenRouter, Groq,
//                    Mistral, DeepSeek, LM Studio, vLLM, LocalAI, any custom endpoint)
import { RECIPE_SCHEMA, parseAiJson, systemPrompt, validateAndFix } from "./core.js";

export const PROVIDERS = {
  anthropic: { label: "Anthropic Claude", base: "https://api.anthropic.com/v1", key: true, web: true, pdf: true,
    keyUrl: "https://console.anthropic.com/settings/keys", hint: "claude-sonnet-5-5" },
  openai: { label: "OpenAI (ChatGPT)", base: "https://api.openai.com/v1", key: true, keyUrl: "https://platform.openai.com/api-keys", hint: "gpt-…" },
  gemini: { label: "Google Gemini", base: "https://generativelanguage.googleapis.com/v1beta/openai", key: true,
    keyUrl: "https://aistudio.google.com/apikey", hint: "gemini-…" },
  openrouter: { label: "OpenRouter (300+ models, some free)", base: "https://openrouter.ai/api/v1", key: true,
    keyUrl: "https://openrouter.ai/keys", hint: "…:free" },
  groq: { label: "Groq", base: "https://api.groq.com/openai/v1", key: true, keyUrl: "https://console.groq.com/keys", hint: "llama-…" },
  mistral: { label: "Mistral", base: "https://api.mistral.ai/v1", key: true, keyUrl: "https://console.mistral.ai/api-keys", hint: "mistral-…" },
  deepseek: { label: "DeepSeek", base: "https://api.deepseek.com/v1", key: true, keyUrl: "https://platform.deepseek.com/api_keys", hint: "deepseek-chat" },
  ollama: { label: "Ollama (local, free)", base: "http://localhost:11434", key: false, local: true, hint: "qwen3, llama3.1, gemma3 …" },
  lmstudio: { label: "LM Studio (local, free)", base: "http://localhost:1234/v1", key: false, local: true, hint: "local model id" },
  custom: { label: "Other (OpenAI-compatible)", base: "", key: true, hint: "model id" },
};

export const isReady = (cfg) => !!cfg && !!PROVIDERS[cfg.provider] && !!cfg.model && (!PROVIDERS[cfg.provider].key || !!cfg.key) && !!baseOf(cfg);
const baseOf = (cfg) => (cfg.base || PROVIDERS[cfg.provider]?.base || "").replace(/\/+$/, "");

class AIError extends Error {}

async function http(url, init, cfg) {
  let res;
  try { res = await fetch(url, init); }
  catch {
    // network error in a browser = server unreachable or CORS refused
    if (PROVIDERS[cfg.provider]?.local)
      throw new AIError(`LOCAL_UNREACHABLE`);
    throw new AIError(`CORS_BLOCKED`);
  }
  const text = await res.text();
  let data = {};
  try { data = JSON.parse(text); } catch {}
  if (!res.ok) {
    const msg = data?.error?.message || data?.error || data?.message || text.slice(0, 300) || res.statusText;
    if (res.status === 401 || res.status === 403) throw new AIError(`API key rejected (${res.status}): ${msg}`);
    if (res.status === 429) throw new AIError(`Rate limit / quota (429): ${msg}`);
    const err = new AIError(`${res.status}: ${typeof msg === "string" ? msg : JSON.stringify(msg)}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

// ---------------- reading inputs without provider web tools ----------------
async function readLink(url, useReader) {
  if (!useReader) throw new AIError("LINK_NEEDS_READER");
  const res = await fetch("https://r.jina.ai/" + url, { headers: { Accept: "text/plain", "X-Return-Format": "markdown" } }).catch(() => null);
  if (!res || !res.ok) throw new AIError("LINK_UNREADABLE");
  const text = await res.text();
  if (text.length < 200) throw new AIError("LINK_UNREADABLE");
  return text.slice(0, 40000);
}

let pdfjs = null;
async function pdfText(base64) {
  if (!pdfjs) {
    await new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
      s.onload = ok; s.onerror = () => fail(new AIError("PDF reader could not be loaded"));
      document.head.appendChild(s);
    });
    pdfjs = window.pdfjsLib;
    pdfjs.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  }
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const doc = await pdfjs.getDocument({ data: bytes }).promise;
  let out = "";
  for (let p = 1; p <= Math.min(doc.numPages, 15); p++) {
    const page = await doc.getPage(p);
    out += (await page.getTextContent()).items.map((i) => i.str).join(" ") + "\n";
  }
  if (out.trim().length < 50) throw new AIError("PDF_NO_TEXT");
  return out;
}

function taskText(input, opts, extra = "") {
  let task = "Convert this recipe into a Thermomix guided recipe.\n";
  if (opts.servings) task += `Scale it to ${opts.servings} servings.\n`;
  if (opts.wishes) task += `Wishes from the cook: ${opts.wishes}\n`;
  return task + extra;
}

const JSON_RULE = `\n\nOUTPUT FORMAT: reply with ONLY one JSON object, no prose, matching this JSON schema:\n${JSON.stringify(RECIPE_SCHEMA)}`;

// ---------------- Anthropic (native, with web tools) ----------------
const SAVE_TOOL = { name: "save_thermomix_recipe", description: "Save the converted Thermomix recipe. Call exactly once, at the end.", input_schema: RECIPE_SCHEMA };

async function viaAnthropic(cfg, input, opts, onStatus) {
  const lang = opts.language || "de", machine = opts.machine || "TM6";
  const call = (body) => http(baseOf(cfg) + "/messages", { method: "POST", headers: {
    "content-type": "application/json", "x-api-key": cfg.key, "anthropic-version": "2023-06-01",
    "anthropic-dangerous-direct-browser-access": "true" }, body: JSON.stringify(body) }, cfg);
  const content = [];
  for (const f of input.files || []) {
    content.push(f.mime === "application/pdf"
      ? { type: "document", source: { type: "base64", media_type: "application/pdf", data: f.base64 } }
      : { type: "image", source: { type: "base64", media_type: f.mime, data: f.base64 } });
  }
  let extra = "Call save_thermomix_recipe with the result.\n";
  if (input.url) extra += `\nThe recipe is at this link – fetch it with web_fetch (if that fails, use web_search for the same recipe): ${input.url}\nPut the URL in source_url.\n`;
  if (input.dish) extra += `\nOnly a dish name was given: "${input.dish}". Use web_search to find one authentic, complete home-style recipe (local/traditional sources first), read it with web_fetch, put its URL in source_url.\n`;
  if (input.text) extra += `\nRECIPE / PAGE CONTENT:\n${input.text.slice(0, 60000)}\n`;
  if (input.files?.length) extra += "\nThe recipe is in the attached file(s) (may be handwritten, Arabic/French/German).\n";
  content.push({ type: "text", text: taskText(input, opts, extra) });
  const tools = [SAVE_TOOL];
  const web = !!(input.url || input.dish);
  if (web) {
    tools.push({ type: "web_fetch_20250910", name: "web_fetch", max_uses: 4, max_content_tokens: 60000 });
    tools.push({ type: "web_search_20250305", name: "web_search", max_uses: 4 });
  }
  const messages = [{ role: "user", content }];
  const base = { model: cfg.model, max_tokens: 8000, system: systemPrompt(lang, machine), tools };
  for (let turn = 0; turn < 6; turn++) {
    onStatus(turn === 0 ? "reading" : "working");
    const forced = !web || turn >= 4;
    const resp = await call({ ...base, messages, tool_choice: forced ? { type: "tool", name: SAVE_TOOL.name } : { type: "auto" } });
    const save = resp.content.find((b) => b.type === "tool_use" && b.name === SAVE_TOOL.name);
    messages.push({ role: "assistant", content: resp.content });
    if (save) {
      try { return finish(save.input, input, opts); }
      catch (err) {
        messages.push({ role: "user", content: [{ type: "tool_result", tool_use_id: save.id, is_error: true,
          content: `Invalid recipe: ${err.message}. Fix it and call save_thermomix_recipe again.` }] });
        continue;
      }
    }
    if (resp.stop_reason === "pause_turn") continue;
    messages.push({ role: "user", content: [{ type: "text", text: "Now call save_thermomix_recipe with the converted recipe." }] });
  }
  throw new AIError("The AI did not return a recipe. Try again.");
}

// ---------------- shared prep for providers without web tools ----------------
async function prepare(cfg, input, opts, onStatus) {
  let extra = "", warnings = [];
  if (input.url) {
    onStatus("reading");
    extra += `\nSOURCE URL: ${input.url}\nPAGE CONTENT:\n${await readLink(input.url, opts.useReader !== false)}\n`;
  }
  if (input.dish) {
    extra += `\nNo source document: only the dish name "${input.dish}". Write an authentic, home-style recipe for it from your own culinary knowledge (traditional version), then convert it. Add a warning that amounts come from general knowledge.\n`;
    warnings.push("dish-from-knowledge");
  }
  if (input.text) extra += `\nRECIPE / PAGE CONTENT:\n${input.text.slice(0, 40000)}\n`;
  const images = [];
  for (const f of input.files || []) {
    if (f.mime === "application/pdf") extra += `\nRECIPE FROM PDF:\n${(await pdfText(f.base64)).slice(0, 40000)}\n`;
    else images.push(f);
  }
  if (images.length) extra += "\nThe recipe is in the attached photo(s) (may be handwritten, Arabic/French/German).\n";
  return { text: taskText(input, opts, extra), images };
}

function finish(data, input, opts) {
  return validateAndFix({ ...data, language: opts.language || "de", machine: opts.machine || "TM6",
    source_url: data.source_url || input.url || "" });
}

async function retryLoop(send, messages, input, opts, onStatus) {
  let lastErr = "";
  for (let attempt = 0; attempt < 3; attempt++) {
    onStatus("working");
    const reply = await send(messages);
    try { return finish(parseAiJson(reply), input, opts); }
    catch (err) {
      lastErr = err.message;
      messages.push({ role: "assistant", content: reply });
      messages.push({ role: "user", content: `That was not valid (${err.message}). Reply again with ONLY the corrected JSON object.` });
    }
  }
  throw new AIError(`The model did not return a valid recipe (${lastErr}). Try a bigger model.`);
}

// ---------------- OpenAI-compatible ----------------
function oaHeaders(cfg) {
  const h = { "content-type": "application/json" };
  if (cfg.key) h.authorization = `Bearer ${cfg.key}`;
  if (cfg.provider === "openrouter") { h["HTTP-Referer"] = location.origin; h["X-Title"] = "TuniMix"; }
  return h;
}

async function viaOpenAI(cfg, input, opts, onStatus) {
  const { text, images } = await prepare(cfg, input, opts, onStatus);
  const user = images.length
    ? [{ type: "text", text }, ...images.map((f) => ({ type: "image_url", image_url: { url: `data:${f.mime};base64,${f.base64}` } }))]
    : text;
  const messages = [{ role: "system", content: systemPrompt(opts.language, opts.machine) + JSON_RULE }, { role: "user", content: user }];
  let jsonMode = true;
  const send = async (msgs) => {
    const body = { model: cfg.model, messages: msgs, temperature: 0.3 };
    if (jsonMode) body.response_format = { type: "json_object" };
    try {
      const d = await http(baseOf(cfg) + "/chat/completions", { method: "POST", headers: oaHeaders(cfg), body: JSON.stringify(body) }, cfg);
      return d.choices?.[0]?.message?.content || "";
    } catch (err) {
      if (jsonMode && err.status === 400) { jsonMode = false; return send(msgs); }  // provider/model without JSON mode
      throw err;
    }
  };
  return retryLoop(send, messages, input, opts, onStatus);
}

// ---------------- Ollama (native API, schema-constrained) ----------------
async function viaOllama(cfg, input, opts, onStatus) {
  const { text, images } = await prepare(cfg, input, opts, onStatus);
  const messages = [{ role: "system", content: systemPrompt(opts.language, opts.machine) + JSON_RULE },
    { role: "user", content: text, ...(images.length ? { images: images.map((f) => f.base64) } : {}) }];
  const send = async (msgs) => {
    const d = await http(baseOf(cfg) + "/api/chat", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: cfg.model, messages: msgs, stream: false, format: RECIPE_SCHEMA,
        options: { temperature: 0.3, num_ctx: 16384 } }) }, cfg);
    return d.message?.content || "";
  };
  return retryLoop(send, messages, input, opts, onStatus);
}

// ---------------- public API ----------------
export async function convert(cfg, input, opts = {}, onStatus = () => {}) {
  if (!isReady(cfg)) throw new AIError("NOT_CONFIGURED");
  if (cfg.provider === "anthropic") return viaAnthropic(cfg, input, opts, onStatus);
  if (cfg.provider === "ollama") return viaOllama(cfg, input, opts, onStatus);
  return viaOpenAI(cfg, input, opts, onStatus);
}

export async function listModels(cfg) {
  const base = baseOf(cfg);
  if (cfg.provider === "ollama") {
    const d = await http(base + "/api/tags", {}, cfg);
    return (d.models || []).map((m) => m.name).sort();
  }
  if (cfg.provider === "anthropic") {
    const d = await http(base + "/models?limit=100", { headers: { "x-api-key": cfg.key, "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true" } }, cfg);
    return (d.data || []).map((m) => m.id);
  }
  const d = await http(base + "/models", { headers: oaHeaders(cfg) }, cfg);
  return (d.data || d.models || []).map((m) => m.id || m.name).filter(Boolean).sort();
}

export async function testConfig(cfg) {
  const r = await convert(cfg, { text: "Tomato soup: 500 g tomatoes, 1 onion, 300 ml water, salt. Chop onion, cook everything 20 min, blend." },
    { language: "en", machine: "TM6", useReader: false });
  return r.title;
}

export { AIError };
