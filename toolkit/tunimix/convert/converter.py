"""Convert a RawSource into a validated Thermomix `Recipe` using Claude."""
from __future__ import annotations

import copy
import json

from pydantic import ValidationError

from ..config import settings
from ..extract import RawSource
from ..models import Recipe
from .prompt import build_system_prompt
from .rules import validate_and_fix

INTERNAL_FIELDS = {"language", "machine", "source_url", "source_type", "image_url",
                   "cookidoo_id", "cookidoo_url"}


def _inline_refs(schema: dict) -> dict:
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return walk(copy.deepcopy(defs[name]))
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(n) for n in node]
        return node

    return walk(schema)


def tool_schema() -> dict:
    schema = _inline_refs(Recipe.model_json_schema())
    for f in INTERNAL_FIELDS:
        schema["properties"].pop(f, None)
    schema["required"] = [r for r in schema.get("required", []) if r not in INTERNAL_FIELDS]
    return {
        "name": "save_thermomix_recipe",
        "description": "Save the converted Thermomix recipe.",
        "input_schema": schema,
    }


def _client():
    import anthropic
    settings.require_anthropic()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _task(raw: RawSource, servings: int | None, extra_instructions: str) -> str:
    request = "Convert this recipe into a Thermomix guided recipe.\n"
    if servings:
        request += f"Scale it to {servings} servings.\n"
    if extra_instructions:
        request += f"Extra wishes from the cook: {extra_instructions}\n"
    return request + "\n" + raw.as_prompt()


def _finish(data: dict, raw: RawSource, language: str, machine: str) -> Recipe:
    src = data.get("source_url") or raw.url
    data = {k: v for k, v in data.items() if k not in INTERNAL_FIELDS}
    recipe = Recipe(**data, language=language, machine=machine, source_url=src,
                    source_type=raw.kind, image_url=raw.image_url)
    return validate_and_fix(recipe)


def _convert_generic(raw: RawSource, language: str, machine: str, servings: int | None,
                     extra_instructions: str) -> Recipe:
    """Any OpenAI-compatible API or Ollama: JSON answer, validated, retried with the error."""
    from .providers import (chat_ollama, chat_openai, resolve, split_media, to_ollama_user,
                            to_openai_user)
    from ..extract.web import parse_json_object
    settings.require_llm()
    base, key = resolve(settings.provider, settings.base_url, settings.api_key)
    schema = tool_schema()["input_schema"]
    images, pdf_text = split_media(raw.media)
    system = build_system_prompt(language, machine).replace(
        "Output by calling the `save_thermomix_recipe` tool exactly once.",
        "Reply with ONLY one JSON object, no prose.") + \
        "\n\n## JSON schema of the answer\n" + json.dumps(schema, ensure_ascii=False)
    text = _task(raw, servings, extra_instructions) + pdf_text
    if images:
        text += "\nThe recipe is in the attached photo(s)."
    if settings.provider == "ollama":
        messages = [{"role": "system", "content": system}, to_ollama_user(text, images)]
        send = lambda msgs: chat_ollama(base, settings.model, msgs, schema)  # noqa: E731
    else:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": to_openai_user(text, images)}]
        send = lambda msgs: chat_openai(base, key, settings.model, msgs, settings.provider)  # noqa: E731
    last_error = ""
    for _ in range(3):
        reply = send(messages)
        try:
            return _finish(parse_json_object(reply), raw, language, machine)
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            messages = messages + [{"role": "assistant", "content": reply},
                                   {"role": "user", "content": f"Not valid ({last_error[:800]}). Reply again with ONLY the corrected JSON object."}]
    raise RuntimeError(f"{settings.provider}/{settings.model} returned no valid recipe after 3 attempts: {last_error[:300]}")


def convert(raw: RawSource, language: str | None = None, machine: str | None = None,
            servings: int | None = None, extra_instructions: str = "") -> Recipe:
    language = language or settings.recipe_language
    machine = machine or settings.machine
    if settings.provider != "anthropic":
        return _convert_generic(raw, language, machine, servings, extra_instructions)
    client = _client()

    request = "Convert this recipe into a Thermomix guided recipe.\n"
    if servings:
        request += f"Scale it to {servings} servings.\n"
    if extra_instructions:
        request += f"Extra wishes from the cook: {extra_instructions}\n"
    content: list[dict] = list(raw.media) + [{"type": "text", "text": request + "\n" + raw.as_prompt()}]
    messages = [{"role": "user", "content": content}]
    tool = tool_schema()

    last_error = ""
    for attempt in range(3):
        resp = client.messages.create(
            model=settings.model,
            max_tokens=8000,
            system=build_system_prompt(language, machine),
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=messages,
        )
        block = next(b for b in resp.content if b.type == "tool_use")
        data = dict(block.input)
        try:
            recipe = Recipe(**data, language=language, machine=machine,
                            source_url=raw.url, source_type=raw.kind,
                            image_url=raw.image_url)
            return validate_and_fix(recipe)
        except ValidationError as exc:
            last_error = str(exc)
            messages = messages + [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": block.id, "is_error": True,
                    "content": f"Validation failed, fix and call the tool again:\n{last_error}"}]},
            ]
    raise RuntimeError(f"Could not produce a valid recipe after 3 attempts: {last_error}")


def recipe_from_json(data: dict | str) -> Recipe:
    """For recipes written by Claude Desktop via MCP or edited by hand."""
    if isinstance(data, str):
        data = json.loads(data)
    return validate_and_fix(Recipe(**data))
