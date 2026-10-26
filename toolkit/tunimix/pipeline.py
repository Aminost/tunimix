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
    language: str | None = None
    machine: str | None = None
    servings: int | None = None
    wishes: str = ""          # e.g. "weniger scharf", "mit Lamm statt Huhn"
    kind: str | None = None   # force: url | youtube | search | text | file | knowledge
    upload: bool = False
    ingredient_chips: bool = False
    category: str = ""


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
    raw = from_knowledge(value) if kind == "knowledge" else extract(value, kind)
    return _finish(raw, opt, library)


def process_bytes(data: bytes, filename: str, opt: Options | None = None,
                  library: Library | None = None) -> Recipe:
    return _finish(extract_bytes(data, filename), opt or Options(), library)


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
