"""MCP server for Claude Desktop / Claude Code.

Claude itself does the conversion (no Anthropic API key needed): it fetches the
source with `get_recipe_source`, reads `thermomix_conversion_guide`, writes the
recipe JSON and saves it with `save_recipe`, then `upload_to_cookidoo`.

Claude Desktop config (claude_desktop_config.json):
{
  "mcpServers": {
    "tunimix": {
      "command": "python",
      "args": ["-m", "tunimix", "mcp"],
      "cwd": "C:/path/to/tunimix"
    }
  }
}
"""
from __future__ import annotations

import asyncio
import json

from ..config import settings
from ..convert import recipe_from_json, tool_schema
from ..convert.prompt import build_system_prompt
from ..extract import extract
from ..library import Library
from ..outputs.text import to_markdown

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

mcp = _Server("tunimix", instructions=(
    "Build the user's Tunisian Thermomix cookbook. Workflow: get_recipe_source (or your own web "
    "search for a dish name) -> read thermomix_conversion_guide -> write the recipe JSON exactly "
    "matching the schema -> save_recipe -> show the result -> upload_to_cookidoo only after the "
    "user agrees."))
lib = Library()


@mcp.tool()
def thermomix_conversion_guide(language: str = "", machine: str = "") -> str:
    """Rules + JSON schema for writing a Thermomix recipe. Read before save_recipe."""
    lang = language or settings.recipe_language
    m = machine or settings.machine
    return (build_system_prompt(lang, m).replace("by calling the `save_thermomix_recipe` tool exactly once",
                                                 "by calling `save_recipe` with JSON")
            + "\n\n## JSON schema for save_recipe\n" + json.dumps(tool_schema()["input_schema"], ensure_ascii=False))


@mcp.tool()
async def get_recipe_source(source: str) -> str:
    """Fetch a recipe page or YouTube video and return its ingredients/steps/text.
    `source` is a URL. (For a dish name, use your own web search and pass the best URL.)"""
    raw = await asyncio.to_thread(extract, source, None if source.startswith("http") else "text")
    return raw.as_prompt()


@mcp.tool()
def save_recipe(recipe_json: str) -> str:
    """Validate (Thermomix safety rules, auto-fixes) and save a recipe to the library.
    Returns the rendered recipe and any warnings."""
    data = json.loads(recipe_json)
    data.setdefault("language", settings.recipe_language)
    data.setdefault("machine", settings.machine)
    r = recipe_from_json(data)
    lib.save(r)
    return f"Saved as '{r.slug}'.\n\n" + to_markdown(r)


@mcp.tool()
def list_recipes() -> str:
    """List recipes in the cookbook (☁ = already on Cookidoo)."""
    return "\n".join(f"{'☁' if r.cookidoo_id else '-'} {r.slug} | {r.category} | {r.title}"
                     for r in lib.all()) or "empty"


@mcp.tool()
def get_recipe(slug: str) -> str:
    """Return one recipe as JSON (to edit and save again)."""
    return lib.get(slug).model_dump_json(indent=2)


@mcp.tool()
async def upload_to_cookidoo(slug: str, ingredient_chips: bool = False) -> str:
    """Upload a saved recipe to Cookidoo 'Created recipes' so it appears on the Thermomix."""
    from ..outputs.cookidoo import upload_many
    r = (await upload_many([lib.get(slug)], ingredient_chips))[0]
    lib.save(r)
    return f"Uploaded: {r.cookidoo_url}"


@mcp.tool()
def preview_cookidoo_payload(slug: str) -> str:
    """Show the exact JSON that would be sent to Cookidoo (no network)."""
    from ..outputs.cookidoo import preview_payload
    return json.dumps(preview_payload(lib.get(slug)), ensure_ascii=False, indent=2)


@mcp.tool()
def build_cookbook(formats: str = "html,pdf", title: str = "Tunesisches Thermomix-Kochbuch") -> str:
    """Write the cookbook files (html, pdf, md, jsonld) and return their paths."""
    from ..outputs import export_book
    paths = export_book(lib.all(), settings.output_dir, title, formats.split(","))
    return "\n".join(str(p) for p in paths)


@mcp.tool()
def import_seed_recipes() -> str:
    """Load the bundled Tunisian base recipes (ojja, lablabi, couscous, makroudh …)."""
    return f"{lib.import_seeds()} recipe(s) imported"


@mcp.prompt()
def tunisian_recipe(dish: str) -> str:
    """Find, convert and save a Tunisian dish for the Thermomix."""
    return (f"Find an authentic Tunisian recipe for '{dish}' on the web (Tunisian sources first). "
            "Call get_recipe_source on the best URL, read thermomix_conversion_guide, convert it, "
            "save_recipe, show me the result and ask before upload_to_cookidoo.")


def run():
    mcp.run()


if __name__ == "__main__":
    run()
