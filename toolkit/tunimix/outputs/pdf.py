"""Printable PDF cookbook (cover, table of contents, one recipe per page)."""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from ..models import Recipe
from .text import grouped_ingredients, labels, rendered_steps, servings_label

BLUE = colors.HexColor("#1f5fa8")
TERRA = colors.HexColor("#b8502e")
OLIVE = colors.HexColor("#6b7d3a")
INK = colors.HexColor("#22201c")
MUTED = colors.HexColor("#6f675c")
CHIP = "#1f4f8a"

FONT_CANDIDATES = {
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
                "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "serif": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf",
              "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"],
}
ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+")


def _register_fonts() -> tuple[str, str, str]:
    names = {}
    for key, paths in FONT_CANDIDATES.items():
        for p in paths:
            if Path(p).exists():
                name = f"TM-{key}"
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    names[key] = name
                    break
                except Exception:
                    continue
    reg = names.get("regular", "Helvetica")
    bold = names.get("bold", "Helvetica-Bold")
    serif = names.get("serif", bold)
    return reg, bold, serif


def _latin(text: str) -> str:
    """Drop Arabic script (ReportLab cannot shape it) and tidy separators."""
    t = ARABIC.sub("", text or "")
    return re.sub(r"\s*[·|]\s*$", "", t).strip()


def _picture(path: str, max_w: float = 170 * mm, max_h: float = 85 * mm):
    """Recipe photo, scaled to fit (None if missing or unreadable)."""
    if not path or not Path(path).exists():
        return None
    try:
        from PIL import Image as PILImage
        from reportlab.platypus import Image
        with PILImage.open(path) as im:
            w, h = im.size
        scale = min(max_w / w, max_h / h)
        return Image(path, width=w * scale, height=h * scale)
    except Exception:
        return None


class _Doc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if getattr(flowable, "toc_entry", None):
            self.notify("TOCEntry", (0, flowable.toc_entry, self.page))


def build_pdf(recipes: list[Recipe], path: Path, title: str = "Tunesisches Thermomix-Kochbuch",
              subtitle: str = "Guided Cooking für TM5 · TM6 · TM7", author: str = "") -> Path:
    reg, bold, serif = _register_fonts()
    st = {
        "cover": ParagraphStyle("cover", fontName=serif, fontSize=34, leading=40, alignment=TA_CENTER, textColor=INK),
        "coversub": ParagraphStyle("cs", fontName=reg, fontSize=13, leading=18, alignment=TA_CENTER, textColor=MUTED),
        "cat": ParagraphStyle("cat", fontName=bold, fontSize=9, leading=12, textColor=TERRA),
        "h1": ParagraphStyle("h1", fontName=serif, fontSize=24, leading=29, textColor=INK, spaceAfter=2),
        "orig": ParagraphStyle("orig", fontName=reg, fontSize=11, leading=14, textColor=MUTED),
        "meta": ParagraphStyle("meta", fontName=reg, fontSize=9.5, leading=13, textColor=MUTED, spaceBefore=6),
        "body": ParagraphStyle("body", fontName=reg, fontSize=10.5, leading=15, textColor=INK),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=10, leading=14, textColor=OLIVE, spaceBefore=12, spaceAfter=4),
        "ing": ParagraphStyle("ing", fontName=reg, fontSize=10, leading=14, textColor=INK, leftIndent=8, bulletIndent=0),
        "grp": ParagraphStyle("grp", fontName=bold, fontSize=10, leading=14, textColor=INK, spaceBefore=4),
        "step": ParagraphStyle("step", fontName=reg, fontSize=10.5, leading=15, textColor=INK),
        "num": ParagraphStyle("num", fontName=bold, fontSize=11, leading=15, textColor=colors.white, alignment=TA_CENTER),
        "warn": ParagraphStyle("warn", fontName=reg, fontSize=8.5, leading=12, textColor=MUTED, spaceBefore=10),
        "toc": ParagraphStyle("toc", fontName=reg, fontSize=11, leading=18),
    }

    def page_deco(canvas, doc):
        canvas.saveState()
        canvas.setFont(reg, 8)
        canvas.setFillColor(MUTED)
        if doc.page > 1:
            canvas.drawCentredString(A4[0] / 2, 12 * mm, str(doc.page))
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(2)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.restoreState()

    story = [Spacer(1, 70 * mm), Paragraph(escape(title), st["cover"]), Spacer(1, 8 * mm),
             Paragraph(escape(subtitle), st["coversub"]), Spacer(1, 4 * mm),
             Paragraph(f"{len(recipes)} Rezepte" + (f" · {escape(author)}" if author else ""), st["coversub"]),
             PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [st["toc"]]
    story += [Paragraph("Inhalt", st["h1"]), Spacer(1, 6 * mm), toc, PageBreak()]

    for r in recipes:
        L = labels(r.language)
        head = Paragraph(escape(r.title), st["h1"])
        head.toc_entry = escape(r.title)
        block = [Paragraph(escape((r.category or "").upper()), st["cat"]), head]
        orig = _latin(r.original_title)
        if orig and orig.lower() != r.title.lower():
            block.append(Paragraph(escape(orig), st["orig"]))
        block.append(Paragraph(
            f"{servings_label(r)} · {L['prep']} {r.prep_time_min} {L['min']} · "
            f"{L['total']} {r.total_time_min} {L['min']} · {r.machine}", st["meta"]))
        if r.description:
            block += [Spacer(1, 4), Paragraph(escape(r.description), st["body"])]
        pic = _picture(r.image_file)
        if pic is not None:
            block += [Spacer(1, 6), pic]
        story.append(KeepTogether(block))

        story.append(Paragraph(L["ing"].upper(), st["h2"]))
        for group, items in grouped_ingredients(r):
            if group:
                story.append(Paragraph(escape(group), st["grp"]))
            for i in items:
                story.append(Paragraph(escape(i.line()), st["ing"], bulletText="•"))

        story.append(Paragraph(L["steps"].upper(), st["h2"]))
        for n, (text, setting, off) in enumerate(rendered_steps(r), 1):
            t = escape(text)
            if setting:
                t = t.replace(escape(setting), f'<font name="{bold}" color="{CHIP}">{escape(setting)}</font>', 1)
            if off:
                t += f' <font color="#b8502e" size="8.5">({escape(L["off"])})</font>'
            row = Table([[Paragraph(str(n), st["num"]), Paragraph(t, st["step"])]],
                        colWidths=[8 * mm, None])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, 0), BLUE),
                ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [row, Spacer(1, 3)]

        if r.hints:
            story.append(Paragraph(L["hints"].upper(), st["h2"]))
            for h in r.hints:
                story.append(Paragraph(escape(h), st["ing"], bulletText="•"))
        if r.warnings:
            story.append(Paragraph(f"<b>{escape(L['warn'])}:</b> " + escape(" · ".join(r.warnings)), st["warn"]))
        if r.source_url:
            story.append(Paragraph(f"{L['src']}: {escape(r.source_url)}", st["warn"]))
        story.append(PageBreak())

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = _Doc(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
               topMargin=20 * mm, bottomMargin=20 * mm, title=title, author=author or "TuniMix")
    doc.multiBuild(story, onFirstPage=page_deco, onLaterPages=page_deco)
    return path
