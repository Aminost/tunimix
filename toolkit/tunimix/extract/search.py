"""Dish name -> recipe from the internet.

Uses Claude with the server-side web search tool to pick an authentic recipe
page (Tunisian/Maghreb sources preferred), then tries to fetch that page for
structured data. If the site blocks scraping, the recipe text Claude read
during the search is used instead.
"""
from __future__ import annotations

import json
import os
import re

from ..config import settings
from . import RawSource

SEARCH_TOOL = os.getenv("TUNIMIX_WEB_SEARCH_TOOL", "web_search_20250305")

FIND_PROMPT = """Find ONE authentic, complete home-style recipe on the web for this dish: "{dish}".

Preferences: Tunisian sources first (Tunisian blogs, Tunisian cooks, French/Arabic
Tunisian recipe sites), then other Maghreb sources, then Thermomix community pages.
The recipe must have an ingredient list with amounts and clear steps.

Reply with ONLY a JSON object, no prose:
{{"url": "<best recipe page>",
  "alternatives": ["<other good url>", "..."],
  "title": "<dish title as on the page>",
  "recipe_text": "<the full recipe as found: yield, ingredients with amounts, numbered steps>"}}"""


def _client():
    import anthropic
    settings.require_anthropic()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("search returned no JSON")
    return json.loads(m.group(0))


def search_candidates(dish: str) -> dict:
    client = _client()
    resp = client.messages.create(
        model=settings.model,
        max_tokens=4000,
        tools=[{"type": SEARCH_TOOL, "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": FIND_PROMPT.format(dish=dish)}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _parse_json(text)


def ddg_search(query: str, limit: int = 6) -> list[str]:
    """Key-free web search (DuckDuckGo HTML) - used when the model can't search itself."""
    import requests
    from urllib.parse import parse_qs, unquote, urlparse
    from bs4 import BeautifulSoup
    from .web import HEADERS
    r = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    urls = []
    for a in BeautifulSoup(r.text, "html.parser").select("a.result__a"):
        href = a.get("href", "")
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        if href.startswith("http") and "duckduckgo.com" not in href and href not in urls:
            urls.append(href)
        if len(urls) >= limit:
            break
    return urls


def find_recipe_any_model(dish: str) -> RawSource:
    from .web import extract_url
    for query in (f"{dish} recette tunisienne", f"{dish} recipe", f"{dish} Rezept"):
        try:
            urls = ddg_search(query)
        except Exception:
            urls = []
        for url in urls:
            try:
                raw = extract_url(url)
            except Exception:
                continue
            if raw.structured.get("ingredients"):
                raw.kind = "search"
                return raw
    return from_knowledge(dish)


def find_recipe(dish: str) -> RawSource:
    if settings.provider != "anthropic":
        return find_recipe_any_model(dish)
    found = search_candidates(dish)
    urls = [found.get("url", "")] + list(found.get("alternatives", []))
    from .web import extract_url
    for url in [u for u in urls if u]:
        try:
            raw = extract_url(url)
            if raw.structured.get("ingredients") or len(raw.text) > 800:
                raw.kind = "search"
                return raw
        except Exception:
            continue
    # fall back to what Claude read during the search
    return RawSource(kind="search", url=found.get("url", ""), title=found.get("title", dish),
                     text=found.get("recipe_text", ""))


def from_knowledge(dish: str) -> RawSource:
    """No web: let the converter write the recipe from culinary knowledge."""
    return RawSource(kind="knowledge", title=dish, text=(
        f"No source document. Write an authentic, home-style Tunisian recipe for "
        f"'{dish}' from your own culinary knowledge, then convert it."))
