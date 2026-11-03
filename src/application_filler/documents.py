from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def render_letter(markdown: str, directory: Path) -> tuple[Path, Path]:
    """A restricted Markdown renderer: paragraphs, headings, bullets. No HTML or remote assets."""
    if not markdown.strip() or len(markdown) > 20000:
        raise ValueError("Cover letter must contain 1–20,000 characters")
    directory.mkdir(parents=True, exist_ok=True)
    md = directory / "cover-letter.md"
    pdf = directory / "cover-letter.pdf"
    styles = getSampleStyleSheet()
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    font = next((p for p in candidates if p.is_file()), None)
    if font is None:
        raise ValueError("Unicode PDF font unavailable; use the Docker image")
    if "LetterFont" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("LetterFont", str(font)))
    for style in styles.byName.values():
        style.fontName = "LetterFont"
        style.leading = 16
    story = []
    for block in markdown.strip().split("\n\n"):
        style = styles["BodyText"]
        if block.startswith("# "):
            block, style = block[2:], styles["Heading1"]
        elif block.startswith("## "):
            block, style = block[3:], styles["Heading2"]
        story.extend([Paragraph(escape(block).replace("\n", "<br/>"), style), Spacer(1, 8)])
    SimpleDocTemplate(
        str(pdf),
        title="Cover letter",
        author="",
        leftMargin=50,
        rightMargin=50,
        topMargin=45,
        bottomMargin=45,
    ).build(story)
    if not pdf.read_bytes().startswith(b"%PDF-"):
        raise ValueError("PDF rendering failed")
    md.write_text(markdown.strip() + "\n", encoding="utf-8")
    return md, pdf


def remove_generated(paths: list[Path], root: Path) -> None:
    for path in paths:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Generated-file cleanup escaped its directory")
        path.unlink(missing_ok=True)
