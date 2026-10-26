# TuniMix 🇹🇳 → Thermomix

Turn **any recipe** into a **Thermomix guided-cooking recipe** and build your Tunisian cookbook
in **Cookidoo** (Meine Kreationen), so it shows up on the TM5/TM6/TM7 with tappable settings.

```
 INPUTS                       CORE                                   OUTPUTS
 recipe link (any site) ─┐                                       ┌─ Cookidoo "Meine Kreationen" (auto upload)
 YouTube video ──────────┤   extract  →  convert (Claude)  →     ├─ PDF cookbook (cover, TOC, 1 recipe/page)
 dish name ("kafteji") ──┤   recipe-       Thermomix rules +     ├─ HTML cookbook (search, filter, offline)
 pasted text ────────────┤   scrapers,     Tunisian knowledge    ├─ Markdown
 photo / handwriting ────┤   JSON-LD,   →  safety validator   →  ├─ Copy-paste text (Cookidoo form / Rezeptwelt)
 PDF / scan ─────────────┤   vision        (≤99 min, 2.2 L,      ├─ schema.org JSON-LD (Mealie, Tandoor, Paprika…)
 batch file / folder ────┘                  Linkslauf …)         └─ your library: one JSON per recipe

 INTERFACES: CLI · web app (+ bookmarklet, phone) · Telegram bot · Claude Desktop (MCP) · claude.ai skill · watch folder · Docker
```

Comes with **9 Tunisian recipes already converted** (Ojja Merguez, Lablabi, Chorba Frik, Couscous
mit Hähnchen, Harissa, Salata Mechouia, Makroudh, Mloukhia, Tabil).

---

## 1. Install (5 minutes)

**Windows:** unzip, then double-click `start.bat`. It creates the environment, opens `.env` for you
to fill in, and starts the web app.

**macOS / Linux / Raspberry Pi:**
```bash
cd tunimix
./start.sh            # first run creates .env → fill it in → run again
```

**Manual setup:**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # fill in keys
python -m tunimix check
python -m tunimix seeds                             # loads the 9 Tunisian recipes
```

`.env` needs:

| Key | What for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | converting new recipes | console.anthropic.com → API Keys (not needed for the Claude Desktop route) |
| `COOKIDOO_EMAIL` / `COOKIDOO_PASSWORD` | uploading to Cookidoo | your Cookidoo login (active subscription) |
| `COOKIDOO_COUNTRY` / `COOKIDOO_LANGUAGE` | your Cookidoo site | `de` / `de-DE` for cookidoo.de |
| `TELEGRAM_BOT_TOKEN` | the bot (optional) | @BotFather on Telegram |

---

## 2. Every way to use it

### A. Command line
```bash
python -m tunimix add https://www.some-blog.tn/lablabi          # any recipe page
python -m tunimix add "https://youtu.be/xxxxxxxxxxx"            # YouTube recipe video
python -m tunimix add "kafteji"                                 # dish name → web search
python -m tunimix add "brik à l'oeuf" --kind knowledge          # no web, from culinary knowledge
python -m tunimix add mama_couscous.jpg                         # photo of a handwritten recipe
python -m tunimix add rezept.pdf --servings 6 --wish "weniger scharf"
python -m tunimix add <anything> --upload                       # …and push straight to Cookidoo
python -m tunimix batch links.example.txt --upload              # many at once (1 per line)

python -m tunimix list                                          # your library (☁ = on Cookidoo)
python -m tunimix show lablabi --format txt                     # md | txt | jsonld | json | cookidoo
python -m tunimix upload lablabi --dry-run                      # exact Cookidoo payload, no network
python -m tunimix upload --all                                  # whole book → Cookidoo
python -m tunimix cookidoo list                                 # what's in Meine Kreationen
python -m tunimix book --formats html,pdf,md,jsonld             # build cookbook into ./output
python -m tunimix watch "D:/GoogleDrive/Rezepte-Inbox" --upload # drop photos/links from the phone
```
Options: `--lang de|fr|en`, `--machine TM5|TM6|TM7`, `--servings N`, `--category Suppe`,
`--chips` (ingredient chips in Cookidoo, experimental).

### B. Web app (laptop or phone)
```bash
python -m tunimix web                                  # http://127.0.0.1:8765
python -m tunimix web --host 0.0.0.0                   # phone on the same Wi-Fi (set TUNIMIX_WEB_TOKEN!)
```
- Paste a link, type a dish name or text, or upload a photo/PDF → review → **Zu Cookidoo hochladen**.
- Download PDF / Markdown / Copy-Paste / schema.org, edit the JSON, browse the cookbook at `/book`.
- **Bookmarklet:** drag "+ Thermomix" from the home page into the bookmarks bar. One click on any
  recipe page imports it.
- **iPhone Shortcut / Android:** "Share → Shortcut" doing *Get contents of URL*
  `http://<pc-ip>:8765/api/convert` (POST JSON `{"value": "<shared URL>", "upload": true}`, header
  `X-Token: <your token>`). You can also open `http://<pc-ip>:8765/add?token=…&url=<shared URL>`.

