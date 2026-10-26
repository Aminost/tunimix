import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("bookmarklet source parses and stays small enough for a bookmark", () => {
  const src = readFileSync(new URL("../bookmarklet.js", import.meta.url), "utf8").replaceAll("__APP__", "https://example.github.io/tunimix/");
  assert.ok(!src.includes("__APP__"));
  assert.ok(src.includes('var APP = "https://example.github.io/tunimix/"'));
  new Function(src);  // syntax check only, not executed
  const url = "javascript:" + encodeURIComponent(src);
  assert.ok(url.length < 64000, `bookmarklet too long: ${url.length}`);
});
