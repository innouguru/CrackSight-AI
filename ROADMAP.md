# ROADMAP

## Project Foundation

This roadmap starts from the actual existing project state: a model development project with a trained U-Net ResNet-34 baseline, a working inference pipeline, dataset ingestion pipeline, unit tests, and supporting documentation. No application code has been implemented yet.

### Completed Model and Inference Milestones

**Status**: Complete

| Objective | Description |
|---|---|
| Train U-Net ResNet-34 baseline (B1) | Trained on crack-seg and concrete400 datasets, checkpoint saved |
| Develop reusable inference pipeline | `src/crack_detection/inference.py` with `CrackSegmentationPipeline` and `run_inference()` |
| Create unit tests for inference | `tests/unit/test_inference.py` covers loading, preprocessing, outputs, error handling |
| Document data contracts | M1 pipeline with manifest generation, mask conversion, deduplication |
| Record evaluation results | Mean Dice: 0.7242, Mean IoU: 0.5884, Precision: 0.7379, Recall: 0.7758 |

**Main Deliverables**:
- Trained checkpoint: `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`
- Inference pipeline module with full API
- Unit test suite passing
- Dataset ingestion pipeline with manifest contracts
- Evaluation report: `final_test_report.json`

**Dependencies**: None (already completed in project history)

**Acceptance Criteria**:
- ✅ Inference pipeline loads checkpoint and produces valid `InferenceResult`
- ✅ Unit tests pass with real and synthetic checkpoints
- ✅ Preprocessing matches model expectations (256×256 RGB, /255.0, CHW)
- ✅ Model architecture: UNetResNet34 with ResNet-34 encoder
- ✅ Evaluation metrics documented and preserved

---

### Milestone 1: Documentation and Architecture

**Objective**: Create comprehensive product documentation and technical design before any application code begins.

**Main Deliverables**:
- `PROJECT_CONTEXT.md` - Concise project memory for future sessions
- `APP_SPECIFICATION.md` - Complete functional requirements and user workflows
- `TECHNICAL_DESIGN.md` - System architecture, component boundaries, data designs
- `ROADMAP.md` - Development plan from existing project state

**Dependencies**: None (documentation-only milestone; preserves existing work)

**Acceptance Criteria**:
- ✅ All four documents created and in project root
- ✅ Documents agree with each other on user capabilities, constraints, and exclusions
- ✅ Existing model work preserved and referenced (not modified)
- ✅ No contradictions between documents
- ✅ Unresolved decisions explicitly marked
- ✅ Product remains simple and achievable on limited budget
- ✅ Documents useful to another developer starting the project

---

### Milestone 2: Backend Foundation

**Objective**: Implement the main FastAPI backend with authentication integration, inspection management, and image storage coordination.

**Main Deliverables**:
- FastAPI application structure with routers for inspections, photographs, reports, authentication
- Clerk token verification middleware
- Neon PostgreSQL database schema (users, inspections, photographs, prediction_versions, reports)
- Cloudflare R2 storage integration with proper key structure
- Ownership enforcement on all read/write operations
- API endpoint specification and basic implementation

**Dependencies**:
- `PROJECT_CONTEXT.md`, `APP_SPECIFICATION.md`, `TECHNICAL_DESIGN.md` completed
- Clerk account and API keys configured
- Neon PostgreSQL project created
- Cloudflare R2 bucket configured

**Acceptance Criteria**:
- ✅ FastAPI app runs locally with `uvicorn main:app --reload`
- ✅ Clerk sign-in flow works (email/password + Google OAuth)
- ✅ Token verification middleware functional
- ✅ CRUD operations for inspections (draft/completed lifecycle)
- ✅ CRUD operations for photographs with structure type and verification status
- ✅ R2 storage read/write functional for test objects
- ✅ Ownership checks prevent cross-user access
- ✅ Health check endpoint operational

---

### Milestone 3: Authentication

**Objective**: Complete Clerk integration and user access model (guest + registered).

**Main Deliverables**:
- Guest session creation and management
- Registered user registration (email/password) and Google sign-in
- User session management in FastAPI
- Guest vs registered capability enforcement
- Session token isolation for guest data

