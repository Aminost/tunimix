---
name: tunisian-thermomix
description: Convert any recipe (link, dish name, pasted text, photo of a handwritten recipe, PDF) into a Thermomix TM5/TM6/TM7 guided-cooking recipe, with Tunisian cuisine expertise, ready to paste into Cookidoo "Meine Kreationen".
---

# Tunisian Thermomix converter

Use when the user wants a recipe for their Thermomix, especially Tunisian/Maghreb dishes.

## Steps
1. Get the source:
   - Link → fetch the page and read ingredients and steps.
   - Dish name → search the web, Tunisian sources first (Tunisian blogs, French/Arabic Tunisian sites), pick one complete, authentic recipe and name it as the source.
   - Photo/PDF → read it, including handwriting and Arabic/French.
2. Convert it with the rules below. Default to German and TM6 unless the user says otherwise.
3. Output the result in the "Output format" below, so every line pastes straight into a Cookidoo field.
4. Offer the user the upload route: the TuniMix tool (`tunimix add …` or its MCP server) uploads automatically. Otherwise they paste the lines into cookidoo.de → Meine Kreationen → Rezept erstellen.

## Thermomix rules
- Bowl capacity 2.2 L and at most ~800 g meat. If the recipe is bigger, scale it down and say so.
- Temperatures: 37–120 °C or Varoma. Speeds: Sanftrührstufe, 0.5–10. Each timer is max 99 min, so split longer cooking into several steps.
- Use Linkslauf (reverse) for meat, chicken, chickpeas, potatoes, fish, eggs, or any pieces that must stay whole.
- Deep-frying, oven, grill, pan and shaping steps happen outside the Thermomix. Mark them "(außerhalb des Thermomix)".
- Proven settings:
  - Chop onion or garlic: 5 Sek./Stufe 5.
  - Sauté: 3 Min./120°C/Stufe 1.
  - Tasbika (tomato paste, harissa, spices): 3 Min./120°C/Linkslauf/Stufe 1.
  - Meat in sauce: 100°C/Linkslauf/Sanftrührstufe, 30–60 Min.
  - Dough: Teigknetstufe 2 Min.
  - Grind spices: 30 Sek.–1 Min./Stufe 10.
  - Purée soup: 1 Min./Stufe 5–10, increasing gradually.
  - Couscous: cook the marqa in the bowl, and steam the hydrated couscous in the Varoma on a damp cloth, 15 Min./Varoma.
  - Ojja eggs: 4 Min./90°C/Linkslauf/Sanftrührstufe.
  - Mloukhia: 3–5 h at 98°C, split into steps of 99 min or less.
- Write settings exactly in this notation: `5 Min./100°C/Linkslauf/Stufe 1`, `10 Sek./Stufe 5`, `20 Min./Varoma/Sanftrührstufe`, `2 Min./Teigknetstufe`.
- Keep Tunisian ingredient names and add a short explanation, e.g. "Tabil (tunesische Gewürzmischung)", "Frik (grüner geschroteter Weizen)".

## Output format
```
TITEL: <Titel> (<tunesischer Name · arabisch>)
PORTIONEN: <n>   ARBEITSZEIT: <min> Min.   GESAMTZEIT: <min> Min.   GERÄT: TM6

ZUTATEN (eine Zeile = ein Feld):
<Menge> <Einheit> <Zutat>, <Hinweis>
…

ZUBEREITUNG (eine Zeile = ein Schritt):
<Schritt mit Einstellung, z. B. "Zwiebel in den Mixtopf geben und 5 Sek./Stufe 5 zerkleinern.">
…

TIPPS:
…
BITTE PRÜFEN: <Unsicherheiten, skalierte Mengen>
QUELLE: <URL>
```
