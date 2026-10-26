"""Extract a recipe from any web page.

Strategy (first that works wins):
1. recipe-scrapers (500+ supported sites, plus "wild mode" for schema.org pages)
2. Our own schema.org JSON-LD / microdata parser
3. Readable page text (main content) - the LLM then finds the recipe itself
"""
from __future__ import annotations

import json
import re

import requests
from bs4 import BeautifulSoup

from . import RawSource

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept-Language": "de-DE,de;q=0.9,fr;q=0.8,en;q=0.7,ar;q=0.6",
}


def fetch_html(url: str, timeout: int = 25) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def _iso_minutes(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.match(r"P(?:T)?(?:(\d+)H)?(?:(\d+)M)?", str(value))
    if not m:
        return None
    h, mi = m.groups()
    total = int(h or 0) * 60 + int(mi or 0)
    return total or None


def _flatten_instructions(node) -> list[str]:
    out: list[str] = []
    if isinstance(node, str):
        out += [s.strip() for s in re.split(r"\n+", BeautifulSoup(node, "html.parser").get_text("\n")) if s.strip()]
    elif isinstance(node, list):
        for n in node:
            out += _flatten_instructions(n)
    elif isinstance(node, dict):
        if node.get("@type") == "HowToSection":
            name = node.get("name")
            if name:
                out.append(f"## {name}")
            out += _flatten_instructions(node.get("itemListElement", []))
        else:
            out += _flatten_instructions(node.get("text") or node.get("name") or "")
    return out


def _find_recipe_nodes(data) -> list[dict]:
    found = []
    if isinstance(data, list):
        for d in data:
            found += _find_recipe_nodes(d)
    elif isinstance(data, dict):
        t = data.get("@type")
        types = t if isinstance(t, list) else [t]
        if "Recipe" in types:
            found.append(data)
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                found += _find_recipe_nodes(data[key])
    return found


def parse_jsonld(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw.strip()))
            except json.JSONDecodeError:
                continue
        for node in _find_recipe_nodes(data):
            ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
            instructions = _flatten_instructions(node.get("recipeInstructions") or [])
            if not ingredients and not instructions:
                continue
            image = node.get("image")
            if isinstance(image, list):
                image = image[0] if image else ""
            if isinstance(image, dict):
                image = image.get("url", "")
            y = node.get("recipeYield")
            return {
                "title": BeautifulSoup(str(node.get("name", "")), "html.parser").get_text().strip(),
                "ingredients": [BeautifulSoup(str(i), "html.parser").get_text().strip() for i in ingredients],
                "instructions": instructions,
                "yields": (y[0] if isinstance(y, list) and y else y) or "",
                "total_time": _iso_minutes(node.get("totalTime")),
                "prep_time": _iso_minutes(node.get("prepTime")),
                "image": image or "",
                "description": node.get("description", ""),
            }
    return None


def parse_json_object(text: str) -> dict:
    """First JSON object in an LLM answer (handles ```json fences, prose, trailing commas)."""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    raw = m.group(1) if m else text
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object in the answer")
    raw = raw[a:b + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def readable_text(html: str, limit: int = 30000) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text().strip() if soup.title else "")
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "aside",
                   "form", "iframe", "svg"]):
        t.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text("\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return title, text[:limit]


def extract_from_html(html: str, url: str = "") -> RawSource:
    structured: dict = {}
    try:
        from recipe_scrapers import scrape_html
        sc = scrape_html(html, org_url=url or "https://example.com/", supported_only=False)
        structured = {
            "title": sc.title(),
            "ingredients": sc.ingredients(),
            "instructions": [s for s in sc.instructions_list() if s.strip()],
        }
        for key, fn in (("yields", "yields"), ("total_time", "total_time"), ("image", "image")):
            try:
                structured[key] = getattr(sc, fn)()
            except Exception:
                pass
    except Exception:
        structured = {}
    if not structured.get("ingredients"):
        structured = parse_jsonld(html) or {}
    title, text = readable_text(html)
    return RawSource(
        kind="url",
        url=url,
        title=structured.get("title") or title,
        structured=structured,
        text=text,
        image_url=structured.get("image", "") or "",
    )


def extract_url(url: str) -> RawSource:
    html = fetch_html(url)
    return extract_from_html(html, url)