**Dependencies**:
- Backend foundation (Milestone 2) partially complete
- Clerk account configured with email/password and Google
- Frontend routing for sign-in/sign-up flows

**Acceptance Criteria**:
- ✅ Guest can access application without registration (3 analysis limit)
- ✅ Registered user can sign in with email/password
- ✅ Registered user can sign in with Google
- ✅ Guest session isolated; registered user data preserved
- ✅ Guest results cannot be transferred to registered account
- ✅ Registering user must re-upload/re-analyze to save inspections

---

### Milestone 4: Database and Storage

**Objective**: Implement Neon PostgreSQL schema and Cloudflare R2 integration for full application data.

**Main Deliverables**:
- Complete database schema (users, inspections, photographs, prediction_versions, reports)
- Database migration scripts
- R2 bucket configuration with private access
- Object key structure for images, masks, overlays, reports
- Guest session file isolation and 24-hour expiration
- Cleanup procedures for abandoned uploads and failed analyses

**Dependencies**:
- Authentication (Milestone 3) functional
- FastAPI backend (Milestone 2) with database connection

**Acceptance Criteria**:
- ✅ PostgreSQL tables created with correct relationships
- ✅ ON DELETE CASCADE for inspection → photographs → prediction_versions
- ✅ R2 bucket configured; objects readable/writable via backend
- ✅ Guest session isolation by unique token
- ✅ 24-hour expiration mechanism for guest files
- ✅ Inspection deletion removes R2 objects and database records
- ✅ Partial failure handling documented and implemented

---

### Milestone 5: Inference Service Integration

**Objective**: Connect the main backend to the private inference service for crack segmentation.

**Main Deliverables**:
- Internal inference API client in FastAPI backend
- Single-image inference request/response flow
- Batch processing orchestration (independent per-photo processing)
- Progress stages display (uploading, preparing image, running crack detection, generating results, complete)
- Cancellation support for pending work
- Error handling for inference failures (timeout, service unavailable, invalid image)
- Retry logic for failed photographs

**Dependencies**:
- Authentication and database/storage milestones complete
- Inference service (could be local initially, then remote)

**Acceptance Criteria**:
- ✅ Backend can send inference request and receive valid `InferenceResult`
- ✅ Processing stages displayed (no fabricated percentage progress)
- ✅ Each photograph processed independently in batch
- ✅ Successful results retained even if some photographs fail
- ✅ Failed photographs marked for individual retry
- ✅ Users can cancel pending photographs/batch work
- ✅ Completed results retained after cancellation

---

### Pre-Milestone 6: UI/UX Direction and Browser Prototype

**Status**: Complete — visual prototype built and reviewed locally; formal backend/auth integration remains pending.

**Objective**: Establish a coherent inspection-product design direction and make the main product screens available for stakeholder browser review before production frontend integration.

**Deliverables**:
- Responsive React + TypeScript prototype in `frontend/`
- Public landing, auth placeholders, dashboard, guest analysis/results, inspection history/create/detail, report preview, and supporting states
- Reusable design tokens, app shell, status/notice, image comparison, and inspection-card components
- Design rationale, mock boundaries, and transition notes in `docs/ui_ux_design.md`

**Boundary**: Prototype data and interactions are in-memory/local only. No live upload, authentication, report generation, database persistence, API calls, or inference are implemented by this pre-work. Do not treat it as completion of Milestone 6 acceptance criteria.

### Milestone 6: Frontend Foundation

**Objective**: Implement React + TypeScript frontend with responsive interface.

**Main Deliverables**:
- React application structure with TypeScript
- Responsive layout (desktop, tablet, mobile)
- Photograph upload component (file upload + camera capture)
- Image preview and retake before analysis
- Analysis result display (original, mask, overlay, measurements)
- Inspection creation and editing flow
- Dashboard with recent inspections and New Inspection button

**Dependencies**:
- Backend API functional (endpoints operational)
- Inference service integration (Milestone 5) partially complete
- Clerk authentication integration

