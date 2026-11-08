"""Unit tests for the inspection PDF report generator (Milestone 8, Task 6).

The generator is a pure module: structured report data in, PDF bytes out.
Tests verify document structure and content via ``pypdf`` text extraction
(whitespace-normalised); they never assert byte positions or internal
compression details, so they are not brittle against incidental PDF changes.

Run with: ``PYTHONPATH=src python -m pytest tests/unit/test_report_generator.py``
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone

from PIL import Image

from crack_detection.backend.report_generator import (
    InspectionReportData,
    PhotographReportEntry,
    ReportMetadata,
    generate_inspection_report_pdf,
)

_INSPECTION_ID = "11111111-1111-4111-8111-111111111111"
_PHOTO_ID_A = "00000000-0000-4000-8000-000000000001"
_PHOTO_ID_B = "00000000-0000-4000-8000-000000000002"
_REPORT_ID = "22222222-2222-4222-8222-222222222222"

_CREATED_AT = datetime(2026, 11, 8, 9, 30, 0, tzinfo=timezone.utc)
_GENERATED_AT = datetime(2026, 11, 8, 14, 45, 0, tzinfo=timezone.utc)
_PREDICTED_AT = datetime(2026, 11, 8, 10, 15, 0, tzinfo=timezone.utc)

_DEFAULT_OBSERVATION = "Fine surface crack visible across wall finish."


def _png_bytes(color=(20, 130, 120), size=(64, 48)) -> bytes:
    """Create a small valid PNG in memory for embedding tests."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _measurements(**overrides):
    """Realistic pixel measurement dict matching the analysis service shape."""
    base = {
        "crack_pixel_count": 12345,
        "crack_pixel_percentage": 12.34,
        "bounding_box": {"min_x": 210, "min_y": 96, "max_x": 480, "max_y": 512},
        "region_count": 3,
    }
    base.update(overrides)
    return base


def _photo(**overrides) -> PhotographReportEntry:
    base = dict(
        photo_id=_PHOTO_ID_A,
        structure_type="wall",
        verification_status="not_verified",
        observation=_DEFAULT_OBSERVATION,
        model_version="120",
        prediction_timestamp=_PREDICTED_AT,
        pixel_measurements=_measurements(),
        original_image=_png_bytes(),
        overlay_image=_png_bytes((180, 20, 60)),
    )
    base.update(overrides)
    return PhotographReportEntry(**base)


def _inspection(photos=None, **overrides) -> InspectionReportData:
    base = dict(
        inspection_id=_INSPECTION_ID,
        title="Tower A facade survey",
        status="draft",
        created_at=_CREATED_AT,
        building_type="Residential",
        building_location="Downtown district",
        notes="Annual visual check of visible cracks.",
        completed_at=None,
        photographs=photos if photos is not None else [_photo()],
    )
    base.update(overrides)
    return InspectionReportData(**base)


def _metadata() -> ReportMetadata:
    return ReportMetadata(report_id=_REPORT_ID, generated_at=_GENERATED_AT)


def _photo_inspection(status: str) -> InspectionReportData:
    """Inspection with a single photo carrying one verification status variant."""
    return _inspection(photos=[_photo(verification_status=status)])


def _generate(report_data=None, metadata=None, **kwargs) -> bytes:
    """Generate a report; a bare PhotographReportEntry is wrapped in a
    single-photograph InspectionReportData for convenience."""
    if isinstance(report_data, PhotographReportEntry):
        report_data = _inspection(photos=[report_data])
    return generate_inspection_report_pdf(
        report_data if report_data is not None else _inspection(),
        metadata if metadata is not None else _metadata(),
        **kwargs,
    )


def _reader(pdf_bytes: bytes):
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(pdf_bytes))


def _text(pdf_bytes: bytes, include_decorations: bool = False) -> str:
    """Extract whitespace-normalised pagewise text from the PDF."""
    reader = _reader(pdf_bytes)
    pages = [page.extract_text() or "" for page in reader.pages]
    # Canvas-drawn header/footer text is part of page content streams and is
    # included by extract_text; the flag is a readability aid for callers.
    normalised = [" ".join(page.split()) for page in pages]
    return " ".join(normalised) if include_decorations else " ".join(normalised)


def _count_image_xobjects(pdf_bytes: bytes) -> int:
    """Count embedded image XObjects across all pages of the PDF."""
    total = 0
    for page in _reader(pdf_bytes).pages:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for value in xobjects.values():
            resolved = value.get_object()
            if resolved.get("/Subtype") == "/Image":
                total += 1
    return total


