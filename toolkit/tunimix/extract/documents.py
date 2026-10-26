"""Open-source extraction for everything that isn't a recipe web page:

  .docx          python-docx  (paragraphs, lists, tables, embedded photo)
  .pdf           pdfplumber   (text; embedded photo) -> Tesseract OCR for scanned pages (pypdfium2 render)
  .jpg/.png/…    Tesseract OCR via pytesseract (de/fr/en/ar if the language packs are installed)
  .txt/.md/.html plain text / readable HTML

…and a rule-based structurer that turns loose recipe text (OCR output, a Word document, a blog
without schema.org) into {title, ingredients, instructions, yields}.
"""
from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..convert.ingredients import AMOUNT, UNIT_ALIASES, fold

# ---------------- structuring loose text ----------------
H_ING = re.compile(r"^\W*(zutaten|ingredients?|ingrédients|ingredientes|المكونات|المقادير|مقادير)\b.{0,40}$", re.I)
H_STEPS = re.compile(r"^\W*(zubereitung|anleitung|so geht'?s|instructions?|method|methode|directions|preparation|"
                     r"préparation|étapes|etapes|recette|طريقة التحضير|التحضير|الطريقة|طريقة)\b.{0,30}$", re.I)
H_OTHER = re.compile(r"^\W*(tipps?|tips?|notes?|astuces?|conseils?|nährwerte|nutrition|serving|à savoir|نصائح)\b.{0,30}$", re.I)
H_GROUP = re.compile(r"^(für (den|die|das)\b.{2,40}|pour (la|le|les|l')\b.{2,40}|for the\b.{2,40}|.{2,40}:)$", re.I)
NUMBERED = re.compile(r"^\s*(?:\d{1,2}|[a-z])\s*[.)\-:]\s+|^\s*(?:schritt|étape|step)\s*\d+\s*[:.)-]?\s*", re.I)
YIELD = re.compile(r"(?:für|pour|serves|for|makes|ergibt|portionen?:?|personnes?:?|servings?:?)\s*(\d{1,2})\s*"
                   r"(?:personen|portionen|personnes|people|persons|servings|portions|stück|pieces|parts)?", re.I)
YIELD2 = re.compile(r"(\d{1,2})\s*(?:personen|portionen|personnes|people|servings|portions|أشخاص|اشخاص)", re.I)
UNIT_WORDS = sorted({a for a in UNIT_ALIASES if len(a) > 1}, key=len, reverse=True)
QTY_START = re.compile(rf"^\s*[-•*·–]?\s*({AMOUNT})", re.I)
VERBISH = re.compile(r"\b(geben|zugeben|kochen|garen|rühren|schneiden|hacken|mixen|backen|braten|add|cook|stir|mix|"
                     r"bake|chop|boil|simmer|ajouter|cuire|mélanger|melanger|couper|faire|laisser|mettre|verser)\b", re.I)


def _is_ingredient_line(line: str) -> bool:
    if len(line) > 90 or line.endswith(".") and len(line) > 40:
        return False
    if QTY_START.match(line):
        return True
    f = fold(line)
    if re.match(r"^[-•*·–]\s*\S", line) and len(line) < 60 and not VERBISH.search(line):
        return True
    if any(f.startswith(u + " ") for u in ("prise", "pincee", "pinch", "etwas", "un peu", "some", "sel", "salz", "salt")):
        return True
    return False


def _join_wrapped(lines: list[str]) -> list[str]:
    """OCR / PDF break steps across lines: re-join until a sentence or a numbered step ends."""
    out: list[str] = []
    for ln in lines:
        if out and not NUMBERED.match(ln) and not re.search(r"[.!?:]$", out[-1]) and not ln[:1].isdigit():
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return [NUMBERED.sub("", x).strip() for x in out if x.strip()]


def structure_text(text: str, title: str = "") -> dict:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln and not re.fullmatch(r"[\W_]+", ln)]
    data = {"title": title, "ingredients": [], "instructions": [], "yields": "", "description": ""}
    m = YIELD.search(text) or YIELD2.search(text)
    if m:
        data["yields"] = m.group(1)
    i_ing = next((i for i, ln in enumerate(lines) if H_ING.match(ln)), None)
    i_stp = next((i for i, ln in enumerate(lines) if H_STEPS.match(ln) and (i_ing is None or i > i_ing)), None)
    if not data["title"]:
        for ln in lines[: (i_ing if i_ing is not None else 6)]:
            if 2 < len(ln) < 80 and not H_ING.match(ln) and not _is_ingredient_line(ln) and not YIELD2.search(ln):
                data["title"] = ln.strip("#* ")
                break
    if i_ing is not None:
        end = i_stp if i_stp is not None else len(lines)
        block = lines[i_ing + 1:end]
        steps_block = lines[i_stp + 1:] if i_stp is not None else []
        if i_stp is None:  # no step heading: ingredients until the first sentence-like line
            k = next((j for j, ln in enumerate(block) if not _is_ingredient_line(ln) and not H_GROUP.match(ln) and len(ln) > 40), len(block))
            block, steps_block = block[:k], block[k:]
    else:
        block = [ln for ln in lines if _is_ingredient_line(ln)]
        steps_block = [ln for ln in lines if not _is_ingredient_line(ln) and ln != data["title"]
                       and (NUMBERED.match(ln) or len(ln) > 35)]
    for ln in block:
        if H_OTHER.match(ln):
            break
        if H_GROUP.match(ln) and not QTY_START.match(ln):
            data["ingredients"].append("## " + ln.rstrip(":"))
        else:
            data["ingredients"].append(ln.lstrip("-•*·– ").strip())
    steps = []
    for ln in steps_block:
        if H_OTHER.match(ln):
            break
        if not H_GROUP.match(ln) or len(ln) > 40:
            steps.append(ln)
    data["instructions"] = _join_wrapped(steps)
    return data


