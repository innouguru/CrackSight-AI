# DECISIONS

**Last updated:** 2026-11-08

## 2026-11-08 — Report page-count capture (Milestone 8, Task 6 step 3)

`reports.page_count` is populated by the generator itself via an optional
`page_count_sink` list parameter (the two-pass branded canvas knows the total
after build). Parsing the PDF in the endpoint was rejected because `pypdf` is
declared as a **test-only** dependency and should not become a runtime
requirement; storing NULL when count is unavailable remains fine per schema.

## Technical Decisions

### Architecture
1. **Two-tier API:** Public FastAPI backend + private inference service for isolation and scalability.
2. **CPU-first inference:** Runs on CPU; "auto" selects CUDA if available but no GPU assumption.
3. **No ORM:** Straightforward database access for maintainability.
4. **Existing inference pipeline reused:** The application inference service wraps `src/crack_detection/inference.py` without independent preprocessing or prediction logic.
5. **Prediction versioning:** Preserve previous predictions as separate versions during reanalysis rather than overwriting.

### Product Scope
6. **Inspection-focused:** Not a model research/evaluation platform.
7. **Pixel measurements only:** No physical calibration (mm/cm) in initial version.
8. **Simple lifecycle:** Two statuses (Draft, Completed).
9. **No manual mask editing.**
10. **Safety boundary:** AI predictions require professional structural engineering review; no safety certification.

### Infrastructure
11. **Neon PostgreSQL:** Already selected for application database.
12. **Cloudflare R2:** Already selected for object storage.
13. **Clerk:** Already selected for authentication (email/password + Google).
14. **Frontend:** React + TypeScript, responsive.
15. **Inference hosting:** Unresolved — requires research and benchmarking before selection.

### Authentication Decisions
16. **Clerk JWT verification via JWKS:** Backend verifies Clerk JWTs by fetching Clerk's JWKS endpoint (`https://<issuer>/.well-known/jwks.json`) and validating signatures using `python-jose[cryptography]`. Keys are cached with a 1-hour TTL to handle key rotation.
17. **Guest session management:** Guest sessions are stored in PostgreSQL (`guest_sessions` table) with unique session tokens, 24-hour expiration, and per-session analysis counters. Guest sessions are isolated from registered users and cannot access registered-user resources.
18. **Guest analysis limit:** Maximum 3 photo analyses per guest session, enforced atomically at the database level using `UPDATE ... SET analyses_count = analyses_count + 1 WHERE ... analyses_count < 3` to prevent race conditions.

## Product Decisions

16. **Hybrid access model:** Guests (3 analyses/session, 24-hour expiry) + Registered users (inspections, PDF reports, monthly allowance).
17. **Guest results not transferable:** Registered users must re-upload and re-analyze.
18. **No public shareable report links:** Reports are downloadable files only.
19. **No organization-level collaboration:** Initial scope is single-user.
20. **Structural components:** Walls, beams, columns only.

## UI/UX Prototype Decisions

1. **Inspection-first visual language:** Use a light, neutral workspace with structural navy and restrained teal accents; avoid generic AI-dashboard decoration and gradients.
2. **System typography:** Use the local system font stack so local review does not depend on a remote font service.
3. **Explicit prediction/observation distinction:** Label model outputs as AI predictions and manual notes as inspector observations; keep image-space pixel units visible.
4. **Persistent safety boundary:** Keep the inspection-aid limitation in the landing, results, and workspace contexts; do not introduce severity ratings or structural safety conclusions.
5. **Isolated visual prototype:** Keep routes and reusable components in `frontend/`; hold mock records and interactions in local React state, make their non-persistent nature explicit, and do not call production APIs until formal Milestone 6 integration.

## Frontend Report Integration Decisions (2026-11-08 — Milestone 8, Task 6 step 7)

1. **Access gating:** PDF report actions on `InspectionDetailPage` render only for authenticated users (`isAuthenticated`); guests and unauthenticated users see no report card. Draft AND Completed inspections are both reportable, matching the backend contract.
2. **Duplicate prevention:** The generate button is disabled while a generation request is in flight; after a failure it re-enables so the user can retry. Each successful generation creates a new backend report row.
3. **Download contract:** `apiClient.downloadReportPdf(reportId)` calls `GET /reports/{reportId}/download` with the bearer token and returns a blob URL, which is revoked after the anchor click. The anchor filename `cracksight-report-{report_id}.pdf` matches the backend's `Content-Disposition` attachment name exactly. Internal R2 keys are never exposed to the browser.
4. **ReportsPage honesty:** The page renders clearly-labelled sample content only. Its "Generate report" CTA navigates to `/app/history`; no report-history/list endpoint was fabricated, since the backend has none (addition requires approval).
