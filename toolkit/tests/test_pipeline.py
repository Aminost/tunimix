"""Pipeline, web app and MCP tools with a mocked Claude client (no network)."""
import json
from types import SimpleNamespace

import pytest

from tunimix.extract import RawSource

GOOD = {
    "title": "Kafteji", "original_title": "Kafteji · كفتاجي", "servings": 4,
    "prep_time_min": 20, "total_time_min": 45, "category": "Hauptgericht",
    "ingredients": [{"amount": "2", "unit": "", "name": "Paprika"}, {"amount": "3", "unit": "", "name": "Eier"}],
    "steps": [{"text": "Paprika {S} zerkleinern.", "setting": {"time_s": 4, "speed": "4"}},
              {"text": "Kartoffeln frittieren.", "off_machine": True}],
}


class FakeMessages:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        data = self.payloads.pop(0)
        block = SimpleNamespace(type="tool_use", id=f"tu{len(self.calls)}", input=data)
        return SimpleNamespace(content=[block])


@pytest.fixture
def fake_claude(monkeypatch):
    def install(*payloads):
        fake = FakeMessages(payloads)
        from tunimix.convert import converter
        monkeypatch.setattr(converter, "_client", lambda: SimpleNamespace(messages=fake))
        return fake
    return install


def test_convert_retry_on_invalid(fake_claude):
    from tunimix.convert import convert
    bad = dict(GOOD, steps=[{"text": "x", "setting": {"speed": "42"}}])
    fake = fake_claude(bad, GOOD)
    r = convert(RawSource(kind="text", text="..."), language="de", machine="TM6")
    assert r.title == "Kafteji" and len(fake.calls) == 2
    assert fake.calls[0]["tool_choice"]["name"] == "save_thermomix_recipe"
    assert r.steps[1].setting is None


def test_process_text_and_save(fake_claude, tmp_path):
    from tunimix.library import Library
    from tunimix.pipeline import Options, process
    fake_claude(GOOD)
    lib = Library(tmp_path)
    r = process("Kafteji: Paprika, Kürbis, Eier …\nalles frittieren und hacken", Options(engine="ai"), lib)
    assert lib.get("kafteji").title == r.title


def test_tool_schema_is_self_contained():
    from tunimix.convert import tool_schema
    s = json.dumps(tool_schema())
    assert "$ref" not in s and "cookidoo_id" not in s


def test_web_app(library, monkeypatch):
    from tunimix.interfaces import web
    monkeypatch.setattr(web, "lib", library)
    c = web.app.test_client()
    assert c.get("/").status_code == 200
    assert b"Lablabi" in c.get("/recipes").data
    page = c.get("/r/lablabi")
    assert page.status_code == 200 and "Linkslauf".encode() in page.data
    assert c.get("/r/lablabi/download/pdf").data[:4] == b"%PDF"
    assert c.get("/r/lablabi/download/txt").status_code == 200
    assert b"Lablabi" in c.get("/book").data
    assert c.get("/r/lablabi/edit").status_code == 200


def test_mcp_save_recipe(tmp_path, monkeypatch):
    import asyncio
    from tunimix.interfaces import mcp_server
    from tunimix.library import Library
    monkeypatch.setattr(mcp_server, "lib", Library(tmp_path))
    out = asyncio.run(mcp_server.mcp.call_tool("save_recipe", {"recipe_json": json.dumps(GOOD)}))
    text = out.content[0].text if hasattr(out, "content") else str(out)
    assert "Saved as 'kafteji'" in text
