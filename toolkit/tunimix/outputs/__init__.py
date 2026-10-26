"""Output adapters. Each takes `Recipe` objects from the library."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import Recipe
from .html import to_html
from .text import to_copy_paste, to_jsonld, to_jsonld_str, to_markdown

FORMATS = ("md", "txt", "jsonld", "html", "pdf", "cookidoo-json")


def export_recipe(recipe: Recipe, out_dir: Path, formats=("md", "txt", "jsonld")) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in formats:
        if fmt == "md":
            p = out_dir / f"{recipe.slug}.md"
            p.write_text(to_markdown(recipe), "utf-8")
        elif fmt == "txt":
            p = out_dir / f"{recipe.slug}.cookidoo.txt"
            p.write_text(to_copy_paste(recipe), "utf-8")
        elif fmt == "jsonld":
            p = out_dir / f"{recipe.slug}.schema.json"
            p.write_text(to_jsonld_str(recipe), "utf-8")
        elif fmt == "cookidoo-json":
            from .cookidoo import preview_payload
            p = out_dir / f"{recipe.slug}.cookidoo-payload.json"
            p.write_text(json.dumps(preview_payload(recipe), ensure_ascii=False, indent=2), "utf-8")
        elif fmt == "html":
            p = out_dir / f"{recipe.slug}.html"
            p.write_text(to_html([recipe], title=recipe.title, subtitle=recipe.original_title or " "), "utf-8")
        elif fmt == "pdf":
            from .pdf import build_pdf
            p = build_pdf([recipe], out_dir / f"{recipe.slug}.pdf", title=recipe.title)
        else:
            raise ValueError(f"unknown format {fmt}")
        written.append(p)
    return written


def export_book(recipes: list[Recipe], out_dir: Path, title: str, formats=("html", "pdf", "md", "jsonld"),
                author: str = "") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if "html" in formats:
        p = out_dir / "kochbuch.html"
        p.write_text(to_html(recipes, title=title), "utf-8")
        written.append(p)
    if "pdf" in formats:
        from .pdf import build_pdf
        written.append(build_pdf(recipes, out_dir / "kochbuch.pdf", title=title, author=author))
    if "md" in formats:
        p = out_dir / "kochbuch.md"
        p.write_text(f"# {title}\n\n" + "\n---\n\n".join(to_markdown(r) for r in recipes), "utf-8")
        written.append(p)
    if "jsonld" in formats:
        p = out_dir / "kochbuch.schema.json"
        p.write_text(json.dumps([to_jsonld(r) for r in recipes], ensure_ascii=False, indent=2), "utf-8")
        written.append(p)
    return written
