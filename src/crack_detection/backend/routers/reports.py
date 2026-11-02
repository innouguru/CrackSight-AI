"""PDF report generation endpoints.

Provides endpoints for generating and downloading professional branded
PDF inspection reports. Reports are downloadable files only — no public
shareable links.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from psycopg2.extras import RealDictCursor

from crack_detection.backend.dependencies import get_current_user, get_db, get_r2_storage, require_ownership
from crack_detection.backend.schemas import ReportGenerateResponse

router = APIRouter()


@router.post("/generate/{inspection_id}", response_model=ReportGenerateResponse, summary="Generate PDF report")
async def generate_report(
    request: Request,
    inspection_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> ReportGenerateResponse:
    """Generate a PDF inspection report for the given inspection."""
    # Verify inspection exists and user owns it
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id FROM inspections WHERE id = %s", (inspection_id,)
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    require_ownership(request, row["user_id"])

    report_id = uuid4()
    report_key = f"reports/{report_id}.pdf"

    # TODO: Implement PDF generation using ReportLab or WeasyPrint.
    # Library choice is an unresolved decision per TECHNICAL_DESIGN.md.
    # For now, record the report metadata without generating the PDF.

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO reports (id, inspection_id, user_id, report_pdf_key)
            VALUES (%s, %s, %s, %s)
            RETURNING id, generated_at
            """,
            (report_id, inspection_id, user["user_id"] or "guest", report_key),
        )
        row = cur.fetchone()
        conn.commit()

    return ReportGenerateResponse(
        report_id=row["id"],
        generated_at=row["generated_at"],
        download_url=f"/reports/{report_id}/download",
    )


@router.get("/{report_id}/download", summary="Download PDF report")
async def download_report(
    request: Request,
    report_id: UUID = Path(...),
    conn=Depends(get_db),
    storage=Depends(get_r2_storage),
    user=Depends(get_current_user),
) -> dict:
    """Download a generated PDF inspection report."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT r.*, i.user_id FROM reports r
            JOIN inspections i ON r.inspection_id = i.id
            WHERE r.id = %s
            """,
            (report_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    require_ownership(request, row["user_id"])

    # TODO: Stream the PDF from R2 storage once generation is implemented.
    return {
        "report_id": report_id,
        "download_url": f"/reports/{report_id}/download",
        "message": "PDF report download endpoint — generation library selection pending",
    }
