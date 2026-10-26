"""Your recipe book on disk: one JSON file per recipe in ./library."""
from __future__ import annotations

import json
from pathlib import Path

from .config import ROOT, settings
from .models import Recipe

SEEDS = ROOT / "seeds"
CATEGORY_ORDER = {c: i for i, c in enumerate([
    "vorspeise", "salat", "suppe", "hauptgericht", "beilage", "brot", "dessert", "gebäck",
    "getränk", "grundrezept", "starter", "soup", "main", "dessert", "basics",
    "entrée", "soupe", "plat principal"])}


class Library:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.library_dir)
        self.path.mkdir(parents=True, exist_ok=True)

    def _file(self, slug: str) -> Path:
        return self.path / f"{slug}.json"

    def save(self, recipe: Recipe, overwrite: bool = True) -> Path:
        f = self._file(recipe.slug)
        if f.exists() and not overwrite:
            n = 2
            while self._file(f"{recipe.slug}-{n}").exists():
                n += 1
            f = self._file(f"{recipe.slug}-{n}")
        f.write_text(recipe.model_dump_json(indent=2), encoding="utf-8")
        return f

    def get(self, slug: str) -> Recipe:
        f = self._file(slug)
        if not f.exists():
            matches = [p for p in self.path.glob("*.json") if slug.lower() in p.stem]
            if len(matches) != 1:
                raise KeyError(f"Recipe '{slug}' not found ({len(matches)} matches)")
            f = matches[0]
        return Recipe.model_validate_json(f.read_text(encoding="utf-8"))

    def all(self) -> list[Recipe]:
        out = []
        for f in sorted(self.path.glob("*.json")):
            try:
                out.append(Recipe.model_validate_json(f.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(out, key=lambda r: (CATEGORY_ORDER.get(r.category.lower(), 50), r.category, r.title))

    def delete(self, slug: str) -> None:
        self._file(slug).unlink(missing_ok=True)

    def import_seeds(self) -> int:
        n = 0
        for f in sorted(SEEDS.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            r = Recipe(**data)
            if not self._file(r.slug).exists():
                self.save(r)
                n += 1
        return n
