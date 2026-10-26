// Calls the Claude API straight from the browser with the user's own key.
// The key never leaves the user's device except to api.anthropic.com.
import { RECIPE_SCHEMA, systemPrompt, validateAndFix } from "./core.js";

const API = "https://api.anthropic.com/v1/messages";
export const DEFAULT_MODEL = "claude-sonnet-5-5";

const SAVE_TOOL = {
  name: "save_thermomix_recipe",
  description: "Save the converted Thermomix recipe. Call exactly once, at the end.",
  input_schema: RECIPE_SCHEMA,
};

async function call(key, body) {
  const res = await fetch(API, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.error?.message || res.statusText;
    if (res.status === 401) throw new Error("API key invalid (401). Check it in Settings.");
    if (res.status === 429) throw new Error("Rate limit reached – wait a minute and try again.");
    throw new Error(`Claude API ${res.status}: ${msg}`);
  }
  return data;
}

/**
 * input: { text?, url?, dish?, files?: [{mime, base64}] }
 * opts:  { language, machine, servings, wishes, model }
 */
export async function convertWithClaude(key, input, opts = {}, onStatus = () => {}) {
  const lang = opts.language || "de", machine = opts.machine || "TM6";
  const content = [];
  for (const f of input.files || []) {
    if (f.mime === "application/pdf")
      content.push({ type: "document", source: { type: "base64", media_type: "application/pdf", data: f.base64 } });
    else content.push({ type: "image", source: { type: "base64", media_type: f.mime, data: f.base64 } });
  }
  let task = "Convert this recipe into a Thermomix guided recipe and call save_thermomix_recipe.\n";
  if (opts.servings) task += `Scale it to ${opts.servings} servings.\n`;
  if (opts.wishes) task += `Wishes from the cook: ${opts.wishes}\n`;
  if (input.url) task += `\nThe recipe is at this link – fetch it with web_fetch (if it fails, use web_search for the same recipe): ${input.url}\nPut the URL in source_url.\n`;
  if (input.dish) task += `\nOnly a dish name was given: "${input.dish}". Use web_search to find one authentic, complete home-style recipe (local/traditional sources first), read it with web_fetch, and put its URL in source_url.\n`;
  if (input.text) task += `\nRECIPE / PAGE CONTENT:\n${input.text.slice(0, 60000)}\n`;
  if (input.files?.length) task += "\nThe recipe is in the attached file(s) (may be handwritten, Arabic/French/German).\n";
  content.push({ type: "text", text: task });

  const tools = [SAVE_TOOL];
  if (input.url || input.dish) {
    tools.push({ type: "web_fetch_20250910", name: "web_fetch", max_uses: 4, max_content_tokens: 60000 });
    tools.push({ type: "web_search_20250305", name: "web_search", max_uses: 4 });
  }
  const messages = [{ role: "user", content }];
  const base = { model: opts.model || DEFAULT_MODEL, max_tokens: 8000, system: systemPrompt(lang, machine), tools };

  for (let turn = 0; turn < 6; turn++) {
    onStatus(turn === 0 ? "reading" : "working");
    const forced = !(input.url || input.dish) || turn >= 4;
    const resp = await call(key, { ...base, messages, tool_choice: forced ? { type: "tool", name: SAVE_TOOL.name } : { type: "auto" } });
    const save = resp.content.find((b) => b.type === "tool_use" && b.name === SAVE_TOOL.name);
    if (save) {
      try {
        const r = validateAndFix({ ...save.input, language: lang, machine, source_url: save.input.source_url || input.url || "" });
        return r;
      } catch (err) {
        messages.push({ role: "assistant", content: resp.content });
        messages.push({ role: "user", content: [{ type: "tool_result", tool_use_id: save.id, is_error: true,
          content: `Invalid recipe: ${err.message}. Fix it and call save_thermomix_recipe again.` }] });
        continue;
      }
    }
    messages.push({ role: "assistant", content: resp.content });
    if (resp.stop_reason === "pause_turn") continue;  // server tool still working
    messages.push({ role: "user", content: [{ type: "text", text: "Now call save_thermomix_recipe with the converted recipe." }] });
  }
  throw new Error("The AI did not return a recipe. Try again or use the free mode.");
}

export async function testKey(key) {
  await call(key, { model: DEFAULT_MODEL, max_tokens: 5, messages: [{ role: "user", content: "hi" }] });
  return true;
}
