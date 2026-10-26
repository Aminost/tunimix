// Used by .github/workflows/add-recipe.yml. Reads the issue body (issue form), extracts the
// recipe JSON, validates it with the same rules as the website, writes recipes/<slug>.json.
// Never executes anything from the issue; it is only parsed as JSON.
import { existsSync, writeFileSync, appendFileSync } from "node:fs";
import { parseAiJson, slugify, validateAndFix } from "../core.js";

const body = process.env.ISSUE_BODY || "";
const author = process.env.ISSUE_AUTHOR || "";
const out = (k, v) => process.env.GITHUB_OUTPUT && appendFileSync(process.env.GITHUB_OUTPUT, `${k}<<EOF\n${v}\nEOF\n`);
try {
  const section = body.split(/^###\s+/m).find((s) => /JSON/i.test(s.split("\n")[0])) || body;
  const raw = parseAiJson(section);
  delete raw.id; delete raw.warnings;
  raw.author = raw.author || author;
  const r = validateAndFix(raw);
  let slug = slugify(r.title), n = 2;
  while (existsSync(`recipes/${slug}.json`)) slug = `${slugify(r.title)}-${n++}`;
  const { warnings, ...clean } = r;
  writeFileSync(`recipes/${slug}.json`, JSON.stringify(clean, null, 2) + "\n");
  out("slug", slug); out("title", r.title); out("ok", "true");
  out("warnings", warnings.length ? warnings.map((w) => `- ${w}`).join("\n") : "");
  console.log(`added recipes/${slug}.json`);
} catch (err) {
  out("ok", "false"); out("error", err.message);
  console.error(err.message);
}