# ---------------------------------------------------------------------------
# Valid PDF generation and document structure
# ---------------------------------------------------------------------------

class TestValidPdfGeneration:
    def test_generation_returns_pdf_bytes(self) -> None:
        pdf = _generate()
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0
        assert pdf.startswith(b"%PDF")

    def test_document_is_parseable_and_readable(self) -> None:
        reader = _reader(_generate())
        assert len(reader.pages) >= 1
        assert reader.metadata is not None
        assert "CrackSight AI" in (reader.metadata.title or "")
        assert reader.metadata.author == "CrackSight AI"

    def test_headers_and_page_numbers_on_every_page(self) -> None:
        photos = [
            _photo(overlay_image=None, pixel_measurements=None, model_version=None),
            _photo(),
        ]
        text = _text(_generate(_inspection(photos=photos)), include_decorations=True)
        assert text.count("CrackSight AI") >= 1
        page_number_matches = re.findall(r"Page (\d+) of (\d+)", text)
        assert page_number_matches, "page-number footer missing"
        first_page, total_first = page_number_matches[0]
        _, total_last = page_number_matches[-1]
        assert total_first == total_last, "inconsistent page total across footers"
        assert first_page == "1"
        assert int(total_last) >= 1

    def test_approved_disclaimer_included(self) -> None:
        text = _text(_generate())
        assert "Limitations:" in text
        assert "not a structural safety assessment" in text
        assert "no physical scale" in text

    def test_custom_disclaimer_text_used_when_passed(self) -> None:
        text = _text(_generate(disclaimer_html="Custom <b>test</b> disclaimer body."))
        assert "Custom test disclaimer body." in text

    def test_footer_safety_note_present(self) -> None:
        text = _text(_generate(), include_decorations=True)
        assert "predictions require professional review" in text


# ---------------------------------------------------------------------------
# Inspection information and report metadata
# ---------------------------------------------------------------------------

class TestInspectionInformation:
    def test_report_metadata_present(self) -> None:
        text = _text(_generate())
        assert _REPORT_ID in text
        assert "Report ID" in text
        assert "Generated at" in text
        assert "2026-11-08 14:45:00 UTC" in text

    def test_inspection_information_present(self) -> None:
        text = _text(_generate())
        assert "Tower A facade survey" in text
        assert _INSPECTION_ID in text
        assert "Residential" in text
        assert "Downtown district" in text
        assert "Annual visual check of visible cracks." in text
        assert "2026-11-08 09:30:00 UTC" in text

    def test_inspection_status_displayed(self) -> None:
        assert "Draft" in _text(_generate())
        completed_text = _text(_generate(_inspection(status="completed")))
        assert "Completed" in completed_text

    def test_optional_fields_missing_rendered_as_not_provided(self) -> None:
        text = _text(_generate(_inspection(
            building_type=None,
            building_location=None,
            notes=None,
        )))
        assert text.count("Not provided") >= 2

    def test_completed_at_missing_rendered_gracefully(self) -> None:
        text = _text(_generate())
        assert "Not provided" in text  # completed_at is None by default

    def test_xml_special_characters_escaped(self) -> None:
        text = _text(_generate(_inspection(title="Roof <and> wall survey")))
        assert "Roof <and> wall survey" in text


# ---------------------------------------------------------------------------
# Photographs
# ---------------------------------------------------------------------------

class TestPhotographSections:
    def test_multiple_photographs_each_presented(self) -> None:
        photos = [
            _photo(structure_type="wall", observation="Hairline crack in joint."),
            _photo(
                photo_id=_PHOTO_ID_B,
                structure_type="beam",
                verification_status="correct",
                observation="Diagonal crack near support.",
            ),
        ]
        text = _text(_generate(_inspection(photos=photos)))
        assert "Photographs analysed: 2" in text
        assert "Wall ×1" in text
        assert "Beam ×1" in text
        assert "Photograph 1 — Wall" in text
        assert "Photograph 2 — Beam" in text
        assert "Hairline crack in joint." in text
        assert "Diagonal crack near support." in text

    def test_structure_types_in_summary(self) -> None:
        photos = [
            _photo(structure_type="wall"),
            _photo(photo_id=_PHOTO_ID_B, structure_type="wall"),
        ]
        text = _text(_generate(_inspection(photos=photos)))
        assert "Wall ×2" in text

    def test_verification_status_displayed(self) -> None:
        text = _text(_generate(_photo_inspection("correct")))
        assert "Verification status:" in text
        assert "Correct" in text

    def test_unknown_verification_status_rendered_verbatim(self) -> None:
        text = _text(_generate(_photo_inspection("weird_status")))
        assert "weird_status" in text

    def test_multi_page_report_with_many_photographs(self) -> None:
        photos = [
            _photo(photo_id=f"00000000-0000-4000-8000-00000000000{i}")
            for i in range(1, 5)
        ]
        pdf = _generate(_inspection(photos=photos))
        reader = _reader(pdf)
        assert len(reader.pages) >= 2, "expected multi-page output for four photographs"
        text = _text(pdf, include_decorations=True)
        for index in range(1, len(reader.pages) + 1):
            assert f"Page {index} of {len(reader.pages)}" in text

    def test_zero_photographs_graceful(self) -> None:
        pdf = _generate(_inspection(photos=[]))
        assert pdf.startswith(b"%PDF")
        text = _text(pdf)
        assert "Photographs analysed: 0" in text
        assert "No photographs were analysed" in text
        assert "Photograph 1 —" not in text

    def test_observation_missing_rendered_gracefully(self) -> None:
        text = _text(_generate(_photo(observation=None)))
        assert "No observation recorded." in text
        assert "Inspector observation" in text


