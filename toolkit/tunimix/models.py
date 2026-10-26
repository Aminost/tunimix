"""Data model for a Thermomix-ready recipe.

One `Recipe` is the single source of truth. Every input (link, dish name, text,
photo, PDF, video transcript) is converted into it, and every output (Cookidoo,
PDF cookbook, HTML, Markdown, schema.org JSON-LD, copy-paste text) is rendered
from it.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Thermomix limits (TM5 / TM6 / TM7)
SPEEDS = ["soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5",
          "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10"]
TEMPS = [37, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100, 105, 110,
         115, 120]
MODES = ["dough", "browning", "turbo", "steaming", "blend", "warm_up",
         "rice_cooker"]
ACCESSORIES = ["Varoma", "SimmeringBasket", "VaromaAndSimmeringBasket"]
MACHINES = ["TM5", "TM6", "TM7"]
BOWL_CAPACITY_ML = 2200


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "recipe"


class TMSetting(BaseModel):
    """Guided-cooking setting for one step (what the Thermomix runs)."""

    time_s: int | None = Field(None, ge=0, description="Duration in seconds")
    temperature: int | Literal["varoma"] | None = Field(
        None, description="°C (37-120) or 'varoma'")
    speed: str | None = Field(None, description="'soft', '0.5' … '10'")
    reverse: bool = Field(False, description="Linkslauf / reverse blade")
    mode: Literal["dough", "browning", "turbo", "steaming", "blend", "warm_up",
                  "rice_cooker"] | None = None
    accessory: Literal["Varoma", "SimmeringBasket",
                       "VaromaAndSimmeringBasket"] | None = None
    browning_power: Literal["Gentle", "Intense"] | None = None

    @field_validator("speed", mode="before")
    @classmethod
    def _norm_speed(cls, v):
        if v is None or v == "":
            return None
        s = str(v).strip().lower().replace(",", ".")
        if s in {"sanft", "spoon", "stir", "doux", "mijotage"}:
            s = "soft"
        if s.endswith(".0"):
            s = s[:-2]
        if s not in SPEEDS:
            raise ValueError(f"invalid speed {v!r}; allowed: {SPEEDS}")
        return s

    @field_validator("temperature", mode="before")
    @classmethod
    def _norm_temp(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            s = v.strip().lower().replace("°c", "").replace("°", "").strip()
            if s == "varoma":
                return "varoma"
            v = int(float(s))
        v = int(v)
        if v > 120:
            return "varoma"
        if v < 37:
            raise ValueError(f"temperature {v} below Thermomix minimum 37°C")
        # snap to nearest Thermomix step
        return min(TEMPS, key=lambda t: abs(t - v))

    @property
    def is_empty(self) -> bool:
        return not any([self.time_s, self.temperature, self.speed, self.mode])


class Ingredient(BaseModel):
    amount: str = Field("", description="e.g. '400', '1-2', '½'")
    unit: str = Field("", description="g, ml, EL, TL, Prise …")
    name: str
    note: str = Field("", description="e.g. 'in Stücken', 'optional'")
    group: str = Field("", description="Sub-heading, e.g. 'Für die Soße'")

    def line(self) -> str:
        parts = [p for p in [self.amount, self.unit, self.name] if p]
        s = " ".join(parts)
        if self.note:
            s += f", {self.note}"
        return s.strip()


class Step(BaseModel):
    text: str = Field(..., description="Instruction text WITHOUT the setting string")
    setting: TMSetting | None = None
    off_machine: bool = Field(False, description="True for oven/pan/hands steps")

    @model_validator(mode="after")
    def _drop_empty(self):
        if self.setting is not None and self.setting.is_empty:
            self.setting = None
        return self


class Recipe(BaseModel):
    title: str
    original_title: str = Field("", description="Name in Arabic/Tounsi/French")
    description: str = ""
    language: str = "de"
    servings: int = Field(4, ge=1)
    unit_text: str = "portion"
    prep_time_min: int = Field(15, ge=0, description="Active time")
    total_time_min: int = Field(45, ge=0)
    machine: Literal["TM5", "TM6", "TM7"] = "TM6"
    category: str = Field("", description="Hauptgericht, Suppe, Vorspeise, Dessert…")
    region: str = Field("Tunesien")
    tags: list[str] = Field(default_factory=list)
    ingredients: list[Ingredient]
    steps: list[Step]
    hints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list,
                                description="Validator / converter warnings")
    source_url: str = ""
    source_type: str = ""
    image_url: str = ""
    image_file: str = Field("", description="Local copy of the recipe picture (library/images/…)")
    cookidoo_id: str = ""
    cookidoo_url: str = ""

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @model_validator(mode="after")
    def _times(self):
        if self.prep_time_min > self.total_time_min:
            self.total_time_min = self.prep_time_min
        return self

    def ingredient_lines(self) -> list[str]:
        return [i.line() for i in self.ingredients]
