# TuniMix 🇹🇳 · any recipe into your Thermomix

**→ https://aminost.github.io/tunimix/**

[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-support%20TuniMix-1d4e9e?logo=ko-fi&logoColor=white)](https://ko-fi.com/aminoste)

Paste a link, type a dish name, upload a photo of grandma's handwritten recipe, or press the
TuniMix button on any recipe page. TuniMix turns it into a **Thermomix guided-cooking recipe**
("5 Min./100°C/Linkslauf/Stufe 1"). One more click saves it to **your Cookidoo "Created recipes"**,
and it appears on your TM5 / TM6 / TM7.

- **No AI needed.** By default, open-source tools read the recipe right in your browser: schema.org
  data from links, **pdf.js** for PDFs, **mammoth.js** for Word and **tesseract.js** OCR for photos.
  A Thermomix rules engine then writes the guided-cooking steps. It is free, needs no key and works
  offline once loaded.
- **Optional: free AI chat.** For a dish name without a recipe, or a translation, TuniMix copies a ready-made
  instruction for any AI chat (Claude, ChatGPT, Gemini). You paste the chat's answer back. No key and no account
  in TuniMix.
- **Nothing to install.** It's a web page, and it can be installed as an app on your phone.
- **No server, no account, no password sharing.** Everything runs in your browser. Cookidoo is
  reached through your own logged-in session.
- **Every link.** Because the button reads what your browser already shows, it also works on
  Instagram, TikTok, Facebook, sites that need JavaScript, and sites that block scrapers.
- **4 languages.** Deutsch, Français, English, العربية. Tunisian/Maghreb cuisine knowledge is built in.
- **Community cookbook.** Anyone can share their family recipes, and everyone can add them to
  Cookidoo in one click.

## How it works

```
 any recipe page ──(TuniMix button)──┐
 link / dish name / text / photo ────┼─► TuniMix web app ──► AI converts (free chat or own key)
                                     │        │  rules: ≤99 min per step, ≤2.2 L, Linkslauf for pieces …
                                     │        ▼
                                     │   queue in your browser
                                     │        │
 cookidoo.de ──(TuniMix button)──────┴────────┴─► saved to "Created recipes" with YOUR session
                                                  → appears on the Thermomix
```

1. **Add a recipe.** Paste a link or text, add a photo, PDF or Word file, or press the TuniMix
   bookmark on a recipe page.
2. **Convert.** Press **Umwandeln**. The rules engine runs without AI. If you want, there's
   also an optional free AI-chat route.
3. **Save to Cookidoo.** Open Cookidoo, press the same TuniMix bookmark, and the recipe is saved,
   **with its photo**. The photo is uploaded the same way the Cookidoo website does it
   (signature → Vorwerk's image service → attach to the recipe).

Setting up the button takes one minute: open the **Cookidoo button** tab and drag it to your
bookmarks bar. On a phone, save the **short code** from that tab as a bookmark and open it from the
address bar on Cookidoo.

## Python script (no AI needed)

`toolkit/` contains a command-line script that does everything **without AI**, using open-source
tools only. It reads links (with the recipe photo), Word, PDF and photos (Tesseract OCR), converts
them with a Thermomix rules engine and uploads to Cookidoo:

```bash
cd toolkit && pip install -r requirements.txt
python -m tunimix add "https://some-blog.tn/lablabi" --upload
python -m tunimix add mamas-rezept.docx rezept.pdf foto.jpg --upload
```

See [toolkit/README.md](toolkit/README.md#no-ai-needed).

## Is this new? What already exists

| | Converts any recipe | Saves to Cookidoo | Cost | How you log in to Cookidoo |
|---|---|---|---|---|
| **TuniMix** | ✓ link, dish, text, photo, PDF, social posts | ✓ one click (button) | free / own key | your own browser session, no password sharing |
| [Mixidoo](https://www.mixidoo.co.uk/) | ✓ links | ✓ | freemium (3/month free) | via their service |
| [AIdoo](https://aidoo.tools/convert-recipe) | ✓ text, PDF, URL | ✓ | not stated | via their service |
| [cookidoo-recipe-creator](https://github.com/guimatheus92/cookidoo-recipe-creator) | ✓ | ✓ | free | Claude Code + exported cookies (technical) |
| [miaucl/cookidoo-api](https://github.com/miaucl/cookidoo-api), [recode-software/cookidoo-api](https://github.com/recode-software/cookidoo-api) | ✗ (libraries only) | ✓ for developers | free | email + password in code |

What makes TuniMix different: it's free and needs no install or account, and your Cookidoo
password never leaves your browser. The button works on every site, including social media. It
has an Arabic interface and Tunisian/Maghreb cooking knowledge, plus an open community cookbook.

## Share a recipe with everyone

Convert a recipe, then click **"Share with everyone"**. This opens a pre-filled GitHub form; a free
GitHub account is needed. A maintainer reviews it and adds the label `approved`. A GitHub Action
then checks it with the same Thermomix rules and publishes it under **Community recipes**.

Please only share **your own or family recipes**, not text or photos copied from websites.

## Privacy & safety

- No server, no tracking. Your recipes and the Cookidoo queue live in your browser's local storage.
  Files (PDF, Word, photos) are read on your device. Only links typed into the box go through the
  `r.jina.ai` reader, which you can switch off; the TuniMix button doesn't need it. Recipe photos from
  the web are shrunk through the open-source `images.weserv.nl` image proxy before they go to Cookidoo.
- On Cookidoo, the button uses the same requests the Cookidoo website makes when you create a
  recipe yourself, with your own session. TuniMix never sees your login.
- Converted settings are checked automatically (temperature/speed limits, 99-minute timers,
  2.2 L bowl, Linkslauf for pieces). Still, review the **"Please check"** notes and do a test cook.

## Run your own copy / develop

It's a static site with no build step:

```bash
git clone https://github.com/Aminost/tunimix && cd tunimix
python3 -m http.server 8000         # open http://localhost:8000
node --test tests/*.test.mjs        # tests (no network)
node scripts/build-index.mjs        # rebuild recipes/index.json
```

Forks work automatically on `https://<you>.github.io/<repo>/`. The button and the share form
follow the address the site is served from.

| File | What it is |
|---|---|
| `index.html`, `app.js`, `i18n.js` | the web app |
| `core.js` | recipe model, Thermomix limits, setting strings, Cookidoo payload (shared with tests & Action) |
| `rules.js` | **rules engine without AI** (ingredient parser, action lexicon, Thermomix settings, text structurer), a 1:1 port of `toolkit/tunimix/convert/rulebased.py`, verified by `tests/rules-parity.test.mjs` |
| `docs.js` | reads PDF (pdf.js), Word (mammoth.js) and photos (tesseract.js OCR) in the browser |
| `bookmarklet.js` | the TuniMix button (capture on recipe pages, save on Cookidoo) |
| `bridge.html` | hands queued recipes to the button on Cookidoo |
| `recipes/` | community cookbook (one JSON per recipe + `index.json`) |
| `.github/` | recipe submission form, publish Action, tests |
| `toolkit/` | Python script: **rule-based conversion without AI** (links + photo, Word, PDF, OCR), Cookidoo upload, PDF cookbook, local web app, Telegram bot, MCP server; optional AI providers incl. Ollama |

## Disclaimer

TuniMix is an unofficial, non-commercial open-source project. It is **not affiliated with,
endorsed by, or connected to Vorwerk**. Thermomix® and Cookidoo® are registered trademarks of the
Vorwerk group. Cookidoo has no public API. TuniMix uses the same internal requests as the Cookidoo
website, which can change at any time. Use it with your own account, for personal use, and within
Cookidoo's terms of use. You need an active Cookidoo subscription for "Created recipes".

## Support

TuniMix is free, ad-free and open source. If it saves you time in the kitchen, you can buy me a
coffee on **[Ko-fi](https://ko-fi.com/aminoste)**.

## License

MIT, © 2026 Mohamed Amine Guedria and contributors. Community recipes remain the property of
their authors and are shared for personal, non-commercial use.
