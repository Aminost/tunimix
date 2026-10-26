"""Offline tests: models, formatting, rules, extraction, Cookidoo payload, outputs."""
from pathlib import Path

import pytest

from tunimix.convert.rules import validate_and_fix
from tunimix.extract import detect_kind
from tunimix.extract.web import extract_from_html
from tunimix.formatting import format_setting, step_text_with_setting
from tunimix.models import Ingredient, Recipe, Step, TMSetting

FIX = Path(__file__).parent / "fixtures"


def test_setting_normalisation():
    s = TMSetting(time_s=60, temperature="100°C", speed="1,5")
    assert s.temperature == 100 and s.speed == "1.5"
    assert TMSetting(temperature=130).temperature == "varoma"
    assert TMSetting(temperature=97).temperature == 98       # snapped to TM step
    assert TMSetting(speed="sanft").speed == "soft"
    with pytest.raises(ValueError):
        TMSetting(speed="11")


@pytest.mark.parametrize("st,de,en", [
    (TMSetting(time_s=300, temperature=100, speed="1", reverse=True), "5 Min./100°C/Linkslauf/Stufe 1",
     "5 min/100°C/reverse/speed 1"),
    (TMSetting(time_s=5, speed="5"), "5 Sek./Stufe 5", "5 sec/speed 5"),
    (TMSetting(time_s=2100, temperature="varoma", speed="soft"), "35 Min./Varoma/Sanftrührstufe",
     "35 min/Varoma/speed soft"),
    (TMSetting(time_s=120, mode="dough"), "2 Min./Teigknetstufe", "2 min/Dough"),
])
def test_format(st, de, en):
    assert format_setting(st, "de") == de
    assert format_setting(st, "en") == en


def test_placeholder():
    text, slot = step_text_with_setting("Zwiebel {S} zerkleinern.", TMSetting(time_s=5, speed="5"))
    assert text == "Zwiebel 5 Sek./Stufe 5 zerkleinern." and slot == "5 Sek./Stufe 5"
    text, _ = step_text_with_setting("Zwiebel zerkleinern.", TMSetting(time_s=5, speed="5"))
    assert text == "Zwiebel zerkleinern 5 Sek./Stufe 5."


def _recipe(**kw):
    base = dict(title="Test", ingredients=[Ingredient(amount="500", unit="g", name="Lammfleisch")],
                steps=[Step(text="Lammfleisch {S} garen.", setting=TMSetting(time_s=7200, temperature=100, speed="1"))])
    base.update(kw)
    return Recipe(**base)


def test_rules_split_and_reverse():
    r = validate_and_fix(_recipe())
    assert len(r.steps) == 2
    assert r.steps[0].setting.time_s == 5940 and r.steps[1].setting.time_s == 1260
    assert r.steps[0].setting.reverse  # pieces of meat -> Linkslauf
    assert any("aufgeteilt" in w for w in r.warnings)


def test_rules_liquid_warning():
    r = validate_and_fix(_recipe(ingredients=[Ingredient(amount="2,5", unit="l", name="Wasser")],
                                 steps=[Step(text="kochen")]))
    assert any("2,2 L" in w for w in r.warnings)


def test_off_machine_drops_setting():
    r = validate_and_fix(_recipe(steps=[Step(text="Frittieren", setting=TMSetting(time_s=60, speed="1"),
                                             off_machine=True)]))
    assert r.steps[0].setting is None


def test_detect_kind(tmp_path):
    assert detect_kind("https://www.youtube.com/watch?v=abcdefghijk") == "youtube"
    assert detect_kind("https://cuisine.tn/ojja") == "url"
    assert detect_kind("ojja merguez") == "search"
    assert detect_kind("Zutaten:\n200 g Mehl\n1 Ei") == "text"
    img = tmp_path / "mama.jpg"
    img.write_bytes(b"x")
    assert detect_kind(str(img)) == "file"


def test_jsonld_extraction():
    raw = extract_from_html((FIX / "ojja_page.html").read_text("utf-8"), "https://example.com/ojja")
    s = raw.structured
    assert s["title"] == "Ojja aux crevettes"
    assert len(s["ingredients"]) == 7
    assert any("crevettes" in i for i in s["instructions"])
    assert "INGREDIENTS" in raw.as_prompt()


def test_seeds_valid(seeds):
    assert len(seeds) >= 9
    for r in seeds:
        assert r.ingredients and r.steps
        for st in r.steps:
            if st.setting:
                assert "{S}" not in step_text_with_setting(st.text, st.setting)[0]


def test_cookidoo_payload_all_seeds(seeds):
    from tunimix.outputs.cookidoo import preview_payload
    for r in seeds:
        for chips in (False, True):
            p = preview_payload(r, ingredient_chips=chips)
            assert p["name"] == r.title and p["tools"] == [r.machine]
            assert p["totalTime"] == r.total_time_min * 60
            for step in p["instructions"]:
                for ann in step.get("annotations", []):
                    pos = ann["position"]
                    assert pos["length"] > 0
                    if ann["type"] == "TTS":
                        assert "Min." in step["text"] or "Sek." in step["text"]


def test_cookidoo_reverse_direction(library):
    from tunimix.outputs.cookidoo import preview_payload
    p = preview_payload(library.get("ojja-merguez"))
    dirs = [a["data"].get("direction") for s in p["instructions"] for a in s.get("annotations", [])]
    assert "CCW" in dirs


def test_text_outputs(seeds, tmp_path):
    from tunimix.outputs import export_book, export_recipe
    from tunimix.outputs.text import to_copy_paste, to_jsonld, to_markdown
    r = seeds[0]
    assert r.title in to_markdown(r)
    assert "ZUTATEN" in to_copy_paste(r) or "INGREDIENTS" in to_copy_paste(r)
    assert to_jsonld(r)["@type"] == "Recipe"
    files = export_recipe(r, tmp_path, ("md", "txt", "jsonld", "html", "pdf", "cookidoo-json"))
    assert all(f.exists() and f.stat().st_size > 100 for f in files)
    book = export_book(seeds, tmp_path / "book", "Test-Buch")
    pdf = [f for f in book if f.suffix == ".pdf"][0]
    assert pdf.read_bytes()[:4] == b"%PDF"
    html = [f for f in book if f.suffix == ".html"][0].read_text("utf-8")
    assert "Ojja" in html and "Lablabi" in html
