"""Single-file HTML cookbook: searchable, filterable, printable, works offline
and on the phone. Arabic titles render correctly here."""
from __future__ import annotations

import html
import json

from ..models import Recipe
from .text import grouped_ingredients, labels, rendered_steps, servings_label, to_copy_paste


def _thumb(path: str, size: int = 900) -> str:
    """Small JPEG data-URI of the recipe photo so the single HTML file stays self-contained."""
    if not path:
        return ""
    try:
        import base64
        import io
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _recipe_dict(r: Recipe) -> dict:
    return {
        "slug": r.slug, "title": r.title, "original": r.original_title,
        "description": r.description, "category": r.category or "Andere",
        "servings": r.servings, "slabel": servings_label(r), "prep": r.prep_time_min, "total": r.total_time_min,
        "machine": r.machine, "tags": r.tags, "source": r.source_url,
        "cookidoo": r.cookidoo_url, "lang": r.language,
        "groups": [{"name": g, "items": [i.line() for i in items]} for g, items in grouped_ingredients(r)],
        "steps": [{"text": t, "setting": s, "off": off} for t, s, off in rendered_steps(r)],
        "hints": r.hints, "warnings": r.warnings, "copy": to_copy_paste(r), "img": _thumb(r.image_file),
        "L": labels(r.language),
    }


