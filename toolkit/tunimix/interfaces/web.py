"""Local web app: paste a link / dish name / text or upload a photo, review the
Thermomix version, upload to Cookidoo, download files, browse the cookbook.

Run:  tunimix web                       (http://127.0.0.1:8765)
Phone on the same Wi-Fi:  tunimix web --host 0.0.0.0  and set TUNIMIX_WEB_TOKEN
Quick-add from any page:  GET /add?url=<recipe-link>  (bookmarklet / iOS Shortcut)
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

from flask import (Flask, Response, abort, redirect, render_template_string, request,
                   send_file, url_for)

from ..config import settings
from ..library import Library
from ..outputs.html import to_html
from ..outputs.text import grouped_ingredients, rendered_steps, servings_label, to_copy_paste, to_jsonld_str, to_markdown

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
TOKEN = os.getenv("TUNIMIX_WEB_TOKEN", "")
lib = Library()

BASE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} · TuniMix</title>
<style>
:root{--bg:#faf6ef;--paper:#fffdf8;--ink:#22201c;--muted:#6f675c;--line:#e6dccb;--blue:#1f5fa8;--terra:#b8502e;--olive:#6b7d3a;--chip:#eef3fa;--chipink:#1f4f8a;--warn:#fff4e0}
@media (prefers-color-scheme:dark){:root{--bg:#16150f;--paper:#1f1d17;--ink:#efe8db;--muted:#a89f90;--line:#36322a;--blue:#7fb0ea;--terra:#e08a63;--olive:#a9bd73;--chip:#1c2a3c;--chipink:#a9cbf3;--warn:#2d2616}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
nav{display:flex;gap:16px;align-items:center;padding:14px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
nav b{font-family:Georgia,serif;font-size:20px;margin-right:auto}nav a{color:var(--blue);text-decoration:none;font-weight:600}
main{max-width:820px;margin:0 auto;padding:20px 16px 60px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
h1,h2{font-family:Georgia,serif}h1{font-size:28px;margin:4px 0}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.tabs label{border:1px solid var(--line);padding:7px 12px;border-radius:999px;cursor:pointer;font-weight:600;font-size:14px}
.tabs input{display:none}.tabs input:checked+span{color:var(--blue)}
input[type=text],input[type=number],textarea,select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit}
textarea{min-height:140px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:10px}
.btn{display:inline-block;border:1px solid var(--blue);background:transparent;color:var(--blue);padding:9px 14px;border-radius:10px;font-weight:600;cursor:pointer;text-decoration:none;font-size:14px}
.btn.p{background:var(--blue);color:#fff}.btn.d{border-color:var(--terra);color:var(--terra)}
.chip{background:var(--chip);color:var(--chipink);font-weight:600;padding:1px 7px;border-radius:6px;white-space:nowrap}
ol li{margin:8px 0}.muted{color:var(--muted)}.warn{background:var(--warn);border-radius:10px;padding:10px 12px;font-size:14px}
.list a{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none}
.err{background:#fde8e4;color:#7a2412;border-radius:10px;padding:10px 12px}
#busy{display:none;margin-top:10px}.actions{display:flex;gap:8px;flex-wrap:wrap}
</style></head><body><nav><b>TuniMix</b><a href="{{ url_for('home') }}">Neu</a><a href="{{ url_for('recipes') }}">Rezepte</a><a href="{{ url_for('book') }}">Kochbuch</a></nav>
<main>{% block body %}{% endblock %}</main></body></html>"""