# ---------------------------------------------------------------------------
# AI predictions, model version, measurements
# ---------------------------------------------------------------------------

class TestPredictionsAndMeasurements:
    def test_ai_and_observer_sections_labeled_separately(self) -> None:
        text = _text(_generate())
        assert "AI-assisted prediction (model output — requires verification)" in text
        assert "Inspector observation (recorded by inspector)" in text
        ai_pos = text.index("AI-assisted prediction")
        observer_pos = text.index("Inspector observation")
        observation_pos = text.index(_DEFAULT_OBSERVATION)
        assert ai_pos < observer_pos < observation_pos

    def test_model_version_labelled_checkpoint_epoch(self) -> None:
        text = _text(_generate(_photo(model_version="120")))
        assert "Model version (checkpoint epoch): 120" in text

    def test_model_version_missing_rendered_gracefully(self) -> None:
        text = _text(_generate(_photo(
            model_version=None,
            pixel_measurements=None,
            overlay_image=None,
        )))
        assert "Model version (checkpoint epoch): Not recorded" in text

    def test_pixel_measurements_labelled_image_space(self) -> None:
        text = _text(_generate())
        assert "Image-space measurements (pixels)" in text
        assert "Crack pixels: 12,345" in text
        assert "Crack coverage: 12.34%" in text
        assert "Crack regions: 3" in text
        assert "Bounding box (image coordinates): x 210–480, y 96–512" in text

    def test_no_physical_units_anywhere(self) -> None:
        text = _text(_generate(_photo(observation="long " * 400)))
        assert not re.search(r"\bmm\b", text)
        assert not re.search(r"\bcm\b", text)
        assert not re.search(r"\bmillimet", text, re.IGNORECASE)

    def test_zero_crack_pixels_message(self) -> None:
        text = _text(_generate(_photo(pixel_measurements=_measurements(crack_pixel_count=0))))
        assert "No crack pixels were detected" in text

    def test_pixel_measurements_missing_rendered_gracefully(self) -> None:
        text = _text(_generate(_photo(pixel_measurements=None, overlay_image=None)))
        assert "Pixel measurements: Not available" in text

    def test_prediction_timestamp_displayed(self) -> None:
        text = _text(_generate())
        assert "Prediction time: 2026-11-08 10:15:00 UTC" in text


# ---------------------------------------------------------------------------
# Image asset handling
# ---------------------------------------------------------------------------

class TestImageAssets:
    def test_missing_original_and_overlay_rendered_as_placeholders(self) -> None:
        text = _text(_generate(_photo(original_image=None, overlay_image=None)))
        assert "Original photograph not available" in text
        assert "Predicted overlay not available" in text

    def test_corrupt_image_bytes_rendered_gracefully(self) -> None:
        text = _text(_generate(_photo(
            original_image=b"not-an-image",
            overlay_image=b"\x89PNG-corrupt",
        )))
        assert "Original photograph not available" in text
        assert "Predicted overlay not available" in text

    def test_valid_images_embedded(self) -> None:
        assert _count_image_xobjects(_generate(_photo(original_image=_png_bytes()))) >= 2

    def test_some_images_missing_others_present(self) -> None:
        text = _text(_generate(_photo(original_image=None)))
        assert "Original photograph not available" in text
        assert "Predicted overlay not available" not in text
        assert _count_image_xobjects(_generate(_photo(original_image=None))) >= 1
