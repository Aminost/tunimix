"""Deterministic Thermomix safety & quality checks, applied after the LLM.

Auto-fixes what is safe to fix, and records a warning for everything else.
"""
from __future__ import annotations

import re

from ..models import BOWL_CAPACITY_ML, Recipe, Step, TMSetting

MAX_STEP_S = 99 * 60
PIECES = re.compile(
    r"fleisch|hähnchen|huhn|lamm|rind|kalb|merguez|fisch|kichererbsen|kartoffel|"
    r"stück|würfel|chicken|lamb|beef|meat|fish|chickpea|potato|chunk|poulet|agneau|"
    r"viande|poisson|pois chiche|pomme de terre|morceau", re.I)
LIQUID_UNITS = {"ml": 1, "l": 1000, "liter": 1000, "cl": 10}
PUREE = re.compile(r"pürier|mix|purée|puree|blend|mixer|zerkleiner|chop|hach|mahl|grind", re.I)


def _split_long_steps(recipe: Recipe) -> None:
    new_steps: list[Step] = []
    for st in recipe.steps:
        s = st.setting
        if s and s.time_s and s.time_s > MAX_STEP_S:
            remaining = s.time_s
            first = True
            while remaining > 0:
                chunk = min(remaining, MAX_STEP_S)
                text = st.text if first else (
                    "Weitergaren {S}." if recipe.language.startswith("de") else
                    "Poursuivre la cuisson {S}." if recipe.language.startswith("fr") else
                    "Continue cooking {S}.")
                new_steps.append(Step(text=text, setting=s.model_copy(update={"time_s": chunk})))
                remaining -= chunk
                first = False
            recipe.warnings.append("Langer Garvorgang wurde in Schritte ≤ 99 Min. aufgeteilt.")
        else:
            new_steps.append(st)
    recipe.steps = new_steps


def _liquid_ml(recipe: Recipe) -> int:
    total = 0
    for ing in recipe.ingredients:
        unit = ing.unit.lower().strip(".")
        if unit in LIQUID_UNITS:
            try:
                amount = float(ing.amount.replace(",", ".").split("-")[-1])
            except ValueError:
                continue
            total += int(amount * LIQUID_UNITS[unit])
    return total


def validate_and_fix(recipe: Recipe) -> Recipe:
    _split_long_steps(recipe)
    tm5 = recipe.machine == "TM5"
    for n, st in enumerate(recipe.steps, 1):
        s: TMSetting | None = st.setting
        if st.off_machine:
            st.setting = None
            continue
        if s is None:
            continue
        hot = s.temperature == "varoma" or (isinstance(s.temperature, int) and s.temperature >= 60)
        try:
            spd = float(s.speed) if s.speed and s.speed != "soft" else 0.0
        except ValueError:
            spd = 0.0
        # Keep pieces whole while cooking
        if hot and spd <= 2 and not s.reverse and not s.mode and PIECES.search(st.text):
            s.reverse = True
            recipe.warnings.append(f"Schritt {n}: Linkslauf ergänzt (Stücke bleiben ganz).")
        # Hot + fast
        if hot and spd > 3 and not PUREE.search(st.text):
            recipe.warnings.append(
                f"Schritt {n}: hohe Stufe ({s.speed}) bei {s.temperature} °C – bitte prüfen.")
        if hot and spd >= 5 and PUREE.search(st.text):
            recipe.warnings.append(f"Schritt {n}: Heißes Pürieren – Stufe langsam erhöhen.")
        if s.mode == "steaming" and not s.accessory:
            s.accessory = "Varoma"
        if s.mode == "turbo":
            s.temperature = None
        if tm5 and s.mode in ("browning", "rice_cooker", "steaming", "blend", "warm_up"):
            recipe.warnings.append(
                f"Schritt {n}: Modus '{s.mode}' gibt es am TM5 nicht – manuell einstellen.")
        if tm5 and isinstance(s.temperature, int) and s.temperature > 100 and s.temperature != 120:
            pass  # TM5 supports up to 120 too
        if s.time_s is None and not s.mode and s.speed:
            recipe.warnings.append(f"Schritt {n}: keine Zeit angegeben.")
    ml = _liquid_ml(recipe)
    if ml > BOWL_CAPACITY_ML:
        recipe.warnings.append(
            f"Flüssigkeit ≈ {ml} ml > 2,2 L Mixtopf – Menge reduzieren oder in zwei Durchgängen.")
    # de-duplicate warnings, keep order
    seen: set[str] = set()
    recipe.warnings = [w for w in recipe.warnings if not (w in seen or seen.add(w))]
    return recipe