**Acceptance Criteria**:
- [ ] Production application loads and responds on desktop, tablet, and mobile
- [ ] Photograph upload is connected to the backend for JPEG, PNG, and WebP
- [ ] Smartphone camera capture is connected to the upload flow
- [ ] Preview and retake work with the real upload flow
- [ ] Multiple-photo batch submission is supported
- [ ] Each photograph is processed independently with real results
- [ ] Analysis results are rendered from backend responses

The pre-Milestone 6 browser prototype provides mock screens and local image preview only; it does not satisfy these production acceptance criteria.

---

### Milestone 7: Guest Analysis Workflow

**Objective**: Enable guest users to upload/capture photographs and receive AI-assisted analysis without registration.

**Main Deliverables**:
- Guest access flow (no registration required)
- 3-photo analysis limit per guest session
- 24-hour guest result expiration
- View original image, predicted mask, overlay, pixel measurements
- Download individual analysis results
- Session cleanup on expiry

**Dependencies**:
- Frontend foundation (Milestone 6) complete
- Inference service integration (Milestone 5) complete
- R2 guest session storage (Milestone 4) complete

**Acceptance Criteria**:
- [ ] Guest can upload photograph and run analysis without registering
- [ ] Guest is limited to 3 analyses per backend session
- [ ] Guest can view original, mask, overlay, and measurements from backend results
- [ ] Guest can download individual results (original, mask, overlay, summary)
- [ ] Guest session expires after 3 analyses or 24 hours
- [ ] Guest results cannot be transferred to a registered account

---

### Milestone 8: Registered-User Inspections

**Objective**: Enable registered users to create, save, and manage inspections with PDF reports.

**Main Deliverables** (in implementation order):
1. Registered-user inspection creation with title — connect the frontend creation flow to the existing backend `POST /inspections` endpoint.
2. Add photographs to inspection (structure type per photo) — productionise the existing upload endpoint (declare `python-multipart` dependency; fix foreign-ownership status consistency); the upload, listing, and download endpoints are already implemented and tested.
3. Save inspection results (persist beyond 24 hours) — **COMPLETE (verified)**. Registered-user tables (`users`, `inspections`, `photographs`, `prediction_versions`) have no expiry; only `guest_sessions` carries the 24-hour expiry, and `cleanup_expired_guest_sessions()` never touches registered data.
4. Inspection dashboard and history — connect the mock-backed `DashboardPage` and `HistoryPage` to the existing backend `GET /inspections` endpoint.
5. Filtering by title, date, structure type, verification status — implement backend date/structure-type/verification-status filters on `GET /inspections` (title search already works; the `structure_type` query param is currently accepted but ignored).
6. Monthly analysis allowance with fair-use protection — implement per-registered-user monthly usage tracking with atomic enforcement, reset, and failure compensation (the guest 3-analysis limit already exists).
7. Generate and download professional PDF inspection reports — implemented and verified: ReportLab standalone generator + `POST /reports/generate/{inspection_id}` + `GET /reports/{report_id}/download` endpoints; ReportLab (navy `#18313b`/teal `#167f78` branding matching frontend tokens) chosen over WeasyPrint; branding resolved.
8. View inspection history (list and card views) — implemented together with Task 4 using the same `list_inspections` data fetch (list and card presentations share one backend call).