TEMPLATE = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Reem+Kufi:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=Amiri&display=swap" rel="stylesheet">
<style>
/* layout: sticky search bar over a responsive grid of dish cards; recipe opens in a dialog */
:root{--bg:#f5f7fb;--paper:#ffffff;--ink:#14213a;--muted:#5b6780;--line:#dfe5ef;
--blue:#1b5fae;--terra:#c8341f;--olive:#5d7a2e;--chip:#e8f0fb;--chipink:#174f92;--warn:#fff3e2;--onblue:#ffffff;
--display:"Reem Kufi",Georgia,serif;--body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;--ar:Amiri,"Times New Roman",serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0d1320;--paper:#151d2d;--ink:#e7ecf5;
--muted:#9aa6bc;--line:#26324a;--blue:#76aef0;--terra:#f07a63;--olive:#a8c46e;--chip:#1a2a44;--chipink:#a9cdf6;--warn:#2b2414;--onblue:#0d1320;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0d1320;--paper:#151d2d;--ink:#e7ecf5;--muted:#9aa6bc;--line:#26324a;--blue:#76aef0;
--terra:#f07a63;--olive:#a8c46e;--chip:#1a2a44;--chipink:#a9cdf6;--warn:#2b2414;--onblue:#0d1320;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 var(--body)}
header{padding:48px 16px 28px;text-align:center;border-bottom:1px solid var(--line);
background-image:radial-gradient(circle at 50% 0,rgba(31,95,168,.10),transparent 60%)}
.tile{width:56px;height:56px;margin:0 auto 14px;display:block}
h1{font-family:var(--display);font-weight:700;font-size:clamp(30px,6vw,46px);margin:0;text-wrap:balance}
.sub{color:var(--muted);margin-top:6px}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.bar-in{max-width:1080px;margin:0 auto;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search]{flex:1 1 220px;min-width:0;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);font:inherit}
.f{border:1px solid var(--line);background:var(--paper);color:var(--ink);padding:8px 12px;border-radius:999px;font:500 14px var(--body);cursor:pointer}
.f.on{background:var(--blue);border-color:var(--blue);color:var(--onblue)}
main{max-width:1080px;margin:0 auto;padding:20px 16px 64px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px;cursor:pointer;transition:transform .15s,border-color .15s}
.card:hover,.card:focus-visible{transform:translateY(-2px);border-color:var(--blue);outline:none}
@media (prefers-reduced-motion:reduce){.card{transition:none}.card:hover{transform:none}}
.cat{font:600 12px var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--terra)}
.card h3{font-family:var(--display);font-size:21px;margin:6px 0 2px}
.ar{font-family:var(--ar);color:var(--muted)}
.meta{color:var(--muted);font-size:14px;margin-top:8px}
dialog{border:none;border-radius:16px;padding:0;max-width:760px;width:calc(100% - 24px);background:var(--paper);color:var(--ink)}
dialog::backdrop{background:rgba(10,10,10,.55)}
.r{padding:26px 22px 30px}.r h2{font-family:var(--display);font-size:30px;margin:4px 0}
.close{float:right;border:none;background:none;font-size:26px;color:var(--muted);cursor:pointer}
.r h4{font:600 13px var(--body);text-transform:uppercase;letter-spacing:.07em;color:var(--olive);margin:22px 0 8px}
.r ul{padding-left:20px;margin:0}.r li{margin:3px 0}
.g{font-weight:600;margin:10px 0 4px}
ol.steps{list-style:none;padding:0;counter-reset:s;margin:0}
ol.steps li{counter-increment:s;position:relative;padding:10px 0 10px 40px;border-top:1px solid var(--line)}
ol.steps li::before{content:counter(s);position:absolute;left:0;top:10px;width:28px;height:28px;border-radius:50%;background:var(--blue);color:var(--onblue);font:600 14px/28px var(--body);text-align:center}
.chip{display:inline-block;background:var(--chip);color:var(--chipink);font:600 13.5px var(--body);padding:1px 8px;border-radius:6px;white-space:nowrap}
.off{font-size:12px;color:var(--terra);font-weight:600;margin-left:4px}
.warn{background:var(--warn);border-radius:10px;padding:10px 12px;font-size:14px;margin-top:18px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}
.btn{border:1px solid var(--blue);color:var(--blue);background:transparent;padding:9px 14px;border-radius:10px;font:600 14px var(--body);cursor:pointer;text-decoration:none}
.btn.p{background:var(--blue);color:var(--onblue)}
.empty{color:var(--muted);text-align:center;padding:40px}
@media print{.bar,.actions,.close,header .sub{display:none}dialog{position:static;box-shadow:none}}
</style></head><body>
<header>
<svg class="tile" viewBox="0 0 56 56" aria-hidden="true"><rect x="2" y="2" width="52" height="52" rx="10" fill="var(--blue)"/>
<path d="M28 8l6 14 14 6-14 6-6 14-6-14-14-6 14-6z" fill="var(--paper)"/><circle cx="28" cy="28" r="5" fill="var(--terra)"/></svg>
<h1>__TITLE__</h1><div class="sub">__SUB__</div></header>
<div class="bar"><div class="bar-in"><input type="search" id="q" placeholder="Suchen: ojja, couscous, harissa …" aria-label="Rezepte suchen"><span id="filters"></span></div></div>
<main><div class="grid" id="grid"></div></main>
<dialog id="dlg"><div class="r" id="rv"></div></dialog>
<script>
const R=__DATA__;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let cat="Alle";
const cats=["Alle",...new Set(R.map(r=>r.category))];
const F=document.getElementById("filters");
F.innerHTML=cats.map(c=>`<button class="f${c===cat?" on":""}" data-c="${esc(c)}">${esc(c)}</button>`).join(" ");
F.onclick=e=>{const b=e.target.closest("button");if(!b)return;cat=b.dataset.c;F.querySelectorAll(".f").forEach(x=>x.classList.toggle("on",x===b));draw()};
document.getElementById("q").oninput=draw;
function draw(){const q=document.getElementById("q").value.toLowerCase();
const list=R.filter(r=>(cat==="Alle"||r.category===cat)&&(!q||(r.title+" "+r.original+" "+r.tags.join(" ")+" "+r.groups.map(g=>g.items.join(" ")).join(" ")).toLowerCase().includes(q)));
document.getElementById("grid").innerHTML=list.length?list.map(r=>`<article class="card" data-s="${r.slug}" tabindex="0">${r.img?`<img src="${r.img}" alt="" style="width:100%;height:150px;object-fit:cover;border-radius:10px;margin-bottom:10px">`:""}<div class="cat">${esc(r.category)}</div><h3>${esc(r.title)}</h3>${r.original?`<div class="ar">${esc(r.original)}</div>`:""}<div class="meta">${esc(r.slabel)} · ${r.total} ${esc(r.L.min)} · ${esc(r.machine)}</div></article>`).join(""):`<div class="empty">Keine Rezepte gefunden.</div>`;}
document.getElementById("grid").addEventListener("click",e=>{const c=e.target.closest(".card");if(c)show(c.dataset.s)});
document.getElementById("grid").addEventListener("keydown",e=>{if(e.key==="Enter"){const c=e.target.closest(".card");if(c)show(c.dataset.s)}});
function stepHtml(s){let t=esc(s.text);if(s.setting){t=t.replace(esc(s.setting),`<span class="chip">${esc(s.setting)}</span>`)}return `<li>${t}${s.off?`<span class="off">· ${esc(R[0].L.off)}</span>`:""}</li>`}
function show(slug){const r=R.find(x=>x.slug===slug);const L=r.L;
document.getElementById("rv").innerHTML=`<button class="close" aria-label="Schließen" onclick="dlg.close()">×</button>
${r.img?`<img src="${r.img}" alt="" style="width:100%;border-radius:12px;margin:8px 0 12px;max-height:340px;object-fit:cover">`:""}<div class="cat">${esc(r.category)}</div><h2>${esc(r.title)}</h2>${r.original?`<div class="ar">${esc(r.original)}</div>`:""}
${r.description?`<p>${esc(r.description)}</p>`:""}
<div class="meta">${esc(r.slabel)} · ${esc(L.prep)} ${r.prep} ${esc(L.min)} · ${esc(L.total)} ${r.total} ${esc(L.min)} · ${esc(r.machine)}</div>
<h4>${esc(L.ing)}</h4>${r.groups.map(g=>`${g.name?`<div class="g">${esc(g.name)}</div>`:""}<ul>${g.items.map(i=>`<li>${esc(i)}</li>`).join("")}</ul>`).join("")}
<h4>${esc(L.steps)}</h4><ol class="steps">${r.steps.map(stepHtml).join("")}</ol>
${r.hints.length?`<h4>${esc(L.hints)}</h4><ul>${r.hints.map(h=>`<li>${esc(h)}</li>`).join("")}</ul>`:""}
${r.warnings.length?`<div class="warn"><b>${esc(L.warn)}:</b> ${r.warnings.map(esc).join(" · ")}</div>`:""}
<div class="actions"><button class="btn p" id="cp">Für Cookidoo kopieren</button>
${r.cookidoo?`<a class="btn" href="${esc(r.cookidoo)}" target="_blank" rel="noopener">In Cookidoo öffnen</a>`:""}
${r.source?`<a class="btn" href="${esc(r.source)}" target="_blank" rel="noopener">${esc(L.src)}</a>`:""}
<button class="btn" onclick="window.print()">Drucken</button></div>`;
document.getElementById("cp").onclick=async e=>{try{await navigator.clipboard.writeText(r.copy);e.target.textContent="Kopiert ✓"}catch(_){e.target.textContent="Kopieren nicht möglich"}};
document.getElementById("dlg").showModal();}
const dlg=document.getElementById("dlg");
draw();
</script></body></html>"""


def to_html(recipes: list[Recipe], title: str = "Tunesisches Thermomix-Kochbuch",
            subtitle: str | None = None, artifact: bool = False) -> str:
    data = [_recipe_dict(r) for r in recipes]
    sub = subtitle or f"{len(recipes)} Rezepte · Guided Cooking für TM5 / TM6 / TM7"
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = (TEMPLATE.replace("__TITLE__", html.escape(title))
           .replace("__SUB__", html.escape(sub)).replace("__DATA__", payload))
    return _as_artifact(out) if artifact else out


def _as_artifact(page: str) -> str:
    """Variant for a hosted viewer: no document skeleton, no print button,
    safe-area gutters and sticky offset."""
    import re
    page = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>", "", page, flags=re.I)
    page = page.replace('<meta charset="utf-8">', "").replace(
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="claude:viewport-fit-sides" content="cover">')
    page = page.replace("</head><body>", "").replace("</body></html>", "")
    page = page.replace('<button class="btn" onclick="window.print()">Drucken</button>', "")
    page = page.replace(".bar{position:sticky;top:0;", ".bar{position:sticky;top:env(safe-area-inset-top,0px);")
    gutter = "padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))"
    page = page.replace("header{padding:48px 16px 28px;", f"header{{padding-block:48px 28px;{gutter};")
    page = page.replace(".bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}",
                        f".bar{{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding-block:12px;{gutter}}}")
    page = page.replace("main{max-width:1080px;margin:0 auto;padding:20px 16px 64px}",
                        f"main{{max-width:1080px;margin:0 auto;padding-block:20px 64px;{gutter}}}")
    page = page.replace("</style>", 'body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--bg)}\n</style>')
    return page
