"""Export a saved Markdown analysis report as a readable PDF."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.utils import ImageReader


_IMAGE_PATTERN = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_ORDERED_LIST_PATTERN = re.compile(r"^\s*\d+[.)、]\s+(.+)$")
_BULLET_LIST_PATTERN = re.compile(r"^\s*[-*+]\s+(.+)$")
_SUPERSCRIPT_PATTERN = re.compile(r"[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_SUPERSCRIPT_TRANSLATION = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")


def _register_report_font() -> str:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyh.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("AcademicReport", str(candidate), subfontIndex=0))
            return "AcademicReport"
        except Exception:
            continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def _inline_markup(value: str) -> str:
    normalized = _SUPERSCRIPT_PATTERN.sub(lambda match: f"^{match.group(0).translate(_SUPERSCRIPT_TRANSLATION)}", value.strip())
    escaped = html.escape(normalized)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<font color='#5b554d'>\1</font>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<link href='\2' color='#2f6f58'>\1</link>", escaped)
    return escaped


def _resolve_image_path(target: str, *, project_root: Path, run_dir: Path) -> Path | None:
    value = target.strip().strip("<>")
    parsed = urlparse(value)
    if parsed.path.endswith("/api/files"):
        path_values = parse_qs(parsed.query).get("path", [])
        if path_values:
            value = unquote(path_values[0])
    candidate = Path(value)
    choices = [candidate] if candidate.is_absolute() else [project_root / candidate, run_dir / candidate]
    for choice in choices:
        try:
            resolved = choice.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def _fit_image(path: Path, *, max_width: float, max_height: float) -> Image:
    width, height = ImageReader(str(path)).getSize()
    scale = min(max_width / max(width, 1), max_height / max(height, 1), 1.0)
    image = Image(str(path), width=width * scale, height=height * scale)
    image.hAlign = "CENTER"
    return image


def export_markdown_report_pdf(
    markdown_path: str | Path,
    pdf_path: str | Path,
    *,
    project_root: str | Path,
    run_id: str,
) -> Path:
    """Render a stored Markdown report and its local figures to an A4 PDF."""

    source = Path(markdown_path).resolve()
    destination = Path(pdf_path).resolve()
    root = Path(project_root).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    destination.parent.mkdir(parents=True, exist_ok=True)
    font_name = _register_report_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "AcademicBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.2,
        leading=17,
        textColor=colors.HexColor("#292724"),
        spaceAfter=7,
        wordWrap="CJK",
    )
    heading_styles = {
        1: ParagraphStyle("AcademicH1", parent=body, fontSize=22, leading=30, spaceBefore=0, spaceAfter=18, textColor=colors.HexColor("#1f1e1c")),
        2: ParagraphStyle("AcademicH2", parent=body, fontSize=16, leading=23, spaceBefore=18, spaceAfter=9, textColor=colors.HexColor("#1f1e1c")),
        3: ParagraphStyle("AcademicH3", parent=body, fontSize=13, leading=20, spaceBefore=13, spaceAfter=7, textColor=colors.HexColor("#282622")),
    }
    caption = ParagraphStyle("AcademicCaption", parent=body, fontSize=8.5, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#777168"), spaceAfter=10)
    code_style = ParagraphStyle("AcademicCode", parent=body, fontName=font_name, fontSize=8, leading=12, leftIndent=8, rightIndent=8, borderPadding=7, borderColor=colors.HexColor("#e4e0d8"), borderWidth=.5, backColor=colors.HexColor("#f5f3ef"), spaceBefore=5, spaceAfter=9)

    def draw_page(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#8a847b"))
        canvas.drawString(18 * mm, 12 * mm, run_id)
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"第 {document.page} 页")
        canvas.setStrokeColor(colors.HexColor("#e5e1d9"))
        canvas.line(18 * mm, 17 * mm, A4[0] - 18 * mm, 17 * mm)
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=23 * mm,
        title=run_id,
        author="Academic Agent",
    )
    story = []
    list_buffer: list[tuple[str, bool]] = []
    paragraph_buffer: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            story.append(Paragraph(_inline_markup(" ".join(paragraph_buffer)), body))
            paragraph_buffer.clear()

    def flush_list() -> None:
        if not list_buffer:
            return
        ordered = list_buffer[0][1]
        items = [ListItem(Paragraph(_inline_markup(text), body), leftIndent=8) for text, _ in list_buffer]
        story.append(ListFlowable(items, bulletType="1" if ordered else "bullet", leftIndent=18, bulletFontName=font_name, bulletFontSize=9, spaceAfter=7))
        list_buffer.clear()

    lines = source.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                story.append(Paragraph("<br/>".join(html.escape(item) or "&nbsp;" for item in code_lines), code_style))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue

        image_match = _IMAGE_PATTERN.match(line)
        heading_match = _HEADING_PATTERN.match(line)
        ordered_match = _ORDERED_LIST_PATTERN.match(line)
        bullet_match = _BULLET_LIST_PATTERN.match(line)
        if image_match:
            flush_paragraph()
            flush_list()
            image_path = _resolve_image_path(image_match.group(2), project_root=root, run_dir=source.parent)
            if image_path:
                image = _fit_image(image_path, max_width=document.width, max_height=112 * mm)
                alt = image_match.group(1).strip() or image_path.name
                story.append(KeepTogether([image, Spacer(1, 3 * mm), Paragraph(html.escape(alt), caption)]))
            continue
        if heading_match:
            flush_paragraph()
            flush_list()
            level = min(len(heading_match.group(1)), 3)
            story.append(Paragraph(_inline_markup(heading_match.group(2)), heading_styles[level]))
            continue
        if ordered_match or bullet_match:
            flush_paragraph()
            item = ordered_match.group(1) if ordered_match else bullet_match.group(1)
            ordered = ordered_match is not None
            if list_buffer and list_buffer[-1][1] != ordered:
                flush_list()
            list_buffer.append((item, ordered))
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        if line.strip() == "---":
            flush_paragraph()
            flush_list()
            story.append(Spacer(1, 4 * mm))
            continue
        paragraph_buffer.append(line.strip())

    flush_paragraph()
    flush_list()
    if code_lines:
        story.append(Paragraph("<br/>".join(html.escape(item) or "&nbsp;" for item in code_lines), code_style))
    if not story:
        story.append(Paragraph("报告内容为空。", body))
    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return destination