HOME = BASE.replace("{% block body %}{% endblock %}", """
<h1>Rezept für den Thermomix</h1>
<p class="muted">Link, Gericht, Text oder Foto – wird in ein Guided-Cooking-Rezept umgewandelt.</p>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
<form class="card" method="post" action="{{ url_for('add') }}" enctype="multipart/form-data" onsubmit="document.getElementById('busy').style.display='block'">
<input type="hidden" name="token" value="{{ token }}">
<label for="value"><b>Link, Gerichtname oder Rezepttext</b></label>
<textarea id="value" name="value" placeholder="https://… oder &quot;Kafteji&quot; oder ganzer Rezepttext">{{ prefill }}</textarea>
<div class="row"><div><label for="file">…oder Foto / PDF</label><input id="file" type="file" name="file" accept="image/*,.pdf,.txt,.md"></div>
<div><label for="kind">Art</label><select id="kind" name="kind"><option value="">automatisch</option><option value="url">Link</option><option value="search">Gericht im Web suchen</option><option value="knowledge">Gericht ohne Web (aus Wissen)</option><option value="text">Text</option></select></div></div>
<div class="row"><div><label for="servings">Portionen</label><input id="servings" type="number" name="servings" min="1" max="20" placeholder="wie Original"></div>
<div><label for="machine">Gerät</label><select id="machine" name="machine">{% for m in ['TM6','TM7','TM5'] %}<option {{ 'selected' if m==machine }}>{{ m }}</option>{% endfor %}</select></div>
<div><label for="lang">Sprache</label><select id="lang" name="lang">{% for l,n in [('de','Deutsch'),('fr','Français'),('en','English')] %}<option value="{{ l }}" {{ 'selected' if l==lang }}>{{ n }}</option>{% endfor %}</select></div></div>
<div class="row"><div><label for="wish">Wünsche</label><input id="wish" type="text" name="wish" placeholder="z. B. weniger scharf, mit Lamm"></div>
<div><label for="category">Kategorie</label><input id="category" type="text" name="category" placeholder="Hauptgericht, Suppe …"></div></div>
<p><label><input type="checkbox" name="upload" value="1"> direkt zu Cookidoo hochladen</label></p>
<button class="btn p" type="submit">Umwandeln</button><p id="busy" class="muted">Wird umgewandelt … (20–60 Sek.)</p></form>
<div class="card"><b>Schnell-Import aus dem Browser</b><p class="muted">Diesen Link in die Lesezeichenleiste ziehen, dann auf jeder Rezeptseite anklicken:</p>
<a class="btn" href="javascript:location='{{ request.host_url }}add?token={{ token }}&url='+encodeURIComponent(location.href)">+ Thermomix</a></div>""")

RECIPE = BASE.replace("{% block body %}{% endblock %}", """
{% if msg %}<p class="warn">{{ msg }}</p>{% endif %}
<div class="card"><div class="muted">{{ r.category }}</div><h1>{{ r.title }}</h1>{% if r.original_title %}<div class="muted">{{ r.original_title }}</div>{% endif %}
<p>{{ r.description }}</p><p class="muted">{{ slabel }} · {{ r.prep_time_min }}/{{ r.total_time_min }} Min. · {{ r.machine }}{% if r.source_url %} · <a href="{{ r.source_url }}" target="_blank" rel="noopener">Quelle</a>{% endif %}</p>
<div class="actions">
<form method="post" action="{{ url_for('upload', slug=r.slug) }}"><input type="hidden" name="token" value="{{ token }}"><button class="btn p">{{ 'Erneut zu Cookidoo' if r.cookidoo_id else 'Zu Cookidoo hochladen' }}</button></form>
{% if r.cookidoo_url %}<a class="btn" href="{{ r.cookidoo_url }}" target="_blank" rel="noopener">In Cookidoo öffnen</a>{% endif %}
{% for f,n in [('pdf','PDF'),('md','Markdown'),('txt','Copy-Paste'),('jsonld','schema.org')] %}<a class="btn" href="{{ url_for('download', slug=r.slug, fmt=f, token=token) }}">{{ n }}</a>{% endfor %}
<a class="btn" href="{{ url_for('edit', slug=r.slug, token=token) }}">Bearbeiten</a></div></div>
<div class="card"><h2>Zutaten</h2>{% for g, items in groups %}{% if g %}<b>{{ g }}</b>{% endif %}<ul>{% for i in items %}<li>{{ i.line() }}</li>{% endfor %}</ul>{% endfor %}</div>
<div class="card"><h2>Zubereitung</h2><ol>{% for t, s, off in steps %}<li>{% if s %}{{ t.split(s)[0] }}<span class="chip">{{ s }}</span>{{ t.split(s,1)[1] }}{% else %}{{ t }}{% endif %}{% if off %} <i class="muted">(außerhalb)</i>{% endif %}</li>{% endfor %}</ol></div>
{% if r.hints %}<div class="card"><h2>Tipps</h2><ul>{% for h in r.hints %}<li>{{ h }}</li>{% endfor %}</ul></div>{% endif %}
{% if r.warnings %}<p class="warn"><b>Bitte prüfen:</b> {{ r.warnings|join(' · ') }}</p>{% endif %}
<form method="post" action="{{ url_for('delete', slug=r.slug) }}" onsubmit="return confirm('Rezept löschen?')"><input type="hidden" name="token" value="{{ token }}"><button class="btn d">Löschen</button></form>""")

