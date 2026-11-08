"""PDF report generation endpoints.

Provides endpoints for generating and downloading professional branded
PDF inspection reports. Reports are downloadable files only — no public
shareable links.

Generation flow (registered users only):
1. Verify the caller is a registered user (guests are rejected).
2. Fetch the inspection; unknown or foreign inspections are reported with
   an opaque 404 (no existence leak).
3. Fetch all photographs for the inspection, including their internal R2
   keys (never exposed to clients).
4. Download originals and available overlays from R2.
5. Build the branded PDF in memory via ``report_generator``.
6. Upload the PDF to R2 under ``reports/{report_id}.pdf``.
7. Persist the report row (including the available page count).
If any stage fails after upload, the uploaded PDF is removed best-effort
and the original error is preserved for logging/response.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from psycopg2.extras import RealDictCursor

from crack_detection.backend.dependencies import (
    get_current_user,
    get_db,
    get_r2_storage,
    require_authenticated_user,
    require_ownership,
)
from crack_detection.backend.report_generator import (
    InspectionReportData,
    PhotographReportEntry,
    ReportMetadata,
    generate_inspection_report_pdf,
)
from crack_detection.backend.schemas import ReportGenerateResponse
from crack_detection.backend.storage import R2Storage, StorageError

router = APIRouter()
logger = logging.getLogger(__name__)

_PDF_CONTENT_TYPE = "application/pdf"


def _fetch_report_inspection(conn, inspection_id: UUID) -> Optional[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, title, building_type, building_location,
                   notes, status, created_at, completed_at
            FROM inspections
            WHERE id = %s
            """,
            (inspection_id,),
        )
        return cur.fetchone()


def _fetch_report_photographs(conn, inspection_id: UUID) -> List[dict]:
    """Photographs for the (ownership-verified) inspection, incl. R2 keys."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.id, p.structure_type, p.observation,
                   p.verification_status, p.model_version,
                   p.prediction_timestamp, p.pixel_measurements,
                   p.original_image_key, p.prediction_overlay_key
            FROM photographs p
            WHERE p.inspection_id = %s
            ORDER BY p.created_at ASC, p.id ASC
            """,
            (inspection_id,),
        )
        return cur.fetchall()


def _download_asset(storage: R2Storage, key: Optional[str]) -> Optional[bytes]:
    """Download a photograph asset; ``None`` keys yield ``None`` (graceful)."""
    if not key:
        return None
    try:
        return storage.download_file(key)
    except StorageError as exc:
        logger.error("Failed to download report asset %s: %s", key, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve photograph assets: {exc}",
        )


@router.post(
    "/generate/{inspection_id}",
    response_model=ReportGenerateResponse,
    summary="Generate PDF report",
)
async def generate_report(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(require_authenticated_user),
) -> ReportGenerateResponse:
    """Generate a branded PDF inspection report for the given inspection."""
    inspection_row = _fetch_report_inspection(conn, inspection_id)
    if not inspection_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found"
        )
    require_ownership(request, inspection_row["user_id"])

    photo_rows = _fetch_report_photographs(conn, inspection_id)

    entries: List[PhotographReportEntry] = []
    for row in photo_rows:
        original_bytes = _download_asset(storage, row["original_image_key"])
        overlay_bytes = _download_asset(storage, row["prediction_overlay_key"])
        entries.append(
            PhotographReportEntry(
                photo_id=str(row["id"]),
                structure_type=row["structure_type"],
                verification_status=row["verification_status"],
                observation=row["observation"],
                model_version=row["model_version"],
                prediction_timestamp=row["prediction_timestamp"],
                pixel_measurements=row["pixel_measurements"],
                original_image=original_bytes,
                overlay_image=overlay_bytes,
            )
        )

    report_data = InspectionReportData(
        inspection_id=str(inspection_row["id"]),
        title=inspection_row["title"],
        status=inspection_row["status"],
        created_at=inspection_row["created_at"],
        building_type=inspection_row["building_type"],
        building_location=inspection_row["building_location"],
        notes=inspection_row["notes"],
        completed_at=inspection_row["completed_at"],
        photographs=entries,
    )

    report_id = uuid4()
    report_key = f"reports/{report_id}.pdf"
    page_count_sink: List[int] = []

    try:
        pdf_bytes = generate_inspection_report_pdf(
            report_data,
            ReportMetadata(
                report_id=str(report_id),
                generated_at=datetime.now(timezone.utc),
            ),
            page_count_sink=page_count_sink,
        )
    except Exception as exc:
        logger.exception(
            "PDF generation failed for inspection %s", inspection_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {exc}",
        )

    try:
        storage.upload_file(report_key, pdf_bytes, _PDF_CONTENT_TYPE)
    except Exception as exc:
        logger.error("Report upload failed for key %s: %s", report_key, exc)
        _best_effort_delete(storage, report_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload generated report: {exc}",
        )

    page_count = page_count_sink[-1] if page_count_sink else None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO reports
                    (id, inspection_id, user_id, report_pdf_key, page_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, generated_at
                """,
                (report_id, inspection_id, user["user_id"], report_key, page_count),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as exc:
        # Compensation: an uploaded PDF with no persisted report row would
        # be an orphan; remove it best-effort. Cleanup failures are logged,
        # never raised — the original error is preserved.
        logger.error("Report persistence failed for %s: %s", report_key, exc)
        _best_effort_delete(storage, report_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record report generation: {exc}",
        )

    return ReportGenerateResponse(
        report_id=row["id"],
        generated_at=row["generated_at"],
        download_url=f"/reports/{row['id']}/download",
    )


def _best_effort_delete(storage: R2Storage, report_key: str) -> None:
    """Delete an uploaded report PDF; cleanup failures never mask the
    original error (``R2Storage.delete_file`` already logs internally)."""
    try:
        storage.delete_file(report_key)
    except Exception as cleanup_exc:
        logger.warning(
            "Cleanup of report %s failed: %s", report_key, cleanup_exc
        )


@router.get("/{report_id}/download", summary="Download PDF report")
async def download_report(
    request: Request,
    report_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(require_authenticated_user),
) -> Response:
    """Download a generated PDF inspection report.

    Requires an authenticated registered user (guests and unauthenticated
    requests are rejected by the dependency). Ownership is enforced through
    the report's associated inspection: nonexistent and foreign-owned
    reports are indistinguishable (opaque 404). The PDF is streamed from
    private R2 storage using its internal key, which is never exposed to
    clients.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT r.report_pdf_key, i.user_id
            FROM reports r
            JOIN inspections i ON r.inspection_id = i.id
            WHERE r.id = %s
            """,
            (report_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    require_ownership(request, row["user_id"])

    report_key = row["report_pdf_key"]
    try:
        data = storage.download_file(report_key)
    except StorageError as exc:
        logger.error("Report download failed for key %s: %s", report_key, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve report: {exc}",
        )

    return Response(
        content=data,
        media_type=_PDF_CONTENT_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="cracksight-report-{report_id}.pdf"'
            ),
        },
    )
