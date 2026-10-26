"""Regenerate tests/fixtures/rules-expected.json from the Python rules engine.
The website's rules.js must produce the same output (tests/rules-parity.test.mjs).
Run from the repo root:  python toolkit/scripts_rules_expected.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "toolkit"))
from tunimix.convert.rulebased import convert_structured  # noqa: E402
from tunimix.extract.documents import structure_text  # noqa: E402

KEYS = ["title", "language", "servings", "prep_time_min", "total_time_min", "category", "ingredients", "steps"]


def dump(r):
    d = json.loads(r.model_dump_json())
    out = {k: d[k] for k in KEYS}
    out["first_warning"] = d["warnings"][0]
    out["rule_warnings"] = [w for w in d["warnings"] if any(x in w for x in ("Schritt", "Étape", "Step"))
                            and any(y in w for y in ("geschätzt", "estimé", "estimated", "erkannt", "reconnu", "recognised"))]
    return out


corpus = json.loads((ROOT / "tests/fixtures/rules-corpus.json").read_text(encoding="utf-8"))
res = {"structured": [dump(convert_structured(d)) for d in corpus["structured"]],
       "texts": []}
for t in corpus["texts"]:
    text, title = (t["text"], t.get("title", "")) if isinstance(t, dict) else (t, "")
    data = structure_text(text, title)
    res["texts"].append({"data": data, "recipe": dump(convert_structured(data))})
(ROOT / "tests/fixtures/rules-expected.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("rules-expected.json updated")