LIST = BASE.replace("{% block body %}{% endblock %}", """
<h1>Meine Rezepte ({{ rs|length }})</h1>
<div class="actions" style="margin-bottom:12px"><form method="post" action="{{ url_for('upload_all') }}"><input type="hidden" name="token" value="{{ token }}"><button class="btn p">Alle neuen zu Cookidoo</button></form>
<form method="post" action="{{ url_for('seeds') }}"><input type="hidden" name="token" value="{{ token }}"><button class="btn">Tunesische Basisrezepte laden</button></form></div>
{% if msg %}<p class="warn">{{ msg }}</p>{% endif %}
<div class="card list">{% for r in rs %}<a href="{{ url_for('recipe', slug=r.slug, token=token) }}"><span>{{ '☁ ' if r.cookidoo_id }}{{ r.title }}</span><span class="muted">{{ r.category }}</span></a>{% else %}<p class="muted">Noch leer.</p>{% endfor %}</div>""")

EDIT = BASE.replace("{% block body %}{% endblock %}", """
<h1>{{ r.title }} bearbeiten</h1>{% if error %}<p class="err">{{ error }}</p>{% endif %}
<form method="post"><input type="hidden" name="token" value="{{ token }}"><p class="muted">JSON des Rezepts. In Schritten steht {S} für die Thermomix-Einstellung; time_s in Sekunden.</p>
<label for="json" class="muted">Rezept-JSON</label><textarea id="json" name="json" style="min-height:60vh;font-family:monospace;font-size:13px">{{ data }}</textarea>
<p><button class="btn p">Speichern</button></p></form>""")


def _auth():
    if TOKEN and (request.values.get("token") or request.headers.get("X-Token")) != TOKEN:
        abort(401)


def _ctx(**kw):
    return dict(token=TOKEN, title=kw.pop("title", "TuniMix"), **kw)


def _opts(form):
    from ..pipeline import Options
    return Options(language=form.get("lang") or None, machine=form.get("machine") or None,
                   servings=int(form["servings"]) if form.get("servings") else None,
                   wishes=form.get("wish", ""), kind=form.get("kind") or None,
                   upload=bool(form.get("upload")), category=form.get("category", ""))


@app.get("/")
def home():
    _auth()
    return render_template_string(HOME, **_ctx(prefill=request.args.get("url", ""), error=None,
                                               machine=settings.machine, lang=settings.recipe_language))


@app.route("/add", methods=["GET", "POST"])
def add():
    _auth()
    from ..pipeline import Options, process, process_bytes
    try:
        if request.method == "GET":
            url = request.args.get("url", "")
            if not url:
                return redirect(url_for("home", token=TOKEN))
            r = process(url, Options(), lib)
        else:
            f = request.files.get("file")
            if f and f.filename:
                r = process_bytes(f.read(), f.filename, _opts(request.form), lib)
            else:
                value = request.form.get("value", "").strip()
                if not value:
                    raise ValueError("Bitte einen Link, Gerichtnamen oder Text eingeben.")
                r = process(value, _opts(request.form), lib)
    except Exception as exc:
        return render_template_string(HOME, **_ctx(prefill=request.values.get("value", request.args.get("url", "")),
                                                   error=f"{type(exc).__name__}: {exc}",
                                                   machine=settings.machine, lang=settings.recipe_language)), 400
    return redirect(url_for("recipe", slug=r.slug, token=TOKEN))


@app.get("/recipes")
def recipes():
    _auth()
    return render_template_string(LIST, **_ctx(rs=lib.all(), msg=request.args.get("msg")))


@app.get("/r/<slug>")
def recipe(slug):
    _auth()
    r = lib.get(slug)
    return render_template_string(RECIPE, **_ctx(title=r.title, r=r, groups=grouped_ingredients(r),
                                                 steps=rendered_steps(r), slabel=servings_label(r),
                                                 msg=request.args.get("msg")))


