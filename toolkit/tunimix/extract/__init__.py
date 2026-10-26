"""Extractors: turn any input into a `RawSource` the converter can read.

Supported inputs
- Recipe URL (any site)          -> web.extract_url
- YouTube URL                    -> video.extract_youtube
- Dish name ("ojja merguez")     -> search.find_recipe (web search, then web.extract_url)
- Pasted text                    -> RawSource(text=...)
- Photo / scan / PDF / .txt/.md  -> media.extract_file (Claude vision for images & PDFs)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RawSource:
    kind: str                       # url | youtube | search | text | image | pdf
    text: str = ""                  # readable recipe text for the converter
    structured: dict = field(default_factory=dict)  # parsed fields when available
    url: str = ""
    title: str = ""
    image_url: str = ""
    media: list[dict] = field(default_factory=list)  # Claude content blocks (images/PDF)

    def as_prompt(self) -> str:
        parts = []
        if self.title:
            parts.append(f"TITLE: {self.title}")
        if self.url:
            parts.append(f"SOURCE: {self.url}")
        s = self.structured
        if s.get("yields"):
            parts.append(f"YIELD: {s['yields']}")
        if s.get("total_time"):
            parts.append(f"TOTAL TIME (min): {s['total_time']}")
        if s.get("ingredients"):
            parts.append("INGREDIENTS:\n" + "\n".join(f"- {i}" for i in s["ingredients"]))
        if s.get("instructions"):
            parts.append("INSTRUCTIONS:\n" + "\n".join(
                f"{n}. {i}" for n, i in enumerate(s["instructions"], 1)))
        if self.text and not (s.get("ingredients") and s.get("instructions")):
            parts.append("PAGE / SOURCE TEXT:\n" + self.text[:30000])
        return "\n\n".join(parts)


URL_RE = re.compile(r"^https?://\S+$", re.I)
YT_RE = re.compile(r"(youtube\.com/(watch|shorts)|youtu\.be/)", re.I)
FILE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".pdf", ".txt", ".md", ".docx", ".doc", ".html",
            ".htm", ".tif", ".tiff", ".bmp"}


def detect_kind(value: str) -> str:
    v = value.strip()
    if URL_RE.match(v):
        return "youtube" if YT_RE.search(v) else "url"
    p = Path(v).expanduser()
    if len(v) < 400 and p.suffix.lower() in FILE_EXT and p.exists():
        return "file"
    # short phrase without line breaks -> treat as a dish name to search for
    if "\n" not in v and len(v.split()) <= 8:
        return "search"
    return "text"


def extract(value: str, kind: str | None = None) -> RawSource:
    kind = kind or detect_kind(value)
    if kind == "url":
        from .web import extract_url
        return extract_url(value.strip())
    if kind == "youtube":
        from .video import extract_youtube
        return extract_youtube(value.strip())
    if kind == "file":
        from .media import extract_file
        return extract_file(Path(value.strip()).expanduser())
    if kind == "search":
        from .search import find_recipe
        return find_recipe(value.strip())
    return RawSource(kind="text", text=value)
