"""Generate properly formatted PDF reports from markdown source files."""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Preformatted,
)
from reportlab.lib import colors


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "H1Custom",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=14,
        spaceBefore=6,
        textColor=colors.HexColor("#1a1a2e"),
    ))
    styles.add(ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=12,
        textColor=colors.HexColor("#16213e"),
    ))
    styles.add(ParagraphStyle(
        "H3Custom",
        parent=styles["Heading3"],
        fontSize=12,
        spaceAfter=8,
        spaceBefore=10,
        textColor=colors.HexColor("#0f3460"),
    ))
    styles.add(ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        "BlockQuote",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        leftIndent=24,
        rightIndent=12,
        spaceAfter=6,
        spaceBefore=4,
        textColor=colors.HexColor("#333333"),
        backColor=colors.HexColor("#f5f5f5"),
        borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        "CodeBlock",
        fontName="Courier",
        fontSize=8,
        leading=10,
        leftIndent=18,
        spaceAfter=8,
        spaceBefore=4,
        backColor=colors.HexColor("#f0f0f0"),
    ))
    return styles


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _md_inline(text: str) -> str:
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', text)
    return text


def _parse_table(lines: list[str], styles) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= set("- :") for c in cells):
            continue
        rows.append([_md_inline(c) for c in cells])

    if not rows:
        return Spacer(1, 0)

    para_rows = []
    for row in rows:
        para_rows.append([Paragraph(c, styles["BodyCustom"]) for c in row])

    ncols = max(len(r) for r in para_rows)
    col_width = (6.5 * inch) / ncols
    t = Table(para_rows, colWidths=[col_width] * ncols)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def md_to_elements(md_text: str, styles) -> list:
    elements: list = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            elements.append(Spacer(1, 4))
            i += 1
            continue

        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(code_lines)
            elements.append(Preformatted(_escape(code), styles["CodeBlock"]))
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            elements.append(_parse_table(table_lines, styles))
            elements.append(Spacer(1, 6))
            continue

        if stripped.startswith("# "):
            elements.append(Paragraph(_md_inline(stripped[2:]), styles["H1Custom"]))
            i += 1
            continue
        if stripped.startswith("## "):
            elements.append(Paragraph(_md_inline(stripped[3:]), styles["H2Custom"]))
            i += 1
            continue
        if stripped.startswith("### "):
            elements.append(Paragraph(_md_inline(stripped[4:]), styles["H3Custom"]))
            i += 1
            continue

        if stripped.startswith("> "):
            quote_text = stripped[2:]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_text += " " + lines[i].strip()[2:]
                i += 1
            elements.append(Paragraph(_md_inline(quote_text), styles["BlockQuote"]))
            continue

        if stripped.startswith("- "):
            bullet_text = stripped[2:]
            elements.append(Paragraph(
                f"&bull; {_md_inline(bullet_text)}",
                ParagraphStyle("Bullet", parent=styles["BodyCustom"], leftIndent=18, bulletIndent=6),
            ))
            i += 1
            continue

        para_text = stripped
        i += 1
        while i < len(lines):
            next_stripped = lines[i].strip()
            if (not next_stripped or next_stripped.startswith("#") or
                next_stripped.startswith("|") or next_stripped.startswith(">") or
                next_stripped.startswith("```") or next_stripped.startswith("- ")):
                break
            para_text += " " + next_stripped
            i += 1
        elements.append(Paragraph(_md_inline(para_text), styles["BodyCustom"]))

    return elements


def generate_pdf(md_path: str, pdf_path: str) -> None:
    md_text = Path(md_path).read_text(encoding="utf-8")
    styles = _build_styles()
    elements = md_to_elements(md_text, styles)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(elements)


if __name__ == "__main__":
    generate_pdf("report/report.md", "report/report.pdf")
    print("Generated report/report.pdf")
    generate_pdf("report/ai_use_appendix.md", "report/ai_use_appendix.pdf")
    print("Generated report/ai_use_appendix.pdf")