@app.route("/r/<slug>/edit", methods=["GET", "POST"])
def edit(slug):
    _auth()
    from ..convert import recipe_from_json
    r = lib.get(slug)
    if request.method == "POST":
        try:
            new = recipe_from_json(request.form["json"])
            if new.slug != slug:
                lib.delete(slug)
            lib.save(new)
            return redirect(url_for("recipe", slug=new.slug, token=TOKEN, msg="Gespeichert."))
        except Exception as exc:
            return render_template_string(EDIT, **_ctx(r=r, data=request.form["json"], error=str(exc)))
    return render_template_string(EDIT, **_ctx(r=r, data=r.model_dump_json(indent=2), error=None))


@app.post("/r/<slug>/upload")
def upload(slug):
    _auth()
    from ..outputs.cookidoo import upload as do_upload
    try:
        r = do_upload(lib.get(slug))
        lib.save(r)
        msg = "In Cookidoo gespeichert – erscheint unter Meine Kreationen und am Thermomix."
    except Exception as exc:
        msg = f"Upload fehlgeschlagen: {exc}"
    return redirect(url_for("recipe", slug=slug, token=TOKEN, msg=msg))


@app.post("/upload-all")
def upload_all():
    _auth()
    import asyncio
    from ..outputs.cookidoo import upload_many
    todo = [r for r in lib.all() if not r.cookidoo_id]
    try:
        asyncio.run(upload_many(todo, on_done=lib.save))
        msg = f"{len(todo)} Rezept(e) hochgeladen."
    except Exception as exc:
        msg = f"Upload abgebrochen: {exc}"
    return redirect(url_for("recipes", token=TOKEN, msg=msg))


@app.post("/seeds")
def seeds():
    _auth()
    n = lib.import_seeds()
    return redirect(url_for("recipes", token=TOKEN, msg=f"{n} Rezept(e) geladen."))


@app.post("/r/<slug>/delete")
def delete(slug):
    _auth()
    lib.delete(slug)
    return redirect(url_for("recipes", token=TOKEN))


@app.get("/r/<slug>/download/<fmt>")
def download(slug, fmt):
    _auth()
    r = lib.get(slug)
    if fmt == "md":
        return Response(to_markdown(r), mimetype="text/markdown",
                        headers={"Content-Disposition": f"attachment; filename={slug}.md"})
    if fmt == "txt":
        return Response(to_copy_paste(r), mimetype="text/plain; charset=utf-8")
    if fmt == "jsonld":
        return Response(to_jsonld_str(r), mimetype="application/ld+json")
    if fmt == "pdf":
        from ..outputs.pdf import build_pdf
        tmp = Path(tempfile.mkdtemp()) / f"{slug}.pdf"
        build_pdf([r], tmp, title=r.title)
        return send_file(io.BytesIO(tmp.read_bytes()), mimetype="application/pdf",
                         download_name=f"{slug}.pdf")
    abort(404)


@app.get("/book")
def book():
    _auth()
    return Response(to_html(lib.all()), mimetype="text/html")


@app.get("/book.pdf")
def book_pdf():
    _auth()
    from ..outputs.pdf import build_pdf
    tmp = Path(tempfile.mkdtemp()) / "kochbuch.pdf"
    build_pdf(lib.all(), tmp)
    return send_file(io.BytesIO(tmp.read_bytes()), mimetype="application/pdf", download_name="kochbuch.pdf")


@app.post("/api/convert")
def api_convert():
    """JSON API for Shortcuts / automations: {"value": "...", "upload": true}"""
    _auth()
    from ..pipeline import Options, process
    body = request.get_json(force=True)
    r = process(body["value"], Options(upload=bool(body.get("upload")), servings=body.get("servings"),
                                       wishes=body.get("wish", "")), lib)
    return Response(r.model_dump_json(), mimetype="application/json")


def run(host: str = "127.0.0.1", port: int = 8765):
    if host not in ("127.0.0.1", "localhost") and not TOKEN:
        print("⚠  Listening on the network without TUNIMIX_WEB_TOKEN – anyone on your Wi-Fi can use it.")
    print(f"TuniMix web app → http://{host}:{port}/" + (f"?token={TOKEN}" if TOKEN else ""))
    app.run(host=host, port=port, debug=False)
