"""Inspection PDF report generation (Milestone 8, Task 6 — first step).

Pure report-generation module: accepts structured report data and returns
PDF bytes in memory. Database access, authentication, R2 storage operations,
HTTP response handling, and inference stay outside this module; routers
assemble the data and persist or stream the produced bytes.

Design notes:
- ReportLab (Platypus) is used for layout, per the approved Task 6 audit:
  pure pip install, no system-level dependencies, BSD license.
- Branding follows the approved decision: text wordmark ``CrackSight AI``
  with navy ``#18313b`` and teal ``#167f78`` accents, matching the existing
  frontend design tokens (``frontend/src/index.css``).
- AI-generated predictions and inspector-recorded observations are drawn in
  separately labelled sub-sections (AI in teal, observation in navy).
- Measurements are image-space pixels only; the report never prints
  millimetres, centimetres, or any physical scale.
- Model version is displayed verbatim and clearly labelled as a checkpoint
  epoch value (no semantic version is invented).
- Photographs without a successful prediction, missing optional fields,
  corrupt image bytes, and inspections with zero photographs are all
  degraded gracefully with explicit placeholder wording.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

APP_NAME = "CrackSight AI"

# Brand colors (approved): matching frontend/src/index.css design tokens.
NAVY = HexColor("#18313b")
TEAL = HexColor("#167f78")
TEAL_DARK = HexColor("#116b65")
TEAL_PALE = HexColor("#e8f4f1")
AMBER = HexColor("#a76e21")
RED = HexColor("#bd4d47")
SUBTLE = HexColor("#94a0a5")
LINE = HexColor("#e4e9e7")

NAVY_HEX = "#18313b"
TEAL_DARK_HEX = "#116b65"
SUBTLE_HEX = "#94a0a5"
AMBER_HEX = "#a76e21"
RED_HEX = "#bd4d47"

PAGE_WIDTH, PAGE_HEIGHT = A4
_MARGIN = 46.0
_HEADER_BASELINE = PAGE_HEIGHT - 44.0
_HEADER_RULE_Y = _HEADER_BASELINE - 12.0
_TOP_MARGIN = 68.0
_BOTTOM_MARGIN = 58.0
_FOOTER_RULE_Y = 42.0
_FOOTER_BASELINE = 32.0
_FRAME_WIDTH = PAGE_WIDTH - 2 * _MARGIN

_FOOTER_NOTE = "AI-assisted inspection aid — predictions require professional review."

# Approved disclaimer wording, taken verbatim from the existing ReportsPage
# prototype (frontend/src/pages/ReportsPage.tsx report-sheet disclaimer).
DEFAULT_DISCLAIMER_HTML = (
    "<b>Limitations:</b> AI-assisted crack predictions are not a structural "
    "safety assessment and do not replace qualified structural engineering "
    "review. Measurements are image-space pixels only; no physical scale "
    "is implied."
)

_VERIFICATION_LABELS = {
    "not_verified": "Not verified",
    "correct": "Correct",
    "incorrect": "Incorrect",
    "partial": "Partial",
}

_VERIFICATION_COLORS = {
    "not_verified": SUBTLE_HEX,
    "correct": TEAL_DARK_HEX,
    "incorrect": RED_HEX,
    "partial": AMBER_HEX,
}

_STATUS_LABELS = {
    "draft": "Draft",
    "completed": "Completed",
}

_STRUCTURE_LABELS = {
    "wall": "Wall",
    "beam": "Beam",
    "column": "Column",
}

_NOT_PROVIDED = "Not provided"
_NOT_RECORDED = "Not recorded"
_NOT_AVAILABLE = "Not available"


# ---------------------------------------------------------------------------
# Structured report data
# ---------------------------------------------------------------------------

@dataclass
class PhotographReportEntry:
    """One photograph row as it should appear in the report.

    ``original_image`` and ``overlay_image`` carry raw image bytes (as
    stored in R2 by the upload/analysis flow); a caller may pass ``None``
    when the asset is missing or unavailable. Missing assets render as
    explicit placeholders — the generator never fabricates content.
    """

    photo_id: str
    structure_type: str
    verification_status: str = "not_verified"
    observation: Optional[str] = None
    model_version: Optional[str] = None
    prediction_timestamp: Optional[datetime] = None
    pixel_measurements: Optional[Dict[str, Any]] = None
    original_image: Optional[bytes] = None
    overlay_image: Optional[bytes] = None


@dataclass
class InspectionReportData:
    """Inspection-level information for the report."""

    inspection_id: str
    title: str
    status: str
    created_at: datetime
    building_type: Optional[str] = None
    building_location: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    photographs: List[PhotographReportEntry] = field(default_factory=list)


@dataclass
class ReportMetadata:
    """Report identity metadata (report ID and generation time)."""

    report_id: str
    generated_at: datetime


# ---------------------------------------------------------------------------
# Shared small helpers
# ---------------------------------------------------------------------------

def _format_datetime(value: Optional[datetime]) -> str:
    """Format a datetime for the report without inventing values."""
    if value is None:
        return _NOT_PROVIDED
    if value.tzinfo is not None:
        rendered = value.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
        if rendered:
            return rendered
    return value.isoformat(sep=" ", timespec="seconds")


def _format_option(value: Optional[str]) -> str:
    """Format an optional free-text field."""
    if value is None or value.strip() == "":
        return _NOT_PROVIDED
    return value.strip()


def _verification_markup(status: str) -> str:
    """Return a colored verification-status label as Paragraph markup."""
    label = _VERIFICATION_LABELS.get(status, status)
    color = _VERIFICATION_COLORS.get(status, SUBTLE_HEX)
    return f'<font color="{color}">{xml_escape(label)}</font>'


def _inspection_status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def _structure_label(structure_type: str) -> str:
    return _STRUCTURE_LABELS.get(structure_type, structure_type)


# ---------------------------------------------------------------------------
# ReportLab styles and branded page decorations
# ---------------------------------------------------------------------------

class _BrandedPageCanvas(Canvas):
    """Canvas that adds the report header band and footer (with page
    numbering ``Page X of Y``) to every page at save time.

    The two-pass approach records each finished page's state and replays it
    once the total page count is known, so footers can state the total.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_states: List[dict] = []

    def showPage(self) -> None:
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total_pages = len(self._page_states)
        for index, state in enumerate(self._page_states, start=1):
            self.__dict__.update(state)
            self._draw_branding(page_number=index, total_pages=total_pages)
            Canvas.showPage(self)
        Canvas.save(self)

    def _draw_branding(self, page_number: int, total_pages: int) -> None:
        # --- Header band (every page) ---
        self.setFillColor(TEAL)
        self.rect(_MARGIN, _HEADER_BASELINE, 10.0, 10.0, stroke=0, fill=1)
        self.setFillColor(NAVY)
        self.setFont("Helvetica-Bold", 11)
        self.drawString(_MARGIN + 15, _HEADER_BASELINE + 1, APP_NAME)
        self.setFillColor(SUBTLE)
        self.setFont("Helvetica", 8)
        self.drawRightString(PAGE_WIDTH - _MARGIN, _HEADER_BASELINE + 2, "Inspection report")
        self.setStrokeColor(TEAL)
        self.setLineWidth(1.1)
        self.line(_MARGIN, _HEADER_RULE_Y, PAGE_WIDTH - _MARGIN, _HEADER_RULE_Y)

        # --- Footer (every page): persistent safety note + page numbers ---
        self.setStrokeColor(LINE)
        self.setLineWidth(0.75)
        self.line(_MARGIN, _FOOTER_RULE_Y, PAGE_WIDTH - _MARGIN, _FOOTER_RULE_Y)
        self.setFillColor(SUBTLE)
        self.setFont("Helvetica", 8)
        self.drawString(_MARGIN, _FOOTER_BASELINE, _FOOTER_NOTE)
        self.drawRightString(
            PAGE_WIDTH - _MARGIN,
            _FOOTER_BASELINE,
            f"Page {page_number} of {total_pages}",
        )


