# TuniMix 🇹🇳 · any recipe into your Thermomix

**→ https://aminost.github.io/tunimix/**

Paste a link, type a dish name, upload a photo of grandma's handwritten recipe, or press the
TuniMix button on any recipe page. TuniMix turns it into a **Thermomix guided-cooking recipe**
("5 Min./100°C/Linkslauf/Stufe 1"). One more click saves it to **your Cookidoo "Created recipes"**,
and it appears on your TM5 / TM6 / TM7.

- **Free.** Convert through any AI chat (Claude, ChatGPT, Gemini) at no cost, or use your own
  Claude API key for one-click conversion (about 1–3 cents per recipe).
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

1. **Add a recipe.** Paste anything on the website, or press the TuniMix bookmark on a recipe page.
2. **Convert.** Use "Free with an AI chat" (copy, paste, paste back) or one click with your own key.
3. **Save to Cookidoo.** Open Cookidoo, press the same TuniMix bookmark, and the recipe is saved.

Setting up the button takes one minute: open the **Cookidoo button** tab and drag it to your
bookmarks bar.

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

- No server, no tracking. Your recipes, your API key (if you add one) and the Cookidoo queue live
  in your browser's local storage. The key is sent only to `api.anthropic.com`.
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
| `core.js` | recipe model, Thermomix rules, setting strings, Cookidoo payload (shared with tests & Action) |
| `ai.js` | Claude API from the browser (your key), with web fetch/search for links and dish names |
| `bookmarklet.js` | the TuniMix button (capture on recipe pages, save on Cookidoo) |
| `bridge.html` | hands queued recipes to the button on Cookidoo |
| `recipes/` | community cookbook (one JSON per recipe + `index.json`) |
| `.github/` | recipe submission form, publish Action, tests |
| `toolkit/` | Python toolkit: CLI, local web app, Telegram bot, Claude Desktop (MCP) server, PDF cookbook |

## Disclaimer

TuniMix is an unofficial, non-commercial open-source project. It is **not affiliated with,
endorsed by, or connected to Vorwerk**. Thermomix® and Cookidoo® are registered trademarks of the
Vorwerk group. Cookidoo has no public API. TuniMix uses the same internal requests as the Cookidoo
website, which can change at any time. Use it with your own account, for personal use, and within
Cookidoo's terms of use. You need an active Cookidoo subscription for "Created recipes".

## License

MIT, © 2026 Mohamed Amine Guedria and contributors. Community recipes remain the property of
their authors and are shared for personal, non-commercial use.
