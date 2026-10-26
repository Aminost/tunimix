// The browser rules engine (rules.js) must give exactly the same Thermomix recipe as the
// Python toolkit (toolkit/tunimix/convert/rulebased.py) for the same input.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { convertStructured, structureText } from "../rules.js";

const corpus = JSON.parse(readFileSync(new URL("./fixtures/rules-corpus.json", import.meta.url), "utf8"));
const expected = JSON.parse(readFileSync(new URL("./fixtures/rules-expected.json", import.meta.url), "utf8"));

function view(r) {
  return {
    title: r.title, language: r.language, servings: r.servings, prep_time_min: r.prep_time_min,
    total_time_min: r.total_time_min, category: r.category, ingredients: r.ingredients, steps: r.steps,
    first_warning: r.warnings[0],
    rule_warnings: r.warnings.filter((w) => /(Schritt|Étape|Step)/.test(w) && /(geschätzt|estimé|estimated|erkannt|reconnu|recognised)/.test(w)),
  };
}

corpus.structured.forEach((d, i) => {
  test(`structured recipe parity: ${d.title}`, () => {
    assert.deepStrictEqual(view(convertStructured(d)), expected.structured[i]);
  });
});

corpus.texts.forEach((t, i) => {
  test(`text structuring parity #${i + 1}`, () => {
    const data = structureText(t);
    assert.deepStrictEqual(data, expected.texts[i].data);
    assert.deepStrictEqual(view(convertStructured(data)), expected.texts[i].recipe);
  });
});