def _build_styles() -> Dict[str, ParagraphStyle]:
    """Build the paragraph styles used by the report (fresh per generation)."""
    base_font = "Helvetica"
    return {
        "title": ParagraphStyle(
            "report_title",
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=NAVY,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "report_subtitle",
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            textColor=TEAL_DARK,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "report_section",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=NAVY,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "photo_heading": ParagraphStyle(
            "photo_heading",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=NAVY,
            spaceBefore=2,
            spaceAfter=3,
        ),
        "ai_heading": ParagraphStyle(
            "ai_heading",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=TEAL_DARK,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "observer_heading": ParagraphStyle(
            "observer_heading",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "report_body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=NAVY,
        ),
        "body_soft": ParagraphStyle(
            "report_body_soft",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=SUBTLE,
        ),
        "label": ParagraphStyle(
            "report_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "cell": ParagraphStyle(
            "report_cell",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "image_caption": ParagraphStyle(
            "image_caption",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=SUBTLE,
            alignment=TA_CENTER,
            spaceBefore=2,
        ),
    }


# ---------------------------------------------------------------------------
# Flowable builders
# ---------------------------------------------------------------------------

def _paragraph_table(rows: List[List[str]], label_width: float, styles: Dict[str, ParagraphStyle]) -> Table:
    """Build a two-column label/value table with subtle grid lines."""
    data = [
        [Paragraph(xml_escape(label), styles["label"]), Paragraph(value, styles["cell"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[label_width, _FRAME_WIDTH - label_width])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (0, -1), TEAL_PALE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _image_flowable(image_bytes: Optional[bytes], max_width: float, max_height: float) -> Optional[Image]:
    """Create a proportionally scaled image flowable.

    Returns ``None`` when the bytes are missing or not decodable so the
    caller can substitute an explicit placeholder paragraph.
    """
    if not image_bytes:
        return None
    buffer = io.BytesIO(image_bytes)
    try:
        reader = ImageReader(buffer)
        image_width, image_height = reader.getSize()
    except Exception:  # pylint: disable=broad-except
        return None
    if image_width <= 0 or image_height <= 0:
        return None
    scale = min(max_width / image_width, max_height / image_height)
    return Image(
        buffer,
        width=image_width * scale,
        height=image_height * scale,
    )


def _placeholder_paragraph(text: str, styles: Dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(
        f'<font color="{SUBTLE_HEX}"><i>{xml_escape(text)}</i></font>',
        styles["cell"],
    )


def _image_pair_flowables(
    entry: PhotographReportEntry,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    """Two-column table with the original photograph and the predicted overlay."""
    half_width = (_FRAME_WIDTH - 8) / 2
    image_width = half_width - 12
    original = _image_flowable(entry.original_image, image_width, 300.0)
    overlay = _image_flowable(entry.overlay_image, image_width, 300.0)

    left: List[Flowable] = []
    if original is not None:
        left.append(original)
        left.append(Paragraph(xml_escape("Original photograph"), styles["image_caption"]))
    else:
        left.append(_placeholder_paragraph("Original photograph not available", styles))
        left.append(Paragraph(xml_escape("Original photograph"), styles["image_caption"]))

    right: List[Flowable] = []
    if overlay is not None:
        right.append(overlay)
        right.append(Paragraph(xml_escape("AI-predicted overlay (mask blended on original)"), styles["image_caption"]))
    else:
        right.append(_placeholder_paragraph("Predicted overlay not available", styles))
        right.append(Paragraph(xml_escape("AI-predicted overlay (mask blended on original)"), styles["image_caption"]))

    table = Table([[left, right]], colWidths=[half_width + 4, half_width + 4])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _measurement_lines(measurements: Optional[Dict[str, Any]]) -> List[str]:
    """Human-readable image-space measurement lines (pixels only)."""
    if not measurements:
        return [f"Pixel measurements: {_NOT_AVAILABLE}"]

    crack_pixel_count = measurements.get("crack_pixel_count")
    if crack_pixel_count is not None:
        try:
            count_value = int(crack_pixel_count)
        except (TypeError, ValueError):
            count_value = None
        if count_value == 0:
            return ["No crack pixels were detected in this photograph."]

    lines: List[str] = []
    if crack_pixel_count is not None:
        try:
            lines.append(f"• Crack pixels: {int(crack_pixel_count):,}")
        except (TypeError, ValueError):
            lines.append(f"• Crack pixels: {crack_pixel_count}")

    coverage = measurements.get("crack_pixel_percentage")
    if coverage is not None:
        try:
            lines.append(f"• Crack coverage: {float(coverage):.2f}% of the image")
        except (TypeError, ValueError):
            lines.append(f"• Crack coverage: {coverage}")

    region_count = measurements.get("region_count")
    if region_count is not None:
        try:
            lines.append(f"• Crack regions: {int(region_count)}")
        except (TypeError, ValueError):
            lines.append(f"• Crack regions: {region_count}")

    bounding_box = measurements.get("bounding_box")
    if isinstance(bounding_box, dict):
        min_x = bounding_box.get("min_x")
        max_x = bounding_box.get("max_x")
        min_y = bounding_box.get("min_y")
        max_y = bounding_box.get("max_y")
        if None not in (min_x, max_x, min_y, max_y):
            lines.append(
                f"• Bounding box (image coordinates): "
                f"x {min_x}–{max_x}, y {min_y}–{max_y}"
            )

    if not lines:
        return [f"Pixel measurements: {_NOT_AVAILABLE}"]
    return lines


def _photo_flowables(
    index: int,
    entry: PhotographReportEntry,
    styles: Dict[str, ParagraphStyle],
) -> List[Flowable]:
    """Build all flowables for one photograph's report block."""
    heading = Paragraph(
        f"Photograph {index} — {xml_escape(_structure_label(entry.structure_type))}",
        styles["photo_heading"],
    )
    info_line = Paragraph(
        f'Structure type: {xml_escape(_structure_label(entry.structure_type))} · '
        f"Verification status: {_verification_markup(entry.verification_status)}",
        styles["body"],
    )

    prediction_lines = [
        f"Model version (checkpoint epoch): {xml_escape(str(entry.model_version)) if entry.model_version else _NOT_RECORDED}",
        f"Prediction time: {_format_datetime(entry.prediction_timestamp)}",
        "<b>Image-space measurements (pixels)</b>",
    ]
    prediction_lines.extend(xml_escape(line) if not line.startswith("•") else line for line in _measurement_lines(entry.pixel_measurements))
    ai_block: List[Flowable] = [
        Paragraph("AI-assisted prediction (model output — requires verification)", styles["ai_heading"]),
        Paragraph("<br/>".join(prediction_lines), styles["body"]),
    ]

    observation_text = (
        xml_escape(entry.observation)
        if entry.observation is not None and entry.observation.strip() != ""
        else f'<font color="{SUBTLE_HEX}"><i>No observation recorded.</i></font>'
    )
    observation_block: List[Flowable] = [
        Paragraph("Inspector observation (recorded by inspector)", styles["observer_heading"]),
        Paragraph(observation_text, styles["body"]),
    ]

    divider: Flowable = HRFlowable(
        width="100%",
        thickness=0.75,
        color=LINE,
        spaceBefore=10,
        spaceAfter=8,
    )

    return [
        heading,
        info_line,
        Spacer(1, 4),
        _image_pair_flowables(entry, styles),
        Spacer(1, 2),
    ] + ai_block + observation_block + [divider]


def _summary_flowables(report_data: InspectionReportData, styles: Dict[str, ParagraphStyle]) -> List[Flowable]:
    """Photograph summary section."""
    photographs = report_data.photographs
    if not photographs:
        note: List[Flowable] = [
            Paragraph("Photographs analysed: 0", styles["body"]),
            Spacer(1, 3),
            Paragraph("No photographs were analysed for this inspection.", styles["body_soft"]),
        ]
        return note

    counts: Dict[str, int] = {}
    for entry in photographs:
        counts[entry.structure_type] = counts.get(entry.structure_type, 0) + 1
    breakdown = ", ".join(
        f"{_structure_label(structure_type)} ×{count}"
        for structure_type, count in sorted(counts.items())
    )

    return [
        Paragraph(f"Photographs analysed: {len(photographs)} ({breakdown})", styles["body"]),
        Spacer(1, 3),
        Paragraph(
            "AI-generated predictions and inspector-recorded observations are "
            "labelled separately throughout this report. Predictions require "
            "verification before being relied upon.",
            styles["body_soft"],
        ),
        Spacer(1, 4),
    ]


def _disclaimer_flowables(
    disclaimer_html: str,
    styles: Dict[str, ParagraphStyle],
) -> List[Flowable]:
    """Limitations and safety-disclaimer section (pale background box)."""
    heading = Paragraph("Limitations and safety disclaimer", styles["section"])
    body = Paragraph(disclaimer_html, styles["body"])
    box = Table([[body]], colWidths=[_FRAME_WIDTH - 2])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL_PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, TEAL_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [heading, box, Spacer(1, 6)]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_inspection_report_pdf(
    report_data: InspectionReportData,
    report_metadata: ReportMetadata,
    *,
    disclaimer_html: str = DEFAULT_DISCLAIMER_HTML,
    page_count_sink: Optional[List[int]] = None,
) -> bytes:
    """Generate the inspection PDF report and return it as bytes.

    Raises nothing under normal operation for missing or corrupt
    *optional* content (degraded gracefully with placeholders); unexpected
    ReportLab errors propagate to the caller.

    ``page_count_sink`` is an optional list; after a successful build the
    total page count is appended to it so the caller can persist the
    available page count without parsing the PDF.
    """
    styles = _build_styles()
    story: List[Flowable] = []

    # --- Title block ---
    story.append(Paragraph("Inspection Report", styles["title"]))
    story.append(Paragraph(xml_escape(report_data.title), styles["subtitle"]))

    # --- Report metadata + inspection identification ---
    metadata_rows = [
        ("Report ID", xml_escape(str(report_metadata.report_id))),
        ("Generated at", _format_datetime(report_metadata.generated_at)),
        ("Inspection ID", xml_escape(str(report_data.inspection_id))),
        ("Inspection status", xml_escape(_inspection_status_label(report_data.status))),
    ]
    story.append(_paragraph_table(metadata_rows, 110.0, styles))
    story.append(Spacer(1, 10))

    # --- Inspection information ---
    story.append(Paragraph("Inspection information", styles["section"]))
    inspection_rows = [
        ("Title", xml_escape(_format_option(report_data.title))),
        ("Building type", xml_escape(_format_option(report_data.building_type))),
        ("Building location", xml_escape(_format_option(report_data.building_location))),
        ("Created at", _format_datetime(report_data.created_at)),
        ("Completed at", _format_datetime(report_data.completed_at)),
    ]
    story.append(_paragraph_table(inspection_rows, 110.0, styles))
    story.append(Spacer(1, 6))
    notes = _format_option(report_data.notes)
    story.append(
        Paragraph(
            f'<b>Notes:</b> {xml_escape(notes)}' if notes != _NOT_PROVIDED
            else f'<font color="{SUBTLE_HEX}"><i>Notes: none recorded.</i></font>',
            styles["body"],
        )
    )
    story.append(Spacer(1, 8))

    # --- Photograph summary ---
    story.append(Paragraph("Photograph summary", styles["section"]))
    story.extend(_summary_flowables(report_data, styles))

    # --- Per-photograph blocks ---
    for index, entry in enumerate(report_data.photographs, start=1):
        story.extend(_photo_flowables(index, entry, styles))

    # --- Limitations and safety disclaimer ---
    story.extend(_disclaimer_flowables(disclaimer_html, styles))

    buffer = io.BytesIO()
    canvas_holder: Dict[str, Any] = {}

    def _canvasmaker(*args, **kwargs):
        canvas = _BrandedPageCanvas(*args, **kwargs)
        canvas_holder["canvas"] = canvas
        return canvas

    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
        title=f"{APP_NAME} inspection report",
        author=APP_NAME,
        creator=APP_NAME,
        subject="AI-assisted crack inspection report",
    ).build(story, canvasmaker=_canvasmaker)

    if page_count_sink is not None:
        canvas = canvas_holder.get("canvas")
        page_count_sink.append(
            len(canvas._page_states) if canvas is not None else 0
        )

    return buffer.getvalue()
