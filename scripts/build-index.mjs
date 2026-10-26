// Validates every recipes/*.json and writes recipes/index.json (used by the website).
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { validateAndFix, slugify } from "../core.js";

const dir = new URL("../recipes/", import.meta.url);
const files = readdirSync(dir).filter((f) => f.endsWith(".json") && f !== "index.json").sort();
const recipes = [];
let bad = 0;
for (const f of files) {
  try {
    const raw = JSON.parse(readFileSync(new URL(f, dir), "utf8"));
    const r = validateAndFix(raw);
    recipes.push({ ...r, slug: f.replace(/\.json$/, "") || slugify(r.title) });
  } catch (err) { bad++; console.error(`✗ ${f}: ${err.message}`); }
}
writeFileSync(new URL("index.json", dir), JSON.stringify({ updated: new Date().toISOString(), count: recipes.length, recipes }, null, 1) + "\n");
console.log(`index.json: ${recipes.length} recipes`);
if (bad) process.exit(1);
