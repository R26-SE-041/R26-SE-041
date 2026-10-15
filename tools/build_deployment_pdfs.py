"""Build and render the four repository-based deployment reports."""
from pathlib import Path
import html
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tmp/pdfs/deployment-runtime"))

import pymupdf as fitz
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUT = ROOT / "output/pdf"
QA = ROOT / "tmp/pdfs/deployment-reports"
OUT.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)
BLUE = colors.HexColor("#16466A")
WIDTH = A4[0] - 96
STYLES = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=14, spaceAfter=8),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=BLUE, spaceAfter=17),
    "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=BLUE, spaceBefore=13, spaceAfter=8, keepWithNext=True),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=11.5, spaceAfter=0, splitLongWords=True),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8, leading=11.5, spaceAfter=0, splitLongWords=True),
}


def normalize(text):
    return text.replace("—", "-").replace("–", "-").replace("‑", "-")


def inline(text):
    text = normalize(text.strip())
    links = []
    def link(match):
        label, target = match.groups()
        if not target.startswith("https://"):
            target = (ROOT / "deployment-reports" / target).resolve().relative_to(ROOT).as_posix()
            target = "https://github.com/R26-SE-041/R26-SE-041/blob/main/" + target
        links.append((label, target))
        return f"PDFLINK{len(links)-1}TOKEN"
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    for index, (label, target) in enumerate(links):
        text = text.replace(f"PDFLINK{index}TOKEN", f'<a href="{html.escape(target, quote=True)}" color="#16466A"><u>{html.escape(label)}</u></a>')
    return text


def paragraph(text, kind="body"):
    return Paragraph(inline(text), STYLES[kind])


def table(rows):
    count = len(rows[0])
    if count == 2:
        widths = [WIDTH * .42, WIDTH * .58]
    else:
        widths = [WIDTH * .22, WIDTH * .32, WIDTH * .46]
    data = [[paragraph(cell, "cell") for cell in row] for row in rows]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3EEF5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("LINEBELOW", (0, 0), (-1, 0), .7, BLUE),
        ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#DCE2E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return result


def parse(source):
    lines = source.splitlines()
    story = []
    i = 0
    while i < len(lines):
        value = lines[i].strip()
        if not value:
            i += 1
            continue
        if value.startswith("# "):
            story.append(paragraph(value[2:], "title"))
        elif value.startswith("## "):
            story.append(paragraph(value[3:], "heading"))
        elif value.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append(cells)
                i += 1
            story.extend([table(rows), Spacer(1, 10)])
            continue
        elif value.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].strip())
                i += 1
            block = Table([[Paragraph(html.escape(normalize(x)), STYLES["code"])] for x in code], colWidths=[WIDTH])
            block.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F3F6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.extend([block, Spacer(1, 10)])
        else:
            story.append(paragraph(value))
        i += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#DCE2E8"))
    canvas.line(48, A4[1]-34, A4[0]-48, A4[1]-34)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(BLUE)
    canvas.drawString(48, A4[1]-26, "BioLearnX  |  R26-SE-041")
    canvas.drawRightString(A4[0]-48, A4[1]-26, "Component Deployment Report")
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(48, 29, "Repository-based report  |  14 October 2026")
    canvas.drawRightString(A4[0]-48, 29, f"Page {doc.page}")
    canvas.restoreState()


summary = []
for source in sorted((ROOT / "deployment-reports").glob("0*-deployment-report.md")):
    target = OUT / (source.stem + ".pdf")
    source_text = source.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=48, rightMargin=48,
                            topMargin=51, bottomMargin=48,
                            title=normalize(source_text.splitlines()[0][2:]),
                            author="BioLearnX - R26-SE-041")
    doc.build(parse(source_text), onFirstPage=footer, onLaterPages=footer)
    pages = fitz.open(target)
    thumbnails = []
    all_text = ""
    for index, page in enumerate(pages):
        all_text += page.get_text()
        for block in page.get_text("blocks"):
            if block[0] < 40 or block[2] > A4[0]-40 or block[1] < 15 or block[3] > A4[1]-15:
                raise RuntimeError(f"Out-of-bounds text: {target.name}, page {index+1}")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.1, 1.1), alpha=False)
        preview = QA / f"{source.stem}-page-{index+1}.png"
        pixmap.save(preview)
        thumb = Image.open(preview).convert("RGB")
        thumb.thumbnail((440, 630))
        thumbnails.append(thumb)
    for section in range(1, 8):
        if f"{section}. " not in all_text:
            raise RuntimeError(f"Missing section {section}: {target.name}")
    sheet = Image.new("RGB", (900, ((len(thumbnails)+1)//2)*660), "#DCE2E8")
    draw = ImageDraw.Draw(sheet)
    for index, thumb in enumerate(thumbnails):
        x, y = (index % 2)*450+5, (index//2)*660+20
        sheet.paste(thumb, (x, y))
        draw.text((x, y-15), f"Page {index+1}", fill="black")
    sheet.save(QA / f"{source.stem}-contact.png")
    summary.append({"file": str(target), "pages": len(pages), "bytes": target.stat().st_size})
    pages.close()
(QA / "validation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