### C. Telegram bot (best from the phone)
1. @BotFather → `/newbot` → put the token in `.env`.
2. `python -m tunimix bot`, send `/id` to your bot, and put the number in `TELEGRAM_ALLOWED_USER_IDS`.
3. Share any recipe link, dish name, photo or PDF to the bot → tap **☁ Zu Cookidoo** / **📄 PDF**.
   `/book` sends the full PDF cookbook, and `/uploadall` pushes everything new.

### D. Claude Desktop / Claude Code (no API key needed)
Add to `claude_desktop_config.json` (Settings → Developer → Edit config):
```json
{ "mcpServers": { "tunimix": {
    "command": "C:/path/to/tunimix/.venv/Scripts/python.exe",
    "args": ["-m", "tunimix", "mcp"],
    "cwd": "C:/path/to/tunimix" } } }
```
Then ask Claude: *"Find an authentic kammounia recipe, convert it for my TM6 and save it"*, and later
*"upload it to Cookidoo"*. Claude does the conversion itself. The tools validate, save, upload and
build the book.

### E. claude.ai skill (zero install)
Upload `claude-skill/tunisian-thermomix/` as a skill in claude.ai (Settings → Capabilities → Skills).
Any chat then converts recipes into paste-ready Cookidoo text.

### F. Always-on (NAS / Raspberry Pi / Docker)
```bash
docker build -t tunimix .
docker run -d --env-file .env -v $PWD/library:/app/library -p 8765:8765 tunimix web --host 0.0.0.0
docker run -d --env-file .env -v $PWD/library:/app/library tunimix bot
```

### G. Manual fallback (no automation)
`python -m tunimix show <recipe> --format txt` gives one line per Cookidoo field. Paste them into
cookidoo.de → Meine Kreationen → Rezept erstellen, or post on Rezeptwelt.de and use its
"add to Cookidoo" button.

---

## 3. How the conversion works

1. **Extract**: `recipe-scrapers` (500+ sites + schema.org wild mode) → own JSON-LD parser →
   readable page text. YouTube uses the transcript. Photos and PDFs go to Claude vision. Dish names
   use Claude web search, preferring Tunisian sources.
2. **Convert**: Claude (forced tool call, strict schema) applies Thermomix rules and Tunisian cuisine
   knowledge (tasbika, couscous in the Varoma, mloukhia long simmer, makroudh dough …).
3. **Validate** (`convert/rules.py`): snaps temperature and speed to real TM values and splits
   timers longer than 99 min. It adds Linkslauf for pieces, flags anything over 2.2 L and hot +
   fast settings, drops settings from oven/frying steps, and checks TM5 mode support. If the result
   is invalid, it goes back to Claude for a fix (up to 3 tries).
4. **Render**: each setting becomes a Cookidoo TTS/MODE annotation, so the Thermomix shows the
   tappable "5 Min./100°C/Linkslauf/Stufe 1" button.

Recipe files are plain JSON in `library/`. Edit them by hand or in the web app. In step texts,
`{S}` marks where the setting string goes, and `time_s` is in seconds.

---

## 4. Important notes

- **Cookidoo has no official API.** Uploading uses the community, reverse-engineered
  [`cookidoo-api`](https://github.com/miaucl/cookidoo-api). Vorwerk can change it at any time. Use
  it only for your own account and at low volume (uploads are spaced 12 s apart because the create
  endpoint rate-limits). If uploading ever breaks, everything else still works, and the copy-paste
  route remains.
- Cookidoo limits how many Created Recipes you can store, so check your account before mass imports.
- Review the **"Bitte prüfen"** notes on each converted recipe before cooking, and do a first test
  cook with new recipes.
- Your login token is cached in `.cookidoo_token.json`. Keep `.env` and that file private.

## 5. Tests
```bash
pip install pytest && python -m pytest -q     # 20 offline tests (no keys, no network)
```

## Project layout
```
tunimix/
  models.py          Recipe / Step / TMSetting (single source of truth)
  formatting.py      "5 Min./100°C/Linkslauf/Stufe 1" in de / en / fr
  extract/           web.py · video.py · media.py · search.py
  convert/           prompt.py (TM + Tunisian knowledge) · converter.py · rules.py
  outputs/           cookidoo.py · pdf.py · html.py · text.py (md, copy-paste, JSON-LD)
  interfaces/        web.py · telegram_bot.py · mcp_server.py
  pipeline.py        any input → saved recipe (→ Cookidoo)
  library.py · cli.py
seeds/               9 Tunisian recipes, already converted
claude-skill/        claude.ai skill
```
