"""Upload recipes to Cookidoo "Meine Kreationen / Created Recipes".

Uses the unofficial, reverse-engineered `cookidoo-api` package
(https://github.com/miaucl/cookidoo-api). Vorwerk can change the API at any
time; use it only for your own account and at low volume.

Each step's setting string ("5 Min./100°C/Linkslauf/Stufe 1") becomes a TTS
annotation, so the Thermomix shows a tappable setting button for it (guided
cooking). Modes (dough, browning, steaming, turbo …) become MODE annotations.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from ..config import ROOT, settings
from ..formatting import step_text_with_setting
from ..models import Recipe, TMSetting

log = logging.getLogger(__name__)
TOKEN_FILE = ROOT / ".cookidoo_token.json"


def _annotation(st: TMSetting, slot: str):
    from cookidoo_api.types import (CookidooModeAnnotation, CookidooTemperatureSetting,
                                    CookidooTTSAnnotation)
    temp = None
    if st.temperature is not None:
        temp = CookidooTemperatureSetting(value="varoma" if st.temperature == "varoma"
                                          else str(st.temperature))
    direction = "CCW" if st.reverse else None
    if st.mode:
        return CookidooModeAnnotation(slot=slot, mode=st.mode, time=st.time_s,
                                      temperature=temp, speed=st.speed, direction=direction,
                                      power=st.browning_power, accessory=st.accessory)
    return CookidooTTSAnnotation(slot=slot, time=st.time_s, temperature=temp,
                                 speed=st.speed, direction=direction)


def build_create_payload(recipe: Recipe, ingredient_chips: bool = False):
    """Map our Recipe to cookidoo_api's CookidooCreateCustomRecipe (offline)."""
    from cookidoo_api.types import (CookidooCreateCustomRecipe, CookidooIngredientAnnotation,
                                    CookidooInstruction)
    lines = recipe.ingredient_lines()
    instructions = []
    for step in recipe.steps:
        text, slot = step_text_with_setting(step.text, step.setting, recipe.language)
        if step.off_machine:
            text = f"{text}"
        annotations = []
        if slot and step.setting:
            annotations.append(_annotation(step.setting, slot))
        if ingredient_chips:
            slot_start = text.find(slot) if slot else -1
            for ing, line in zip(recipe.ingredients, lines):
                pos = text.find(ing.name)
                if pos < 0:
                    continue
                if slot and slot_start <= pos < slot_start + len(slot):
                    continue
                annotations.append(CookidooIngredientAnnotation(slot=ing.name, description=line))
        instructions.append(CookidooInstruction(text=text, annotations=annotations)
                            if annotations else text)
    hints = list(recipe.hints)
    if recipe.source_url:
        hints.append(f"Quelle: {recipe.source_url}")
    title = recipe.title if not recipe.original_title else f"{recipe.title}"
    return CookidooCreateCustomRecipe(
        name=title[:120],
        ingredients=lines,
        instructions=instructions,
        serving_size=recipe.servings,
        total_time=recipe.total_time_min * 60,
        active_time=recipe.prep_time_min * 60,
        tools=[recipe.machine],
        unit_text=recipe.unit_text or "portion",
        hints=hints,
    )


def preview_payload(recipe: Recipe, ingredient_chips: bool = False) -> dict:
    """The exact JSON that would be PATCHed to Cookidoo (no network)."""
    from cookidoo_api import Cookidoo
    p = build_create_payload(recipe, ingredient_chips)
    return Cookidoo._build_custom_recipe_payload(
        name=p.name, ingredients=p.ingredients, steps=p.instructions,
        servings=p.serving_size, active_time=p.active_time, total_time=p.total_time,
        hints=p.hints, machine_types=p.tools, unit_text=p.unit_text, image=None,
        image_owned_by_user=False, work_status="PRIVATE", requires_annotations_check=False)


class CookidooClient:
    """Async context manager: `async with CookidooClient() as c: await c.upload(r)`."""

    def __init__(self):
        settings.require_cookidoo()
        self._session = None
        self.api = None

    async def __aenter__(self):
        from aiohttp import ClientSession, CookieJar
        from cookidoo_api import Cookidoo, CookidooConfig, get_localization_options
        self._session = ClientSession(cookie_jar=CookieJar(unsafe=True))
        options = await get_localization_options(country=settings.cookidoo_country,
                                                 language=settings.cookidoo_language)
        if not options:
            raise RuntimeError(f"No Cookidoo localization for {settings.cookidoo_country}/"
                               f"{settings.cookidoo_language}")
        cfg = CookidooConfig(email=settings.cookidoo_email, password=settings.cookidoo_password,
                             localization=options[0])
        self.api = Cookidoo(self._session, cfg)
        if TOKEN_FILE.exists():
            try:
                self.api.load_token(TOKEN_FILE)
                await self.api.refresh()
            except Exception:
                await self.api.login()
        else:
            await self.api.login()
        try:
            self.api.save_token(TOKEN_FILE)
        except Exception:
            pass
        return self

    async def __aexit__(self, *exc):
        if self._session:
            await self._session.close()

    async def upload(self, recipe: Recipe, ingredient_chips: bool = False):
        created = await self.api.create_custom_recipe(build_create_payload(recipe, ingredient_chips))
        return created

    async def list(self):
        return await self.api.list_custom_recipes()

    async def delete(self, recipe_id: str):
        return await self.api.remove_custom_recipe(recipe_id)


async def upload_many(recipes: list[Recipe], ingredient_chips: bool = False,
                      on_done=None) -> list[Recipe]:
    """Upload with a delay between recipes (the create endpoint is rate-limited)."""
    out = []
    async with CookidooClient() as client:
        for i, r in enumerate(recipes):
            if i:
                await asyncio.sleep(settings.upload_delay_s)
            created = await client.upload(r, ingredient_chips)
            r.cookidoo_id = created.id
            r.cookidoo_url = created.url
            out.append(r)
            if on_done:
                on_done(r)
    return out


def upload(recipe: Recipe, ingredient_chips: bool = False) -> Recipe:
    return asyncio.run(upload_many([recipe], ingredient_chips))[0]


def dump_payload(recipe: Recipe, path: Path) -> Path:
    path.write_text(json.dumps(preview_payload(recipe), ensure_ascii=False, indent=2), "utf-8")
    return path
