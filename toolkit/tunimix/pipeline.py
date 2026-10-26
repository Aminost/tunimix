"""One call from any input to a saved (and optionally uploaded) Thermomix recipe."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .config import settings
from .convert import convert
from .extract import RawSource, detect_kind, extract
from .extract.media import extract_bytes
from .extract.search import from_knowledge
from .library import Library
from .models import Recipe

log = logging.getLogger(__name__)


@dataclass
class Options:
    engine: str | None = None   # "rules" (no AI, default) | "ai"
    language: str | None = None
    machine: str | None = None
    servings: int | None = None
    wishes: str = ""          # e.g. "weniger scharf", "mit Lamm statt Huhn"
    kind: str | None = None   # force: url | youtube | search | text | file | knowledge
    upload: bool = False
    ingredient_chips: bool = False
    category: str = ""


# ---------------- rule-based route (no AI) ----------------
def _download_image(url: str) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        import requests
        from .extract.web import HEADERS
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if not ctype.startswith("image/") or len(r.content) < 5000:
            return None
        ext = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(ctype.split(";")[0], "jpg")
        return r.content, ext
    except Exception:
        return None


def _save_image(recipe: Recipe, lib: Library, image: tuple[bytes, str] | None) -> None:
    if not image:
        return
    data, ext = image
    folder = lib.path / "images"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{recipe.slug}.{ext}"
    path.write_bytes(data)
    recipe.image_file = str(path)


def _structured_from_value(value: str, kind: str) -> tuple[dict, tuple[bytes, str] | None]:
    from .extract.documents import read_document, structure_text
    from .extract.search import ddg_search
    from .extract.web import extract_url
    if kind == "file":
        path = Path(value).expanduser()
        doc = read_document(path.read_bytes(), path.name)
        data = structure_text(doc.text, doc.title)
        return data, (doc.images[0] if doc.images else None)
    if kind in ("url", "youtube"):
        raw = extract_url(value) if kind == "url" else extract(value, "youtube")
        return _raw_to_data(raw), _download_image(raw.image_url)
    if kind == "search":
        for query in (f"{value} recette tunisienne", f"{value} recipe", f"{value} Rezept"):
            try:
                urls = ddg_search(query)
            except Exception:
                urls = []
            for url in urls:
                try:
                    raw = extract_url(url)
                except Exception:
                    continue
                if raw.structured.get("ingredients") and raw.structured.get("instructions"):
                    return _raw_to_data(raw), _download_image(raw.image_url)
        raise RuntimeError(f"No recipe page with ingredients found for '{value}'. Paste a link instead.")
    if kind == "knowledge":
        raise RuntimeError("Writing a recipe from a dish name alone needs AI (--engine ai). Give a link, file or text.")
    return structure_text(value), None


def _raw_to_data(raw: RawSource) -> dict:
    from .extract.documents import structure_text
    s = raw.structured or {}
    if s.get("ingredients") and s.get("instructions"):
        return {"title": s.get("title") or raw.title, "ingredients": s["ingredients"], "instructions": s["instructions"],
                "yields": s.get("yields", ""), "total_time": s.get("total_time"), "prep_time": s.get("prep_time"),
                "description": s.get("description", ""), "url": raw.url, "image": raw.image_url}
    data = structure_text(raw.text, raw.title)
    data.update(url=raw.url, image=raw.image_url)
    return data


def _finish_rules(data: dict, image, opt: Options, library: Library | None) -> Recipe:
    from .convert.rulebased import convert_structured
    if not data.get("ingredients") or not data.get("instructions"):
        raise RuntimeError("Could not find ingredients and steps in this source. "
                           "Check the text (or OCR quality) - or try --engine ai.")
    recipe = convert_structured(data, language=opt.language, machine=opt.machine or settings.machine,
                                servings=opt.servings)
    if opt.category:
        recipe.category = opt.category
    lib = library or Library()
    _save_image(recipe, lib, image)
    if opt.upload:
        from .outputs.cookidoo import upload
        recipe = upload(recipe, opt.ingredient_chips)
    lib.save(recipe)
    return recipe


def _use_rules(opt: Options) -> bool:
    return (opt.engine or settings.engine) != "ai"


# ---------------- AI route ----------------
def _finish(raw: RawSource, opt: Options, library: Library | None) -> Recipe:
    recipe = convert(raw, language=opt.language, machine=opt.machine,
                     servings=opt.servings, extra_instructions=opt.wishes)
    if opt.category:
        recipe.category = opt.category
    lib = library or Library()
    if opt.upload:
        from .outputs.cookidoo import upload
        recipe = upload(recipe, opt.ingredient_chips)
    lib.save(recipe)
    return recipe


def process(value: str, opt: Options | None = None, library: Library | None = None) -> Recipe:
    opt = opt or Options()
    kind = opt.kind or detect_kind(value)
    log.info("input kind: %s", kind)
    if _use_rules(opt):
        data, image = _structured_from_value(value, kind)
        return _finish_rules(data, image, opt, library)
    raw = from_knowledge(value) if kind == "knowledge" else extract(value, kind)
    return _finish(raw, opt, library)


def process_bytes(data: bytes, filename: str, opt: Options | None = None,
                  library: Library | None = None) -> Recipe:
    opt = opt or Options()
    if _use_rules(opt):
        from .extract.documents import read_document, structure_text
        doc = read_document(data, filename)
        return _finish_rules(structure_text(doc.text, doc.title), doc.images[0] if doc.images else None, opt, library)
    return _finish(extract_bytes(data, filename), opt, library)


def process_batch(path: Path, opt: Options | None = None, library: Library | None = None,
                  on_result=None) -> list[tuple[str, Recipe | Exception]]:
    """A text file with one input per line (URLs, dish names); '#' lines are comments."""
    results = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            res: Recipe | Exception = process(line, opt, library)
        except Exception as exc:  # keep going with the rest
            res = exc
        results.append((line, res))
        if on_result:
            on_result(line, res)
    return results


__all__ = ["Options", "process", "process_bytes", "process_batch", "settings"]
