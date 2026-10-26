"""Text exports: Markdown, copy-paste (manual Cookidoo / Rezeptwelt entry),
and schema.org JSON-LD (imports into Mealie, Tandoor, Paprika, Nextcloud Cookbook …)."""
from __future__ import annotations

import json
from itertools import groupby

from ..formatting import step_text_with_setting
from ..models import Recipe

LABELS = {
    "de": {"ing": "Zutaten", "steps": "Zubereitung", "hints": "Tipps", "serv": "Portionen",
           "prep": "Arbeitszeit", "total": "Gesamtzeit", "min": "Min.", "src": "Quelle",
           "off": "außerhalb des Thermomix", "warn": "Hinweise zur Umwandlung"},
    "en": {"ing": "Ingredients", "steps": "Method", "hints": "Tips", "serv": "Servings",
           "prep": "Active time", "total": "Total time", "min": "min", "src": "Source",
           "off": "outside the Thermomix", "warn": "Conversion notes"},
    "fr": {"ing": "Ingrédients", "steps": "Préparation", "hints": "Astuces", "serv": "Portions",
           "prep": "Temps actif", "total": "Temps total", "min": "min", "src": "Source",
           "off": "hors Thermomix", "warn": "Remarques de conversion"},
}


def labels(lang: str) -> dict:
    return LABELS.get(lang[:2], LABELS["de"])


def servings_label(recipe: Recipe) -> str:
    L = labels(recipe.language)
    unit = recipe.unit_text if recipe.unit_text and recipe.unit_text != "portion" else L["serv"]
    return f"{recipe.servings} {unit}"


def rendered_steps(recipe: Recipe) -> list[tuple[str, str, bool]]:
    """[(full_text, setting_string, off_machine)]"""
    return [(*step_text_with_setting(s.text, s.setting, recipe.language), s.off_machine)
            for s in recipe.steps]


def grouped_ingredients(recipe: Recipe):
    return [(g, list(items)) for g, items in groupby(recipe.ingredients, key=lambda i: i.group)]


def to_markdown(recipe: Recipe) -> str:
    L = labels(recipe.language)
    out = [f"# {recipe.title}"]
    if recipe.original_title:
        out.append(f"*{recipe.original_title}*")
    if recipe.description:
        out.append(f"\n{recipe.description}")
    out.append(f"\n**{servings_label(recipe)}** · **{L['prep']}:** {recipe.prep_time_min} {L['min']}"
               f" · **{L['total']}:** {recipe.total_time_min} {L['min']} · **{recipe.machine}**")
    out.append(f"\n## {L['ing']}")
    for group, items in grouped_ingredients(recipe):
        if group:
            out.append(f"\n**{group}**")
        out += [f"- {i.line()}" for i in items]
    out.append(f"\n## {L['steps']}")
    for n, (text, setting, off) in enumerate(rendered_steps(recipe), 1):
        if setting:
            text = text.replace(setting, f"**{setting}**", 1)
        out.append(f"{n}. {text}" + (f" *({L['off']})*" if off else ""))
    if recipe.hints:
        out.append(f"\n## {L['hints']}")
        out += [f"- {h}" for h in recipe.hints]
    if recipe.warnings:
        out.append(f"\n> **{L['warn']}:** " + " · ".join(recipe.warnings))
    if recipe.source_url:
        out.append(f"\n{L['src']}: {recipe.source_url}")
    return "\n".join(out) + "\n"


def to_copy_paste(recipe: Recipe) -> str:
    """Plain blocks you can paste field by field into Cookidoo's 'Rezept erstellen'
    form or Rezeptwelt.de - one ingredient / one step per line."""
    L = labels(recipe.language)
    lines = [f"TITEL / TITLE:\n{recipe.title}", "",
             f"{L['serv'].upper()}: {recipe.servings}",
             f"{L['prep'].upper()}: {recipe.prep_time_min} {L['min']}",
             f"{L['total'].upper()}: {recipe.total_time_min} {L['min']}", "",
             f"{L['ing'].upper()} (eine Zeile = ein Feld):"]
    lines += recipe.ingredient_lines()
    lines += ["", f"{L['steps'].upper()} (eine Zeile = ein Schritt):"]
    lines += [t for t, _, _ in rendered_steps(recipe)]
    if recipe.hints:
        lines += ["", f"{L['hints'].upper()}:"] + recipe.hints
    return "\n".join(lines) + "\n"


def to_jsonld(recipe: Recipe) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "alternateName": recipe.original_title or None,
        "description": recipe.description,
        "recipeYield": f"{recipe.servings} {recipe.unit_text}",
        "prepTime": f"PT{recipe.prep_time_min}M",
        "totalTime": f"PT{recipe.total_time_min}M",
        "recipeCategory": recipe.category,
        "recipeCuisine": recipe.region,
        "keywords": ", ".join(["Thermomix", recipe.machine, *recipe.tags]),
        "recipeIngredient": recipe.ingredient_lines(),
        "recipeInstructions": [{"@type": "HowToStep", "text": t} for t, _, _ in rendered_steps(recipe)],
        "url": recipe.source_url or None,
        "image": recipe.image_url or None,
    }


def to_jsonld_str(recipe: Recipe) -> str:
    data = {k: v for k, v in to_jsonld(recipe).items() if v not in (None, "")}
    return json.dumps(data, ensure_ascii=False, indent=2)
