"""Render a TMSetting as the familiar Thermomix setting string.

German:  "5 Min./100°C/Linkslauf/Stufe 1"
English: "5 min/100°C/reverse/speed 1"
French:  "5 min/100°C/sens inverse/vitesse 1"
"""
from __future__ import annotations

from .models import TMSetting

L10N = {
    "de": {"min": "Min.", "sec": "Sek.", "reverse": "Linkslauf", "speed": "Stufe",
           "soft": "Sanftrührstufe", "varoma": "Varoma",
           "modes": {"dough": "Teigknetstufe", "browning": "Anbraten", "turbo": "Turbo",
                     "steaming": "Dampfgaren", "blend": "Mixen", "warm_up": "Aufwärmen",
                     "rice_cooker": "Reiskocher"},
           "acc": {"Varoma": "Varoma", "SimmeringBasket": "Garkörbchen",
                   "VaromaAndSimmeringBasket": "Varoma + Garkörbchen"}},
    "en": {"min": "min", "sec": "sec", "reverse": "reverse", "speed": "speed",
           "soft": "speed soft", "varoma": "Varoma",
           "modes": {"dough": "Dough", "browning": "Browning", "turbo": "Turbo",
                     "steaming": "Steaming", "blend": "Blend", "warm_up": "Warm up",
                     "rice_cooker": "Rice cooker"},
           "acc": {"Varoma": "Varoma", "SimmeringBasket": "simmering basket",
                   "VaromaAndSimmeringBasket": "Varoma + simmering basket"}},
    "fr": {"min": "min", "sec": "sec", "reverse": "sens inverse", "speed": "vitesse",
           "soft": "vitesse mijotage", "varoma": "Varoma",
           "modes": {"dough": "Pétrin", "browning": "Rissolage", "turbo": "Turbo",
                     "steaming": "Cuisson vapeur", "blend": "Mixage", "warm_up": "Réchauffage",
                     "rice_cooker": "Cuiseur à riz"},
           "acc": {"Varoma": "Varoma", "SimmeringBasket": "panier cuisson",
                   "VaromaAndSimmeringBasket": "Varoma + panier cuisson"}},
}


def _l(lang: str) -> dict:
    return L10N.get(lang[:2].lower(), L10N["de"])


def format_time(seconds: int, lang: str = "de") -> str:
    t = _l(lang)
    m, s = divmod(int(seconds), 60)
    if m and s:
        return f"{m} {t['min']} {s} {t['sec']}"
    if m:
        return f"{m} {t['min']}"
    return f"{s} {t['sec']}"


def format_setting(st: TMSetting, lang: str = "de") -> str:
    t = _l(lang)
    parts: list[str] = []
    if st.mode and st.mode not in ("steaming", "dough"):
        label = t["modes"][st.mode]
        if st.mode == "browning" and st.browning_power:
            label += f" ({st.browning_power})"
        parts.append(label)
    if st.time_s:
        parts.append(format_time(st.time_s, lang))
    if st.temperature is not None:
        parts.append(t["varoma"] if st.temperature == "varoma" else f"{st.temperature}°C")
    if st.reverse:
        parts.append(t["reverse"])
    if st.mode in ("dough", "steaming"):
        parts.append(t["modes"][st.mode])
    if st.speed:
        parts.append(t["soft"] if st.speed == "soft" else f"{t['speed']} {st.speed}")
    if st.mode == "steaming" and st.accessory and not (
            st.accessory == "Varoma" and st.temperature == "varoma"):
        parts.append(t["acc"][st.accessory])
    return "/".join(parts)


def step_text_with_setting(text: str, st: TMSetting | None, lang: str = "de") -> tuple[str, str]:
    """Return (full_text, setting_string). The setting string is inserted at
    the {S} placeholder if the text has one, otherwise appended."""
    if st is None:
        return text.replace("{S}", "").strip(), ""
    s = format_setting(st, lang)
    if not s:
        return text.replace("{S}", "").strip(), ""
    if "{S}" in text:
        return text.replace("{S}", s, 1).replace("{S}", ""), s
    body = text.rstrip()
    if body.endswith("."):
        body = body[:-1]
    return f"{body} {s}.", s
