"""Provider layer with mocked HTTP (no network): OpenAI-compatible, Ollama, retries, PDF, search."""
import base64
import json
from types import SimpleNamespace

import pytest

from tunimix.config import settings
from tunimix.extract import RawSource

RECIPE = {"title": "Kafteji", "servings": 4, "prep_time_min": 20, "total_time_min": 40,
          "ingredients": [{"amount": "2", "unit": "", "name": "Paprika"}],
          "steps": [{"text": "Paprika {S} zerkleinern.", "setting": {"time_s": 4, "speed": "4"}}]}


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data
        self.ok = 200 <= status < 300
        self.text = json.dumps(data)

    def json(self):
        return self._data


@pytest.fixture
def provider(monkeypatch):
    def use(name, model="m1", key="k", base=""):
        monkeypatch.setattr(settings, "provider", name)
        monkeypatch.setattr(settings, "model", model)
        monkeypatch.setattr(settings, "api_key", key)
        monkeypatch.setattr(settings, "base_url", base)
    return use


def test_openai_compatible_json_mode_fallback_and_retry(provider, monkeypatch):
    provider("openai")
    calls = []

    def post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json))
        if len(calls) == 1:
            return FakeResp(400, {"error": {"message": "response_format unsupported"}})
        content = "oops not json" if len(calls) == 2 else "```json\n" + __import__("json").dumps(RECIPE) + "\n```"
        return FakeResp(200, {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("requests.post", post)
    from tunimix.convert import convert
    r = convert(RawSource(kind="text", text="Kafteji ...", url="https://x.tn/k"), language="de", machine="TM6")
    assert r.title == "Kafteji" and r.source_url == "https://x.tn/k"
    assert calls[0][0] == "https://api.openai.com/v1/chat/completions"
    assert calls[0][1]["Authorization"] == "Bearer k"
    assert "response_format" in calls[0][2] and "response_format" not in calls[1][2]
    assert "Not valid" in calls[2][2]["messages"][-1]["content"]


def test_ollama_native_schema_and_images(provider, monkeypatch):
    provider("ollama", model="qwen3:8b", key="")
    seen = {}

    def post(url, json=None, timeout=None, headers=None):
        seen.update(url=url, body=json)
        return FakeResp(200, {"message": {"content": __import__("json").dumps(RECIPE)}})

    monkeypatch.setattr("requests.post", post)
    from tunimix.convert import convert
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
    r = convert(RawSource(kind="image", media=[img], text="photo"), language="de", machine="TM6")
    assert r.title == "Kafteji"
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["body"]["format"]["type"] == "object" and seen["body"]["options"]["num_ctx"] == 16384
    assert seen["body"]["messages"][1]["images"] == ["QUJD"]


def test_missing_key_and_model_errors(provider):
    from tunimix.convert.providers import ProviderError
    provider("groq", key="")
    with pytest.raises(ProviderError):
        settings.require_llm()
    provider("ollama", model="", key="")
    with pytest.raises(RuntimeError):
        settings.require_llm()


def test_pdf_text_extraction():
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Lablabi: 250 g Kichererbsen, 5 Knoblauchzehen, Kreuzkuemmel, Wasser, Salz.")
    c.save()
    from tunimix.convert.providers import split_media
    block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.b64encode(buf.getvalue()).decode()}}
    images, text = split_media([block])
    assert not images and "Kichererbsen" in text


def test_dish_search_without_claude(provider, monkeypatch):
    provider("openai")
    from tunimix.extract import search
    monkeypatch.setattr(search, "ddg_search", lambda q, limit=6: ["https://site.tn/kafteji"])
    import tunimix.extract.web as web
    monkeypatch.setattr(web, "extract_url", lambda url: RawSource(kind="url", url=url, structured={"ingredients": ["2 poivrons"]}))
    raw = search.find_recipe("kafteji")
    assert raw.url == "https://site.tn/kafteji" and raw.kind == "search"


def test_ddg_parser(monkeypatch):
    from tunimix.extract import search
    html = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.cuisine.tn%2Fojja&rut=x">Ojja</a>'
            '<a class="result__a" href="https://blog.tn/lablabi">L</a>')
    monkeypatch.setattr("requests.post", lambda *a, **k: SimpleNamespace(text=html, raise_for_status=lambda: None))
    assert search.ddg_search("ojja") == ["https://www.cuisine.tn/ojja", "https://blog.tn/lablabi"]