**Acceptance Criteria**:
- [x] Inspection saves and persists beyond guest session — COMPLETE (verified; no code change required)
- [x] Registered user can create inspection with title — backend endpoint implemented and tested; frontend creation flow connected to `apiClient.createInspection`; navigates to detail page on success
- [x] User can add photographs with structure type (wall/beam/column) — backend upload/list/download implemented and tested; `python-multipart` declared in `requirements.txt`; foreign-ownership status standardised to opaque 404 across upload/complete/update/delete/download/reopen endpoints
- [x] Dashboard shows total inspections, total photographs, and recent inspections from saved data — backend `list_inspections` implemented; frontend `DashboardPage`/`HistoryPage` connected to real authenticated data
- [x] New Inspection button is available in the integrated application — creation flow connected to backend
- [x] PDF report generates with required content (branding, ID, date, photos, measurements, model version, observations, verification statuses, disclaimer, page numbers) — COMPLETE: standalone ReportLab generator implemented + 31 unit tests; `POST /reports/generate/{inspection_id}` implemented + 13 tests (registered-user-only, Draft/Completed, page count persisted); `GET /reports/{report_id}/download` implemented + 8 tests (opaque 404, streamed PDF bytes, attachment disposition); Inspection-delete FK cleanup complete (ON DELETE CASCADE + R2 PDF cleanup before DB DELETE, 12 tests); frontend wiring complete (InspectionDetailPage report generate/download card, ReportsPage honest copy; 14 new frontend tests, all passing).
- [x] PDF is a downloadable file only (no public shareable links) — backend download endpoint implemented: ownership-checked streaming of actual PDF bytes from private R2 with attachment disposition; no public links
- [x] History supports list and card views backed by saved inspections — views connected to real backend data; list/card views, search, filters tested
- [x] Search by title, date, structure type, and verification status works against saved data — backend filters (status/structure_type/verification_status/date_from/date_to) implemented with validation, EXISTS subqueries, correct total; frontend filter UI wired
- [x] Monthly allowance with fair-use protection is connected to backend enforcement — `user_usage` table + atomic increment/decrement; 429 on limit exceeded; failure compensation; 5/5 allowance tests pass

**Dependencies** (implementation order):
1. Inspection creation — depends on Authentication (Milestone 3), Database/storage (Milestone 4); foundation for Tasks 2, 4, 5, 6, 7, 8.
2. Add photographs — depends on Task 1 (inspections must exist); `python-multipart` declared in `requirements.txt`; foreign-ownership status standardised to opaque 404; COMPLETE.
3. Save inspection results — depends on Database/storage (Milestone 4); COMPLETE, no further work.
4. Dashboard and history — depends on Task 1 (inspections must exist); reuses existing `list_inspections` and detail endpoints.
5. Filtering — depends on Task 4 (dashboard/history connected); extends the same `list_inspections` endpoint.
6. Monthly allowance — depends on registered-user identity and persisted analyses; allowance limit/reset period is an unresolved decision.
7. Generate PDF reports — depends on Tasks 1 and 2 (inspections and photographs must exist); PDF library choice (ReportLab) and branding (navy `#18313b`/teal `#167f78`) resolved; frontend wiring complete.
8. View history list and card — implemented with Task 4 (same data fetch, two presentations).

**Status by deliverable**:
- Deliverable 1 (inspection creation): COMPLETE — backend done, frontend connected; verified with 10 frontend tests.
- Deliverable 2 (photographs): COMPLETE — backend upload/list/download implemented and tested; frontend connected; `python-multipart` declared in `requirements.txt`; foreign-ownership status standardised to opaque 404 across upload/complete/update/delete/download/reopen endpoints; verified with regression tests.
- Deliverable 3 (persist beyond 24h): COMPLETE — verified.
- Deliverable 4 (dashboard and history): COMPLETE — backend `GET /inspections` implemented; frontend `DashboardPage`/`HistoryPage` connected to `apiClient.listInspections()` with real authenticated data + tests.
- Deliverable 5 (monthly allowance): COMPLETE — registered-user monthly tracking (`user_usage` table, atomic increment/decrement helpers), 429 on limit exceeded, failure compensation; 5/5 allowance tests pass.
- Deliverable 6 (PDF reports): COMPLETE — ReportLab 4.5.1 installed; standalone `report_generator.py` + 31/31 unit tests; `POST /reports/generate/{inspection_id}` + 13/13 endpoint tests; `GET /reports/{report_id}/download` + 9/9 endpoint tests (incl. download-after-inspection-deleted); `fk_reports_inspection` now `ON DELETE CASCADE` (fresh-DB statement + idempotent guarded constraint-swap migration) and `delete_inspection` cleans up associated report PDFs from R2 before the DB DELETE (+ 12 migration/deletion tests, mocked only); frontend wiring complete (InspectionDetailPage report generate/download card for authenticated users, Draft & Completed; ReportsPage kept as clearly-labelled sample content navigating its CTA to `/app/history` with no fabricated list endpoint; 14 new frontend tests, all passing; `vitest` 71 passed, `tsc --noEmit` clean, `oxlint` clean, `vite build` OK). Real-service integration verification remains deployment-time.
- Deliverable 7 (history list/card views): COMPLETE — views connected to real backend data; list/card views, search, filters tested.
- Deliverable 8 (filtering): COMPLETE — backend `list_inspections` supports `status`, `structure_type`, `verification_status`, `date_from`, `date_to` with enum validation, EXISTS subqueries, and correct total count; frontend filter UI wired to backend params.