# ---------------- readers ----------------
@dataclass
class Extracted:
    text: str = ""
    title: str = ""
    images: list[tuple[bytes, str]] = field(default_factory=list)   # (bytes, extension)
    ocr: bool = False


def ocr_languages() -> str:
    wanted = os.getenv("TUNIMIX_OCR_LANGS", "deu+fra+eng+ara").split("+")
    try:
        import pytesseract
        have = set(pytesseract.get_languages(config=""))
        langs = [lang for lang in wanted if lang in have] or ["eng"]
    except Exception:
        langs = ["eng"]
    return "+".join(langs)


def ocr_image(img) -> str:
    try:
        import pytesseract
        from PIL import ImageOps
    except ImportError as exc:
        raise RuntimeError("OCR needs `pip install pytesseract pillow` and the Tesseract program "
                           "(Windows: UB-Mannheim installer, macOS: brew install tesseract, "
                           "Linux: apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ara).") from exc
    g = ImageOps.exif_transpose(img).convert("L")
    if max(g.size) < 1800:
        f = 1800 / max(g.size)
        g = g.resize((int(g.width * f), int(g.height * f)))
    g = ImageOps.autocontrast(g)
    try:
        return pytesseract.image_to_string(g, lang=ocr_languages(), config="--psm 4")
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR is not installed – see README (Install OCR).") from exc


def read_image(data: bytes) -> Extracted:
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    return Extracted(text=ocr_image(img), ocr=True)


def read_docx(data: bytes) -> Extracted:
    import docx  # python-docx
    d = docx.Document(io.BytesIO(data))
    lines, title = [], ""
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        if not title and ("title" in style or "heading 1" in style or "titel" in style):
            title = t
        numbered = p._p.pPr is not None and p._p.pPr.numPr is not None
        lines.append(("- " if numbered and len(t) < 70 else "") + t)
    for table in d.tables:  # ingredient tables: "200 g | Mehl"
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" ".join(dict.fromkeys(cells)))
    images = []
    for rel in d.part.rels.values():
        if "image" in rel.reltype:
            blob = rel.target_part.blob
            ext = Path(rel.target_part.partname).suffix.lstrip(".") or "jpg"
            images.append((blob, ext))
    images.sort(key=lambda x: len(x[0]), reverse=True)
    return Extracted(text="\n".join(lines), title=title, images=images[:1])


def read_pdf(data: bytes) -> Extracted:
    import pdfplumber
    texts, images = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:15]:
            texts.append(page.extract_text() or "")
    text = "\n".join(texts)
    try:  # largest embedded photo
        from pypdf import PdfReader
        best = None
        for page in PdfReader(io.BytesIO(data)).pages[:5]:
            for im in page.images:
                if best is None or len(im.data) > len(best.data):
                    best = im
        if best is not None and len(best.data) > 20000:
            images.append((best.data, Path(best.name).suffix.lstrip(".") or "jpg"))
    except Exception:
        pass
    if len(text.strip()) >= 80:
        return Extracted(text=text, images=images)
    # scanned PDF -> render pages and OCR them
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    ocr = [ocr_image(doc[i].render(scale=2.5).to_pil()) for i in range(min(len(doc), 6))]
    return Extracted(text="\n".join(ocr), images=images, ocr=True)


def read_html(data: bytes) -> Extracted:
    from .web import readable_text
    title, text = readable_text(data.decode("utf-8", "ignore"))
    return Extracted(text=text, title=title)


READERS = {".docx": read_docx, ".pdf": read_pdf, ".html": read_html, ".htm": read_html,
           ".jpg": read_image, ".jpeg": read_image, ".png": read_image, ".webp": read_image, ".tif": read_image,
           ".tiff": read_image, ".bmp": read_image, ".gif": read_image, ".heic": read_image}


def read_document(data: bytes, filename: str) -> Extracted:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md", ""):
        return Extracted(text=data.decode("utf-8", "ignore"))
    if ext == ".heic":
        try:
            import pillow_heif  # type: ignore
            pillow_heif.register_heif_opener()
        except ImportError as exc:
            raise RuntimeError("HEIC photos need `pip install pillow-heif` (or export as JPEG).") from exc
    if ext == ".doc":
        raise RuntimeError("Old .doc files: save as .docx (Word/LibreOffice → Save as) and try again.")
    reader = READERS.get(ext)
    if not reader:
        raise RuntimeError(f"Unsupported file type {ext}")
    return reader(data)
