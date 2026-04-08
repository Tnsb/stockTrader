"""Append a rendered LangGraph workflow figure to report/report.pdf (assignment: graph in report)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer


def _strip_mmd_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return text.strip()


def render_mermaid_png(mmd_path: Path, png_path: Path) -> None:
    """Render Mermaid to PNG using @mermaid-js/mermaid-cli (npx). Falls back if PNG already exists."""
    body = _strip_mmd_frontmatter(mmd_path.read_text(encoding="utf-8"))
    tmp_mmd = mmd_path.parent / "_langgraph_render.mmd"
    tmp_mmd.write_text(body + "\n", encoding="utf-8")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx",
        "--yes",
        "@mermaid-js/mermaid-cli@11.4.0",
        "-i",
        str(tmp_mmd),
        "-o",
        str(png_path),
        "-b",
        "white",
        "-w",
        "2400",
        "-H",
        "1800",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(mmd_path.parent.parent))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        if png_path.is_file():
            print("mermaid-cli failed; using existing", png_path, file=sys.stderr)
            return
        raise RuntimeError(
            "Could not render Mermaid to PNG. Install Node/npm and run again, or place a pre-rendered "
            f"PNG at {png_path}"
        ) from exc


def build_workflow_image_pdf(png_path: Path, out_pdf: Path) -> None:
    page_size = landscape(LETTER)
    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=page_size,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading2"],
        fontSize=11,
        spaceAfter=8,
    )
    ir = ImageReader(str(png_path))
    iw, ih = ir.getSize()
    aspect = ih / float(iw)
    max_w = doc.width
    # Leave room for title + spacing on one landscape page
    max_h = doc.height - 0.95 * inch
    w = max_w
    h = w * aspect
    if h > max_h:
        h = max_h
        w = h / aspect
    story = [
        KeepTogether(
            [
                Paragraph(
                    "Figure: LangGraph workflow (rendered from <b>outputs/langgraph_workflow.mmd</b>)",
                    title_style,
                ),
                Spacer(1, 8),
                RLImage(str(png_path), width=w, height=h),
            ]
        )
    ]
    doc.build(story)


def _strip_existing_diagram_pages(pages: list) -> list:
    """Remove pages we added in a previous run (raw Mermaid text and/or rendered figure)."""
    out = list(pages)
    while out:
        last = out[-1].extract_text() or ""
        prev = (out[-2].extract_text() or "") if len(out) >= 2 else ""
        if "graph TD" in last or "graph TD;" in last:
            out.pop()
            continue
        if "Figure: LangGraph workflow" in last and "rendered from" in last:
            out.pop()
            continue
        if "Figure: LangGraph workflow" in prev and not last.strip():
            out.pop()
            continue
        if "LangGraph workflow (Mermaid" in last and "outputs/langgraph_workflow.mmd" in last:
            out.pop()
            continue
        break
    return out


def merge_into_report(report_pdf: Path, workflow_pdf: Path) -> None:
    reader = PdfReader(str(report_pdf))
    writer = PdfWriter()
    pages = _strip_existing_diagram_pages(list(reader.pages))
    for p in pages:
        writer.add_page(p)
    wf_reader = PdfReader(str(workflow_pdf))
    for p in wf_reader.pages:
        writer.add_page(p)
    tmp = report_pdf.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(report_pdf)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    mmd = root / "outputs" / "langgraph_workflow.mmd"
    report_pdf = root / "report" / "report.pdf"
    png_path = root / "report" / "workflow_graph.png"
    wf_pdf = root / "report" / "_workflow_page.pdf"
    if not mmd.is_file():
        raise FileNotFoundError(mmd)
    if not report_pdf.is_file():
        raise FileNotFoundError(report_pdf)

    render_mermaid_png(mmd, png_path)
    build_workflow_image_pdf(png_path, wf_pdf)
    merge_into_report(report_pdf, wf_pdf)
    wf_pdf.unlink(missing_ok=True)
    print(f"Embedded workflow figure in {report_pdf} (PNG: {png_path})")


if __name__ == "__main__":
    main()