---

### Milestone 9: Dashboard and History

**Objective**: Implement simple dashboard with inspection statistics and filtering.

**Main Deliverables**:
- Dashboard: total inspections, total photographs analysed, recent inspections, New Inspection button
- Inspection history: list view and card view
- Search by inspection title
- Date filtering
- Structure-type filtering (wall, beam, column)
- Verification-status filtering

**Dependencies**:
- Registered-user inspections (Milestone 8) complete

**Acceptance Criteria**:
- [ ] Dashboard displays correct counts from saved inspections and photographs
- [ ] Recent inspections list shows latest saved inspections
- [ ] New Inspection button navigates to the integrated create flow
- [ ] History supports toggle between list and card views using saved data
- [ ] Search filters saved results by title
- [ ] Date filter works (from-to range or preset ranges)
- [ ] Structure-type filter limits to the selected component
- [ ] Verification-status filter limits to the selected status

---

### Milestone 10: PDF Reports

**Objective**: Generate professional, branded, downloadable PDF inspection reports.

**Main Deliverables**:
- PDF report generation with application branding
- Report ID and generation date included
- Inspection and building information section
- Summary of photographs analysed
- Original photographs and predicted overlays embedded
- Available pixel measurements included
- Model version displayed
- Inspector observations included
- Verification statuses included
- Limitations and safety disclaimer clearly stated
- Page numbers at footers
- Clearly distinguish AI-generated predictions from inspector-recorded observations
- No engineering recommendations or structural safety conclusions

**Dependencies**:
- Registered-user inspections (Milestone 8) complete
- Database data retrieval functional
- R2 storage for report PDFs

**Acceptance Criteria**:
- [ ] PDF generates with all required sections
- [ ] Branding is visible (logo/color scheme)
- [ ] Report ID and generation date are present
- [ ] Photographs and overlays render at appropriate quality
- [ ] Pixel measurements are reported (image-space pixels only)
- [ ] Model version is identified
- [ ] Observations are distinguished from AI predictions
- [ ] Safety disclaimer is included and clear
- [ ] Page numbers appear on each page
- [ ] PDF is downloadable (not a public shareable link)
- [ ] Individual photograph results are downloadable (original, mask, overlay, summary)

---

### Milestone 11: Testing and Security

**Objective**: Implement test suite and security measures.

**Main Deliverables**:
- Unit tests for API endpoints
- Integration tests for end-to-end workflows
- Authentication security tests (Clerk token verification)
- Ownership enforcement tests
- R2 storage access tests
- Inference error handling tests
- PDF report content validation

**Dependencies**:
- All previous milestones complete enough for testing

**Acceptance Criteria**:
- [ ] Existing unit tests pass (inference pipeline, data pipeline)
- [ ] New unit tests cover FastAPI endpoints
- [ ] Authentication flows are tested (guest + registered)
- [ ] Ownership checks prevent unauthorized access
- [ ] R2 storage access is restricted by user/session
- [ ] Error handling is tested for all API endpoints
- [ ] PDF report content is validated against specification

---

### Milestone 12: Deployment

**Objective**: Deploy application to production environment on limited budget.

**Main Deliverables**:
- Frontend deployed to static hosting (Netlify/Vercel free tier)
- Backend deployed to cloud platform (Heroku/Railway free tier consideration)
- Inference service deployed (CPU-optimized, research from unresolved decisions)
- Neon PostgreSQL production connection
- Cloudflare R2 production bucket
- Domain configuration (custom domain if budget allows)
- Monitoring and basic error tracking

**Dependencies**:
- All previous milestones tested locally
- Inference hosting decision resolved (research milestone)
- Domain and SSL configuration

**Deployment sub-deliverables (from the 2026-11-08 deployment-readiness audit; hosting target Render; frontend static site, backend Web Service, model embedded, Neon PostgreSQL, R2 storage, Clerk auth):**

