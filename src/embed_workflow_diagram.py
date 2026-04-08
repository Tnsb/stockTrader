"""Append a LangGraph Mermaid workflow page to report/report.pdf (assignment: graph in report)."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Preformatted


def _strip_mmd_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            lines = lines[end + 1 :]
    return "\n".join(lines).strip()


def build_workflow_pdf(mmd_path: Path, out_path: Path) -> None:
    raw = mmd_path.read_text(encoding="utf-8")
    body = _strip_mmd_frontmatter(raw)

    page_size = landscape(LETTER)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=page_size,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=10,
    )
    code_style = ParagraphStyle(
        "C",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7,
        leading=8,
    )
    story = [
        Paragraph(
            "LangGraph workflow (Mermaid — same source as <b>outputs/langgraph_workflow.mmd</b>, "
            "render in any Mermaid viewer or GitHub)",
            title_style,
        ),
        Spacer(1, 6),
        Preformatted(body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), code_style),
    ]
    doc.build(story)


def merge_into_report(report_pdf: Path, workflow_pdf: Path) -> None:
    writer = PdfWriter()
    for path in (report_pdf, workflow_pdf):
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    tmp = report_pdf.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(report_pdf)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    mmd = root / "outputs" / "langgraph_workflow.mmd"
    report_pdf = root / "report" / "report.pdf"
    wf_pdf = root / "report" / "_workflow_page.pdf"
    if not mmd.is_file():
        raise FileNotFoundError(mmd)
    if not report_pdf.is_file():
        raise FileNotFoundError(report_pdf)
    build_workflow_pdf(mmd, wf_pdf)
    merge_into_report(report_pdf, wf_pdf)
    wf_pdf.unlink(missing_ok=True)
    print(f"Appended workflow diagram page to {report_pdf}")


if __name__ == "__main__":
    main()
