"""Command line: `python -m tunimix <command>` (or `tunimix <command>` after pip install -e .)

Examples
  tunimix seeds                                   # load the bundled Tunisian recipes
  tunimix add https://example.com/ojja-recipe     # link -> Thermomix recipe
  tunimix add "kafteji"                           # dish name -> searched on the web
  tunimix add "brik à l'oeuf" --kind knowledge    # no web, written from culinary knowledge
  tunimix add mama_rezept.jpg --upload            # photo -> recipe -> Cookidoo
  tunimix batch links.txt --upload                # one link / dish per line
  tunimix upload ojja-merguez --dry-run           # show the exact Cookidoo payload
  tunimix upload --all                            # push the whole book to Cookidoo
  tunimix book --formats html,pdf                 # build the cookbook files
  tunimix watch ~/Drive/Rezepte-Inbox --upload    # drop photos/links into a synced folder
  tunimix web | bot | mcp                         # start the web app / Telegram bot / MCP server
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .config import settings
from .library import Library


def _opts(a):
    from .pipeline import Options
    return Options(language=a.lang, machine=a.machine, servings=a.servings, wishes=a.wish or "",
                   kind=a.kind, upload=a.upload, ingredient_chips=a.chips, category=a.category or "")


def _print_recipe(r, prefix="✓"):
    up = f"  → Cookidoo: {r.cookidoo_url}" if r.cookidoo_url else ""
    print(f"{prefix} {r.title}  [{r.slug}]  {r.servings} Port., {r.total_time_min} Min., {len(r.steps)} Schritte{up}")
    for w in r.warnings:
        print(f"    ! {w}")


def cmd_add(a):
    from .pipeline import process
    lib = Library()
    for value in a.inputs:
        try:
            r = process(value, _opts(a), lib)
            _print_recipe(r)
            if a.export:
                from .outputs import export_recipe
                for p in export_recipe(r, settings.output_dir, a.export.split(",")):
                    print(f"    → {p}")
        except Exception as exc:
            print(f"✗ {value}: {exc}", file=sys.stderr)


def cmd_batch(a):
    from .pipeline import process_batch

    def report(line, res):
        if isinstance(res, Exception):
            print(f"✗ {line}: {res}", file=sys.stderr)
        else:
            _print_recipe(res)
    process_batch(Path(a.file), _opts(a), Library(), on_result=report)


def cmd_list(a):
    rs = Library().all()
    if not rs:
        print("Library is empty. Try `tunimix seeds` or `tunimix add <link>`.")
    for r in rs:
        flag = "☁" if r.cookidoo_id else " "
        print(f"{flag} {r.slug:40} {r.category:14} {r.title}")


def cmd_show(a):
    from .outputs.text import to_copy_paste, to_jsonld_str, to_markdown
    r = Library().get(a.slug)
    if a.format == "md":
        print(to_markdown(r))
    elif a.format == "txt":
        print(to_copy_paste(r))
    elif a.format == "jsonld":
        print(to_jsonld_str(r))
    elif a.format == "cookidoo":
        from .outputs.cookidoo import preview_payload
        print(json.dumps(preview_payload(r, a.chips), ensure_ascii=False, indent=2))
    else:
        print(r.model_dump_json(indent=2))


def cmd_upload(a):
    lib = Library()
    recipes = lib.all() if a.all else [lib.get(s) for s in a.slugs]
    if not a.force:
        skipped = [r for r in recipes if r.cookidoo_id]
        recipes = [r for r in recipes if not r.cookidoo_id]
        for r in skipped:
            print(f"- {r.title}: already on Cookidoo (use --force to upload again)")
    if not recipes:
        return
    if a.dry_run:
        from .outputs.cookidoo import preview_payload
        for r in recipes:
            print(f"# {r.slug}\n" + json.dumps(preview_payload(r, a.chips), ensure_ascii=False, indent=2))
        return
    from .outputs.cookidoo import upload_many
    print(f"Uploading {len(recipes)} recipe(s), {settings.upload_delay_s:.0f}s apart …")

    def done(r):
        lib.save(r)
        _print_recipe(r, "☁")
    asyncio.run(upload_many(recipes, a.chips, on_done=done))


def cmd_cookidoo(a):
    from .outputs.cookidoo import CookidooClient

    async def run():
        async with CookidooClient() as c:
            if a.action == "list":
                for r in await c.list():
                    print(f"{r.id}  {r.name}  {r.url}")
            elif a.action == "delete":
                for rid in a.ids:
                    await c.delete(rid)
                    print(f"deleted {rid}")
            elif a.action == "login":
                print("Login OK – token saved.")
    asyncio.run(run())


def cmd_book(a):
    from .outputs import export_book
    rs = Library().all()
    if a.category:
        rs = [r for r in rs if r.category.lower() == a.category.lower()]
    if not rs:
        print("No recipes to export.")
        return
    out = Path(a.out or settings.output_dir)
    for p in export_book(rs, out, a.title, a.formats.split(","), a.author or ""):
        print(f"→ {p}")


def cmd_seeds(a):
    n = Library().import_seeds()
    print(f"Imported {n} Tunisian recipe(s) into {settings.library_dir}")


def cmd_watch(a):
    """Poll a folder: every new photo/PDF/.txt (links or dish names, one per line) is converted.
    Point it at a synced folder (NAS, Google Drive, iCloud) and drop files from your phone."""
    import time
    from .pipeline import process, process_bytes
    folder = Path(a.folder)
    done_dir = folder / "_done"
    done_dir.mkdir(parents=True, exist_ok=True)
    lib = Library()
    print(f"Watching {folder} (Ctrl+C to stop) …")
    while True:
        for f in sorted(folder.iterdir()):
            if f.is_dir() or f.name.startswith((".", "~")):
                continue
            try:
                if f.suffix.lower() == ".txt":
                    for line in f.read_text(encoding="utf-8").splitlines():
                        if line.strip() and not line.startswith("#"):
                            _print_recipe(process(line.strip(), _opts(a), lib))
                else:
                    _print_recipe(process_bytes(f.read_bytes(), f.name, _opts(a), lib))
                f.rename(done_dir / f.name)
            except Exception as exc:
                print(f"✗ {f.name}: {exc}", file=sys.stderr)
                f.rename(done_dir / f"FAILED-{f.name}")
        time.sleep(a.interval)


def cmd_check(a):
    ok = lambda b: "✓" if b else "✗"
    print(f"{ok(settings.anthropic_api_key)} ANTHROPIC_API_KEY   (needed to convert new recipes)")
    print(f"{ok(settings.cookidoo_email and settings.cookidoo_password)} COOKIDOO_EMAIL / PASSWORD (needed to upload)")
    print(f"{ok(settings.telegram_token)} TELEGRAM_BOT_TOKEN  (only for the bot)")
    print(f"  model={settings.model} language={settings.recipe_language} machine={settings.machine}")
    print(f"  cookidoo={settings.cookidoo_country}/{settings.cookidoo_language} library={settings.library_dir}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="tunimix", description="Any recipe → Thermomix → Cookidoo.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def conv_args(sp):
        sp.add_argument("--kind", choices=["url", "youtube", "search", "text", "file", "knowledge"])
        sp.add_argument("--lang", help="de | en | fr (default from .env)")
        sp.add_argument("--machine", choices=["TM5", "TM6", "TM7"])
        sp.add_argument("--servings", type=int)
        sp.add_argument("--wish", help='free text, e.g. "weniger scharf, mit Lamm"')
        sp.add_argument("--category", help="Hauptgericht, Suppe, Dessert …")
        sp.add_argument("--upload", action="store_true", help="also upload to Cookidoo")
        sp.add_argument("--chips", action="store_true", help="add ingredient chips (experimental)")

    s = sub.add_parser("add", help="convert links / dish names / files / text")
    s.add_argument("inputs", nargs="+")
    s.add_argument("--export", help="also write files: md,txt,jsonld,html,pdf,cookidoo-json")
    conv_args(s)
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("batch", help="convert every line of a text file")
    s.add_argument("file")
    conv_args(s)
    s.set_defaults(fn=cmd_batch)

    sub.add_parser("list", help="list your library").set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="print one recipe")
    s.add_argument("slug")
    s.add_argument("--format", default="md", choices=["md", "txt", "jsonld", "json", "cookidoo"])
    s.add_argument("--chips", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("upload", help="upload recipes to Cookidoo")
    s.add_argument("slugs", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("--force", action="store_true", help="upload even if already uploaded")
    s.add_argument("--dry-run", action="store_true", help="print payload, no network")
    s.add_argument("--chips", action="store_true")
    s.set_defaults(fn=cmd_upload)

    s = sub.add_parser("cookidoo", help="login | list | delete on Cookidoo")
    s.add_argument("action", choices=["login", "list", "delete"])
    s.add_argument("ids", nargs="*")
    s.set_defaults(fn=cmd_cookidoo)

    s = sub.add_parser("book", help="build the cookbook (HTML, PDF, Markdown, JSON-LD)")
    s.add_argument("--title", default="Tunesisches Thermomix-Kochbuch")
    s.add_argument("--author")
    s.add_argument("--formats", default="html,pdf,md,jsonld")
    s.add_argument("--category")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_book)

    s = sub.add_parser("watch", help="convert files dropped into a folder")
    s.add_argument("folder")
    s.add_argument("--interval", type=int, default=20)
    conv_args(s)
    s.set_defaults(fn=cmd_watch)

    sub.add_parser("seeds", help="import bundled Tunisian recipes").set_defaults(fn=cmd_seeds)
    sub.add_parser("check", help="check configuration").set_defaults(fn=cmd_check)

    s = sub.add_parser("web", help="start the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=lambda a: __import__("tunimix.interfaces.web", fromlist=["run"]).run(a.host, a.port))
    sub.add_parser("bot", help="start the Telegram bot").set_defaults(
        fn=lambda a: __import__("tunimix.interfaces.telegram_bot", fromlist=["run"]).run())
    sub.add_parser("mcp", help="start the MCP server (Claude Desktop)").set_defaults(
        fn=lambda a: __import__("tunimix.interfaces.mcp_server", fromlist=["run"]).run())

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(message)s")
    a.fn(a)


if __name__ == "__main__":
    main()
