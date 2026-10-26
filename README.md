# TuniMix 🇹🇳 · any recipe into your Thermomix

**→ https://aminost.github.io/tunimix/**

Paste a link, type a dish name, upload a photo of grandma's handwritten recipe, or press the
TuniMix button on any recipe page. TuniMix turns it into a **Thermomix guided-cooking recipe**
("5 Min./100°C/Linkslauf/Stufe 1"). One more click saves it to **your Cookidoo "Created recipes"**,
and it appears on your TM5 / TM6 / TM7.

- **Any AI.** One-click conversion with Claude, OpenAI/ChatGPT, Google Gemini, OpenRouter (300+
  models, some free), Groq, Mistral, DeepSeek, any OpenAI-compatible endpoint, or **free and local
  with Ollama or LM Studio**. Without any key, the free route copies the instruction into any AI
  chat and pastes the answer back.
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

## AI providers

Settings → *AI for converting* → choose a provider, enter the key (not needed locally), press
**Load models**, then **Test**.

| Provider | Key | Opens links itself | Notes |
|---|---|---|---|
| Anthropic Claude | yes | ✓ (web fetch + search) | best results; also reads PDFs natively |
| OpenAI, Gemini, OpenRouter, Groq, Mistral, DeepSeek | yes | via reader* | OpenAI-compatible API, JSON mode with automatic fallback |
| **Ollama** (local) | no | via reader* | free, private; schema-constrained output; vision models read photos |
| LM Studio (local) | no | via reader* | enable CORS in LM Studio |
| Other OpenAI-compatible (vLLM, LocalAI, LiteLLM …) | optional | via reader* | set the base URL |

\* Links are read through the `r.jina.ai` reader (can be switched off), or you can skip it with the
TuniMix button, which sends the page content directly. Dish names without Claude are written from
the model's culinary knowledge and flagged as such. PDFs are read in the browser (text PDFs; for
scans use a photo).

### Ollama in 3 steps

1. Install Ollama and pull a model: `ollama pull qwen3:8b` (vision: `gemma3:12b` or `qwen2.5vl`).
2. Allow the website to talk to Ollama, then restart Ollama:
   - Windows: `setx OLLAMA_ORIGINS "https://aminost.github.io"`
   - macOS: `launchctl setenv OLLAMA_ORIGINS "https://aminost.github.io"`
   - Linux: `OLLAMA_ORIGINS="https://aminost.github.io" ollama serve`
3. In TuniMix Settings, choose **Ollama**, press **Load models**, pick one, press **Test**. If Chrome
   asks to allow access to your local network, allow it.

Small models (≤3B) often produce broken recipes. 7–14B models work well, and TuniMix validates and
retries automatically. Ollama on another machine (NAS, PC) works by changing the base URL, e.g.
`http://192.168.178.20:11434`; some browsers block non-local `http` addresses from an `https` page.

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

- No server, no tracking. Your recipes, your API keys (if you add any) and the Cookidoo queue live
  in your browser's local storage. A key is sent only to the provider you chose. With Ollama or
  LM Studio nothing leaves your computer except the link-reader call, which you can switch off.
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
| `ai.js` | AI providers from the browser: Claude (with web fetch/search), any OpenAI-compatible API, native Ollama |
| `bookmarklet.js` | the TuniMix button (capture on recipe pages, save on Cookidoo) |
| `bridge.html` | hands queued recipes to the button on Cookidoo |
| `recipes/` | community cookbook (one JSON per recipe + `index.json`) |
| `.github/` | recipe submission form, publish Action, tests |
| `toolkit/` | Python toolkit: CLI, local web app, Telegram bot, Claude Desktop (MCP) server, PDF cookbook – same providers incl. Ollama (`TUNIMIX_PROVIDER`) |

## Disclaimer

TuniMix is an unofficial, non-commercial open-source project. It is **not affiliated with,
endorsed by, or connected to Vorwerk**. Thermomix® and Cookidoo® are registered trademarks of the
Vorwerk group. Cookidoo has no public API. TuniMix uses the same internal requests as the Cookidoo
website, which can change at any time. Use it with your own account, for personal use, and within
Cookidoo's terms of use. You need an active Cookidoo subscription for "Created recipes".

## License

MIT, © 2026 Mohamed Amine Guedria and contributors. Community recipes remain the property of
their authors and are shared for personal, non-commercial use.
