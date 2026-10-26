import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { cookidooPayload, formatSetting, normSetting, parseAiJson, stepText, validateAndFix, freePrompt, toCopyPaste } from "../core.js";

const recipesDir = new URL("../recipes/", import.meta.url);
const load = (f) => JSON.parse(readFileSync(new URL(f, recipesDir), "utf8"));
const files = readdirSync(recipesDir).filter((f) => f.endsWith(".json") && f !== "index.json");

test("setting normalisation", () => {
  const s = normSetting({ time_s: 60, temperature: "100°C", speed: "1,5" });
  assert.equal(s.temperature, 100); assert.equal(s.speed, "1.5");
  assert.equal(normSetting({ temperature: 130 }).temperature, "varoma");
  assert.equal(normSetting({ temperature: 97 }).temperature, 98);
  assert.throws(() => normSetting({ speed: "11" }));
  assert.equal(normSetting({}), null);
});

test("setting strings in 4 languages", () => {
  const st = { time_s: 300, temperature: 100, speed: "1", reverse: true };
  assert.equal(formatSetting(st, "de"), "5 Min./100°C/Linkslauf/Stufe 1");
  assert.equal(formatSetting(st, "en"), "5 min/100°C/reverse/speed 1");
  assert.equal(formatSetting(st, "fr"), "5 min/100°C/sens inverse/vitesse 1");
  assert.ok(formatSetting(st, "ar").includes("100°C"));
  assert.equal(formatSetting({ time_s: 120, mode: "dough" }, "de"), "2 Min./Teigknetstufe");
});

test("placeholder rendering", () => {
  assert.deepEqual(stepText({ text: "Zwiebel {S} zerkleinern.", setting: { time_s: 5, speed: "5" } }), ["Zwiebel 5 Sek./Stufe 5 zerkleinern.", "5 Sek./Stufe 5"]);
  assert.deepEqual(stepText({ text: "Frittieren.", setting: null, off_machine: true }), ["Frittieren.", ""]);
});

test("rules: split > 99 min and add reverse for pieces", () => {
  const r = validateAndFix({ title: "T", ingredients: [{ name: "Lamm" }], steps: [{ text: "Lammfleisch {S} garen.", setting: { time_s: 7200, temperature: 100, speed: "1" } }] });
  assert.equal(r.steps.length, 2);
  assert.equal(r.steps[0].setting.time_s, 5940);
  assert.equal(r.steps[0].setting.reverse, true);
});

test("JS Cookidoo payload == Python cookidoo-api payload for every seed recipe", () => {
  const py = JSON.parse(readFileSync(new URL("./fixtures/python-payloads.json", import.meta.url), "utf8"));
  for (const [slug, expected] of Object.entries(py)) {
    const js = cookidooPayload(validateAndFix(load(`${slug}.json`)));
    assert.deepEqual(js, expected, slug);
  }
});

test("all community recipes are valid and annotations point at the setting text", () => {
  for (const f of files) {
    const r = validateAndFix(load(f));
    const p = cookidooPayload(r);
    for (const s of p.instructions) for (const a of s.annotations || []) {
      assert.ok(a.position.offset >= 0, f);
      const slice = s.text.slice(a.position.offset, a.position.offset + a.position.length);
      assert.match(slice, /Sek\.|Min\./, f);
    }
  }
});

test("AI answer parsing (fenced, trailing commas)", () => {
  const r = parseAiJson('Sure!\n```json\n{"title":"X","ingredients":[{"name":"a"},],"steps":[{"text":"b"}]}\n```');
  assert.equal(r.title, "X");
});

test("free prompt and copy text", () => {
  assert.ok(freePrompt("https://example.com/r", { language: "fr" }).includes("French"));
  assert.ok(toCopyPaste(validateAndFix(load("lablabi.json"))).includes("ZUTATEN"));
});