1. **CORS + preflight handling (backend)**: COMPLETE — environment-driven allowed origins (`ALLOWED_ORIGINS`, comma-separated, normalized, wildcards stripped, fail-closed in production, local Vite dev origins allowed when `DEBUG=true` and unset); `create_app()` now reads settings per build (module-level settings snapshot removed); CORSMiddleware registered last so it is outermost (Starlette executes the most-recently added middleware first): OPTIONS preflights are answered by CORS without any Clerk JWT, non-preflight requests still pass through Clerk authentication, and CORS headers are attached to authentication error responses for allowed origins. Verified by 13 new `TestCorsAndPreflight` tests through the real middleware stack (`tests/unit/test_backend.py`); full backend suite 213 passed. Live production behaviour still to be verified at deployment time.
2. **Model checkpoint availability on Render**: COMPLETE — build-time fetch script `scripts/download_checkpoint.py` streams the existing checkpoint from a private R2 bucket via a pre-signed URL (`MODEL_CHECKPOINT_URL`) into `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`, with optional SHA-256 verification (`MODEL_CHECKPOINT_SHA256`), atomic temp-file promotion, reuse of an existing valid checkpoint, and nonzero exit codes on failure. Checkpoint is never committed (`.gitignore: *.pth`). Covered by 19 tests in `tests/unit/test_download_checkpoint.py` (mocked HTTP; no real R2 credentials). Render build command: `pip install -r requirements.txt && python scripts/download_checkpoint.py`.
3. **Backend deployment configuration**: COMPLETE — Render Web Service (`render.yaml` + `.python-version` 3.12.5), build command `pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt && python scripts/download_checkpoint.py`, start command `uvicorn crack_detection.backend.main:app --host 0.0.0.0 --port $PORT`, health check `/live`, CPU-only PyTorch (torch 2.6.0+cpu from the official PyTorch CPU index; `2.6.0+cpu` exists only on that index so pip cannot resolve a CUDA/PyPI distribution), `PYTHONPATH=src` so `crack_detection.backend.main:app` imports, checkpoint downloaded during build via `scripts/download_checkpoint.py` (sub-deliverable 2). Required secret env vars declared with `sync: false` (values supplied via the Render dashboard). Covered by configuration verification (render.yaml parses, `/live` route present, import path valid with PYTHONPATH=src, downloader tests 19/19). Live deployment not performed.
4. **Neon configuration**: COMPLETE — `DATABASE_URL` supplied as a Render secret env var (`sync: false`) with `sslmode=require`; config.py validates `sslmode=require` is present and fails fast if missing; `psycopg2.connect(settings.database_url)` works with both Neon direct and pooled endpoints. Neon pooled endpoint recommended (app opens short-lived per-operation connections, uses no PgBouncer-incompatible features). No code changes needed to database.py beyond the config validator. Tests added for DATABASE_URL sslmode validation. Live Neon connectivity NOT verified (deployment-time; free-tier limitations).
5. **R2 configuration**: COMPLETE — `R2Storage` (`src/crack_detection/backend/storage.py`) wraps boto3 S3-compatible client for private R2 bucket; all settings (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT`) declared as required fields in `config.py` with validation (endpoint must be HTTPS URL, bucket name non-empty); declared as `sync: false` secrets in `render.yaml` (values supplied via Render dashboard); bucket remains private, objects accessed server-side only with ownership enforcement. Tests added for R2 config validation. Live R2 connectivity NOT verified (deployment-time; free-tier limitations).
6. **Backend smoke testing**: COMPLETE — `scripts/smoke_test_backend.py` performs non-mutating GET checks against `/live` and `/ready` on a deployed backend URL (supplied via `--base-url` or `SMOKE_TEST_BASE_URL` env var); validates HTTP status codes and response structure; logs scheme+host only (never secrets/query params); exits nonzero on failure. Unit tests: `TestHealthEndpoints` (6 tests) in `tests/unit/test_backend.py` cover `/live` (200 + status=alive), `/ready` (200 + checks structure), configured vs unconfigured env var reporting, and no-auth-required access. Live deployment smoke testing NOT performed (deployment-time; free-tier limitations).
7. **Frontend deployment**: COMPLETE — Render Static Site configuration prepared: root `frontend`, build command `npm ci && npm run build`, publish directory `dist`, build-time env vars `VITE_API_URL`/`VITE_CLERK_PUBLISHABLE_KEY` (placeholders in `.env.example`), SPA rewrite `/*` → `/index.html` documented for Render dashboard. Vite build verified locally (71 tests pass, `tsc --noEmit` clean, `oxlint` clean, `vite build` produces `dist/`). Live deployment NOT performed (deployment-time).
8. **Clerk configuration**: COMPLETE — Clerk JWT issuer (`CLERK_JWT_ISSUER`) validated as HTTPS URL at startup; JWKS URL derived from issuer when not explicitly set (`CLERK_JWKS_URL`); backend JWT verification (`_verify_clerk_jwt`) validates RS256 signature, issuer, and expiration against Clerk's JWKS with caching; frontend publishes `VITE_CLERK_PUBLISHABLE_KEY` only (secret key stays server-side); `CLERK_SECRET_KEY` declared as `sync: false` secret in Render; email claim required for user identity synchronisation (`ensure_registered_user` fails closed when missing). All secret env vars declared with `sync: false` in `render.yaml`; values supplied via Render dashboard. Tests added for Clerk config validation. Live Clerk authentication NOT verified (deployment-time; free-tier limitations).
9. End-to-end live testing + fixes discovered during live testing.
10. Post-deployment reconciliation of superseded architecture notes (`TECHNICAL_DESIGN.md` still lists Netlify/Vercel + separate inference service; backend `inference_service_url` is only a health-report legacy field).

**Acceptance Criteria**:
- [ ] Application is accessible via a production URL
- [ ] All user flows work in production
- [ ] Inference service is operational (CPU)
- [ ] Database is persistent and accessible
- [ ] R2 storage is persistent and accessible
- [ ] Basic monitoring is in place (error logging, uptime)

---

### Milestone 13: Real-World Validation

**Objective**: Validate application with real building inspection photographs.

**Main Deliverables**:
- Test with real photographs (not just synthetic test images)
- Verify inference results on real-world building component images
- Collect user feedback on workflow and result usefulness
- Assess measurement accuracy and limitations
- Document any issues or edge cases discovered

**Dependencies**:
- Deployment complete (Milestone 12)
- Real building photographs available

**Acceptance Criteria**:
- [ ] Application works with real photographs (JPEG, PNG, WebP)
- [ ] Inference produces reasonable crack masks on real images
- [ ] Pixel measurements are displayed where available
- [ ] User feedback is collected on inspection workflow
- [ ] Limitations are acknowledged (no structural safety claims)
- [ ] Necessary adjustments are documented for future versions

## Roadmap Summary

**Total Milestones**: 13

**Progress**: Milestones 1–5 complete; pre-Milestone 6 design prototype complete; Milestone 6 foundation and Milestone 8 (all eight deliverables, including PDF reports) complete; Milestones 9 and 10 criteria already satisfied by Milestone 8 work; Milestones 11–13 remain pending.

**Critical Path**:
1. Documentation (Milestone 1) → Backend foundation (Milestone 2) → Auth (Milestone 3) → Database/storage (Milestone 4) → Inference integration (Milestone 5) → Frontend (Milestone 6) → Guest workflow (Milestone 7) → Registered inspections (Milestone 8) → Dashboard/history (Milestone 9) → PDF reports (Milestone 10) → Testing/security (Milestone 11) → Deployment (Milestone 12) → Validation (Milestone 13)

**Budget Constraints**: Very limited budget throughout; prefer free-tier services; inference hosting requires research and benchmarking (unresolved decision).

**Key Unresolved Decisions** (carried through roadmap):
- Inference service hosting provider and cost
- Maximum file size/dimension limits
- Monthly analysis allowance
- Batch processing concurrency
- Guest session management approach
- Frontend hosting platform

**Dependencies Between Milestones**: Each milestone depends on completion of preceding infrastructure milestones. Milestone 1 (documentation) has no dependencies and can proceed immediately.