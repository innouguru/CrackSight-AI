# HANDOFF — Next Agent Summary

**Last updated:** 2026-11-08

## Project

CrackSight AI is an AI-assisted building inspection application for visible cracks in walls, beams, and columns. It is an inspection aid, not a structural safety assessment or engineering recommendation system. Pixel measurements are image-space only.

## Current State

- Model, data pipeline, and backend Milestones 2–5 are implemented per `CURRENT_STATE.md`.
- **Milestone 8: Tasks 1.1–1.5, photograph upload, persistence-beyond-24h, and Task 4 (filtering) are implemented.** The production React/TypeScript frontend is under `frontend/`.
- The frontend builds, lints, and passes 71 tests. Local dev server at `http://localhost:5173/` (`cd frontend; npm run dev`).
- Clerk React SDK integrated; guest session creation/validation connected to FastAPI backend.
- All API contracts verified against backend Pydantic schemas.

## Most Recent Work

Completed Milestone 11 task 4 — Database integration-suite repair (2026-11-08, verified):

- **Root cause**: session-scoped `db_conn` ran autocommit-off and never concluded transactions; tests left it idle-in-transaction, and `init_schema()` (own connection) waited indefinitely for DDL locks — decisively the guarded `fk_reports_inspection` cascade swap (`ALTER TABLE reports … REFERENCES inspections`) held against the shared connection's uncommitted transaction. Historical reproduction: 3 tests passed, then `TestDatabaseCRUD::test_create_photograph` hung ≥150s. Today's causality probe: open uncommitted txn + `init_schema()` completes instantly now that `xportra_test` has the CASCADE FK.
- **Fix (fixture, production code unchanged)**: autouse per-test rollback fixture `rollback_db_transaction` (rollback before AND after every test — no idle-in-transaction, no lock retention, test rows discarded); targeted `_delete_test_guest_session(session_id)` cleanup for guest rows created on the helpers' own committed connections; uuid-suffixed CRUD ids; FK test rewritten to genuinely raise `psycopg2.errors.ForeignKeyViolation` (real user + nonexistent inspection, rollback afterwards, no partial row); malformed `test_validate_guest_session_expiration` (module-level) and nested `test_increment_analysis_count` (never collected) promoted to proper `TestGuestSession` methods.
- **Verified (actual, real local PostgreSQL `xportra_test`)**: collection **9** (was 8); affected tests individually **5/5 passed**; full integration file **9 passed** three consecutive times (16.67s / 11.24s / 9.26s, rerun-independent); post-run users/inspections/photographs = 0 and guest_sessions unchanged at 6 stale expired rows (no accumulation); backend suite **200 passed**. One 300s timeout during run 2 verification was a shell-pipeline artifact, not the suite (three clean runs immediately after; no lingering connections).
- **Remaining**: real-service (Neon/R2/Clerk) integration validation BLOCKED on credentials — the only remaining Milestone 11 implementation-level gap. Hygiene observations (non-blocking): stale `request: Request` annotation in `routers/guest.py`; the 6 stale guest rows (removable via the product's `cleanup_expired_guest_sessions()`).
- Nothing staged or committed; `main` @ `a834c33`.

Completed Milestone 11 task 3 — /auth endpoint behavioural tests (2026-11-08, verified):

- **Actual behaviours established first** (not assumed from names): `POST /auth/verify` returns **HTTP 200** `{"valid": false, "user_id": null, "email": null}` for missing/malformed/non-Bearer credentials and for every JWT verification failure path (RS256 against Clerk JWKS, kid lookup, issuer + expiry validation; email optional) — it performs **no user synchronisation and no DB access** (that is `get_current_user`'s role, separately tested). `GET /auth/sign-in-url` derives `https://<issuer-without-scheme>/sign-in`, falling back to `https://clerk.accounts.com/sign-in` for `CHANGE_ME`/empty issuers. `GET /auth/callback` is a **documented placeholder** — `{"message", "note"}` body, no OAuth processing, no redirect; query params ignored; it does not authenticate.
- **Tests**: 12 new tests in `TestAuthEndpoints` (`tests/unit/test_backend.py`). Boundaries mocked: JWKS retrieval (`middleware._fetch_jwks`), `database.get_db_connection`, `dependencies.ensure_registered_user` (asserted never called — verification never creates users); everything else real (`TestClient(main.app)`, ClerkAuthMiddleware, generated RSA keypair + RS256 JWKS verification). `get_settings` lru-cache lifecycle handled per test (`_use_fresh_settings`).
- **Verified (actual)**: `TestAuthEndpoints` **12/12**; combined auth-related classes **52 passed**; full backend suite **200 passed, 0 errors** (was 188). One test expectation corrected during the run: on JWKS retrieval failure the fetch happens **twice** (middleware and endpoint verify independently) — asserted as such.
- **Production code changed**: none; no defects found in the auth endpoints.
- **Not claimed**: live Clerk authentication (mocked JWKS + test-key-signed JWTs ≠ real Clerk instance); frontend Clerk SDK flows.
- **Not complete**: `test_database_integration.py` hang (next task), real-service integration (credentials). Nothing staged or committed; `main` @ `a834c33`.

Completed Milestone 11 task 2 — Guest-session tests made genuine (2026-11-08, verified):

- **Prior state**: all 5 `TestGuestSession` tests in `tests/unit/test_backend.py` were vacuous — they patched `database.create_guest_session`/`validate_guest_session`/`increment_guest_analysis_count`, called the patch, and asserted the mock's return value; the real implementation was never executed.
- **Replaced by 16 genuine tests** (with deeper detail in `agent_context/ACTIVE_TASK.md`): 11 data-layer tests (real guest-session code, only the DB boundary mocked) covering creation (real `secrets.token_urlsafe(32)` 43-char token, ~24h expiry, INSERT text/params, commit, `expiration_hours=0` → settings fallback 24h), validation (valid SELECT with `is_active = TRUE` predicate + no commit; unknown token → None; expired → None + second-connection `UPDATE ... SET is_active = FALSE WHERE id = %s` + commit; naive `expires_at` read as UTC), increment (atomic guard clauses verified verbatim incl. `RETURNING analyses_count`; at-limit 0-row → None), and the real connection scaffold (`DatabaseError` wrapping, rollback+close never committing on statement failure, commit+`finally` close on the happy path). Plus 5 `TestGuestSessionRouter` endpoint tests: `GET /guest/session/validate` (active session state; missing header → `valid=false` with no DB call; invalid token → `valid=false`) and `POST /guest/session/consume-analysis` (consumed within allowance with `(session_id, max_analyses=3)` call shape; limit reached → `consumed=false`/remaining 0; missing header → 401 with no DB call).
- **Verified (actual)**: targeted guest-session tests **18 passed**; full `tests/unit/test_backend.py` **188 passed, 0 errors, 0 deselected** (was 177).
- **Flagged only (not fixed, out of scope)**: `routers/guest.py` annotates `request: Request` without importing `Request` (~line 245) — empirically harmless (annotations not evaluated eagerly; import/uvicorn verified) but unstable. Two write-side caveats learned by the failing runs: `token_urlsafe` may contain `-`/`_`, and patching `get_db_connection` bypasses its real `finally` scaffold so `closed` assertions require patching `psycopg2.connect` instead.
- **Not complete**: Milestone 11 "Authentication flows are tested" still open — `/auth` endpoint tests next, `test_database_integration.py` hang untouched, credentials unconfigured. Nothing staged or committed; `main` @ `a834c33`.

Completed Milestone 11 entry task — Fix FastAPI application entry point (2026-11-08, verified):

- **Root cause**: `main.py` defined `create_app()` but module-level `@app.on_event("startup")` and `@app.get("/")` referenced an `app` name never assigned → `NameError: name 'app' is not defined` on import; `TestGuestSessionRouter::test_create_guest_session` failed in `setup_class`; `uvicorn crack_detection.backend.main:app` could not run. (`python-multipart` is NOT the cause — it is installed, 0.0.10, in `.venv`.)
- **Changes**: `src/crack_detection/backend/main.py` — `_startup_event` registered inside `create_app()` (`app.add_event_handler("startup", _startup_event)`), root `GET /` moved into the factory, module-level `app = create_app()` added; handler behaviour preserved verbatim. `tests/unit/test_backend.py` — new `TestApplicationFactory` (3 tests: factory wiring incl. ClerkAuthMiddleware + `_startup_event` + key routes; module-level app import + distinct fresh instance; root endpoint served via `TestClient(main.app)`).
- **Verified (actual)**: targeted factory + guest-router tests **4/4 passed**; full backend suite with **no deselect: 177 passed, 0 errors** (was 173 passed + 1 setup error); import smoke OK; real `uvicorn crack_detection.backend.main:app --port 8123` → startup complete, `GET /` → 200 `{"service":"CrackSight AI","version":"0.1.0","status":"operational"}`.
- **Not complete**: Milestone 11 "Authentication flows are tested" still open — `/auth` endpoint tests missing, `TestGuestSession` tests vacuous, `test_database_integration.py` hang untouched (by instruction), credentials unconfigured. Nothing staged or committed; `main` @ `a834c33`.

Continuing Milestone 8, Task 6 — PDF report generation, steps 1–5 (2026-11-08, all verified):

- **Step 1**: ReportLab declared (`reportlab>=4.2.0,<5.0.0`; reportlab 4.5.1 + pypdf 7.0.0 test-only installed). Standalone generator `src/crack_detection/backend/report_generator.py`: dataclasses `PhotographReportEntry`/`InspectionReportData`/`ReportMetadata` + `generate_inspection_report_pdf(...) -> bytes` — A4, branded navy/teal header band + `Page X of Y` footer on every page, report metadata + inspection info tables, photograph summary, per-photograph blocks (AI prediction with `Model version (checkpoint epoch)` + image-space pixel measurements, separately labelled inspector observation), safety disclaimer box; graceful degradation for missing data/images; no physical units. **31/31 unit tests** (`tests/unit/test_report_generator.py`).
- **Step 2 (extension)**: generator accepts optional `page_count_sink`; the two-pass canvas page total is persisted into `reports.page_count` without parsing (pypdf stays test-only). 31/31 tests re-verified.
- **Step 3**: `POST /reports/generate/{inspection_id}` implemented in `src/crack_detection/backend/routers/reports.py` — `require_authenticated_user` (guest 403 / anonymous 401, zero SQL executed); opaque 404 for nonexistent ("Inspection not found") and foreign ("Resource not found" via `require_ownership`); Draft and Completed allowed; photographs fetched with internal R2 keys; originals/overlays downloaded (`StorageError` → 500 "Failed to retrieve photograph assets"); PDF generated in memory → uploaded to `reports/{report_id}.pdf` (`application/pdf`) → `INSERT INTO reports (id, inspection_id, user_id, report_pdf_key, page_count) RETURNING id, generated_at` + commit → `ReportGenerateResponse(report_id=row["id"], generated_at=row["generated_at"], download_url="/reports/{row['id']}/download")`; internal keys never exposed. Compensation: upload failure → best-effort PDF delete, no row; DB failure → best-effort PDF delete (cleanup failures logged, original error preserved), 500. **13 new tests** (`TestReportGeneration` via `_reports_app` + `_report_storage` + `_SeqConn`) — 13/13 passed.
- **Verified totals (steps 1–3)**: backend suite **153 passed** (1 pre-existing unrelated error deselected: `TestGuestSessionRouter::test_create_guest_session` module-level `app` NameError in `main.py:82`); report-generator **31/31**; inference **17 passed**. Nothing staged/committed; `main` @ `a834c33` + prior uncommitted work preserved.
- **Step 4**: `GET /reports/{report_id}/download` implemented in the same router — `require_authenticated_user` (guest 403 / anonymous 401); single ownership-scoped query through the associated inspection; nonexistent → 404 "Report not found", foreign → 404 "Resource not found" via `require_ownership` (both opaque, storage never contacted); actual PDF bytes streamed from R2 (`StorageError` incl. missing object → 500 "Failed to retrieve report", established convention); response `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="cracksight-report-{report_id}.pdf"`; internal R2 keys never exposed. **8 new tests** (`TestReportDownload`) — 8/8 passed.
- **Step 5**: inspection-deletion interplay fixed — `database.py`: `fk_reports_inspection` now `ON DELETE CASCADE` (fresh DBs) + an idempotent guarded DO-block constraint-swap statement for existing deployments (fires only when the constraint lacks the cascade rule; mocked-only coverage via `init_schema` against a fake recording connection). `delete_inspection` now fetches all `report_pdf_key` values before deleting and removes each report PDF from R2 first (idempotent `delete_file`; failures logged + 500 aborted **before** the DB DELETE so committed rows keep their keys for retry), then the existing photograph-prefix cleanup and `DELETE FROM inspections` + commit with cascade. Storage-before-DB ordering documented: a later DB failure leaves rows pointing at deleted PDFs (recoverable, logged, retryable) instead of unrecoverable post-commit R2 orphans. **12 new tests** (migration 3 + deletion 8 + download-after-deleted 1) — 12/12 passed.
- **Verified totals**: backend suite **173 passed** (1 pre-existing unrelated error deselected: `TestGuestSessionRouter::test_create_guest_session` module-level `app` NameError in `main.py:82`); report-generator **31/31**; inference **17 passed**. Nothing staged/committed; `main` @ `a834c33` + prior uncommitted work preserved.
- **Step 7 (frontend wiring, verified 2026-11-08)**: `frontend/src/services/api.ts` — `downloadReportPdf(reportId)` added, mirroring `downloadPhotographImage` (bearer token, blob URL from R2-streamed PDF bytes). `frontend/src/pages/InspectionDetailPage.tsx` — authenticated-users-only report card: generate + download actions with duplicate-click prevention, inline errors, `cracksight-report-{report_id}.pdf` anchor download, blob URL revoked after click; Draft and Completed both allowed; unauthenticated/guest users see no report actions. `frontend/src/pages/ReportsPage.tsx` — kept as clearly-labelled sample content; its "Generate report" CTA navigates to `/app/history`; no report-list endpoint fabricated. New tests: `InspectionDetailPage.test.tsx` (7), `ReportsPage.test.tsx` (3), plus `generateReport`/`downloadReportPdf` cases in `api.test.ts`. Frontend: **vitest 71 passed**, `tsc --noEmit` clean, `oxlint` clean, `vite build` OK. All frontend report tests mock the API client — real R2/PostgreSQL integration remains deployment-time.
- **Verified totals**: backend suite **173 passed** (1 pre-existing unrelated error deselected); report-generator **31/31**; inference **17 passed**; frontend **71 passed**. Nothing staged/committed; `main` @ `a834c33` + prior uncommitted work preserved.

Completed Milestone 8, Task 5 — Implement monthly allowance + fair-use protection (Deliverable 5) — see the Task 5 record below; verified 2026-11-08.

Completed Milestone 8, Task 4 — Implement backend date/structure-type/verification-status filters (Deliverable 8):

- Backend `list_inspections` now supports date/structure-type/verification-status filters with proper validation, EXISTS subqueries, and correct total count (pagination fix).
- Frontend History page filter UI wired to backend params; client-side `filtered` memo retains only client-side query + status logic (structure/date/verification handled server-side).
- All 16 HistoryPage tests pass (including new structure-type, verification-status, date, and clear-filters interaction tests).
- 15 backend filter tests collected (written; skipped when deps unavailable).
- Backend `total` now returns filtered row count instead of page size; pagination works correctly with `limit=2` + 5 rows → `total=5`.
- Frontend API client `listInspections` passes all filter params in query string.
- `structure_type` and `verification_status` use EXISTS subqueries; date filter uses UTC midnight-to-exclusive-next-day boundary.

Continuing from Milestone 8, Task 1.4 — Analysis persistence and versioning corrections (including corrective review):
- `analyse_photograph` persists actual calculated `pixel_measurements` into both `prediction_versions` and `photographs`; the photograph record is updated with `prediction_mask_key`, `prediction_overlay_key`, `model_version`, `prediction_timestamp`, and `pixel_measurements`.
- `version_number` is assigned under a row lock (`FOR UPDATE`) as `COALESCE(MAX(version_number), 0) + 1` (first = 1, subsequent increment; concurrent attempts cannot collide; failed analyses consume nothing).
- `reanalyse_photograph` now runs a full analysis and creates the next version (previously it archived the old prediction and returned version 1).
- Registered-user idempotency: explicit `Idempotency-Key` header honoured when provided; deterministic key (`user_id` + `photo_id`) used as fallback so retries without a header are deduped. `/reanalyse` uses a fresh `uuid4()` key. Globally unique constraint retained.
- Guest allowance: `increment_guest_analysis_count` reserves before work; `decrement_guest_analysis_count` compensates on any failure (inference/R2/DB) so a failed attempt never permanently consumes allowance. Atomic conditional UPDATE guarantees at most three successful reservations. Idempotent retries consume no additional allowance. Guest behaviour and three-analysis allowance unchanged.
- `probability_map_key` made nullable via idempotent `ALTER TABLE ... DROP NOT NULL`.
- 23 focused tests added (`TestAnalysisPersistence`); full backend suite 88 passed, 1 pre-existing error (`python-multipart`); inference 17 passed.

Completed Milestone 8, Task 1.5 — Registered-user image downloads:

- `GET /photos/{photo_id}/download/{image_type}` (`download_photograph_image`) + helper `_download_registered_image` in `src/crack_detection/backend/routers/photographs.py`. Supported types: `original`, `mask`, `overlay`.
- `require_authenticated_user`: unauthenticated → 401; guest → 403; registered user proceeds.
- Single ownership-scoped query (`... JOIN inspections i ... WHERE p.id = %s AND i.user_id = %s`) → nonexistent/foreign photographs both 404 (no disclosure). Auth + ownership enforced before any R2 access.
- Unsupported type → 400 before DB/storage. `original` → `original_image_key`; `mask`/`overlay` → `prediction_mask_key`/`prediction_overlay_key`; NULL key → 404 "not available" (photo without a successful prediction still serves its original).
- Existing `R2Storage.download_file` (no presigned URLs; matches existing authenticated backend download pattern). `StorageError` → 500. Returns image bytes via `Response` with `Content-Disposition` attachment header, matching the existing guest download-response convention.
- 12 focused tests added (`TestRegisteredUserImageDownload`): successful original/mask/overlay download, unauthenticated (401), guest (403), foreign photograph (404), nonexistent photograph (404), unsupported type (400), missing mask/overlay (404), R2 object missing (500), R2 storage failure (500).
- Full backend suite → 100 passed, 1 pre-existing error (`python-multipart`); no regressions to Tasks 1.1–1.4. Storage is mocked in tests; no real R2 integration claimed.

Completed Milestone 8 deliverable — Add photographs to an inspection (structure type per photo):

- `POST /photos/{inspection_id}/upload` (`upload_photograph`) + helpers `_store_uploaded_photograph` and `_validate_uploaded_image` in `src/crack_detection/backend/routers/photographs.py`.
- `require_authenticated_user`: unauthenticated → 401; guest → 403; registered user proceeds.
- Inspection existence (404), ownership (403 opaque), draft eligibility (400 for completed — photographs are not added to completed inspections).
- Structure type validated against `wall`/`beam`/`column`; file validated by extension, size (`max_upload_size_bytes`), and PIL image content (not just filename/MIME).
- Original image stored in private R2 at `inspections/{inspection_id}/originals/{photo_id}.{ext}`; photograph record persisted in PostgreSQL (user, inspection, structure type); returned as `PhotographResponse`.
- Failure handling: R2 upload failure → no photograph record; DB persistence failure after successful R2 upload → newly uploaded R2 object deleted (best-effort); prior photographs/prediction versions untouched.
- Multipart body parsed via `await request.form()` (call-time) so the module stays importable where `python-multipart` is unavailable; production installs `python-multipart`.
- 13 backend tests added (`TestRegisteredUserPhotographUpload`) covering success, structure persistence, ownership, foreign/nonexistent inspection, completed rejection, unsupported type/format/content, file size, R2 failure, DB failure + cleanup, unauth/guest.

Frontend:
- `frontend/src/types/index.ts`: added `PhotographMetadataResponse`, `PhotographListResponse`.
- `frontend/src/services/api.ts`: added `listInspectionPhotographs`, `uploadPhotograph`, `downloadPhotographImage`.
- `frontend/src/pages/InspectionDetailPage.tsx`: connected to backend — photo list, upload form with preview/structure select/upload state/errors, refreshes list on success, completed inspections read-only, sign-in prompt.
- 4 frontend API tests added (`api.test.ts`).
- Frontend build, lint, and 22 tests pass; backend suite 113 passed (1 pre-existing unrelated `python-multipart` error), inference 17 passed; no regressions.

Completed Milestone 8 verification — Registered inspection results persist beyond 24 hours:
- Requirement already satisfied by existing implementation; no code changes necessary.
- `inspections`, `photographs`, `prediction_versions`, `users` tables have no `expires_at` / no time-based deletion; only `guest_sessions` carries the 24-hour expiry.
- `cleanup_expired_guest_sessions()` only deactivates `guest_sessions` rows; never touches registered tables or R2 objects.
- Registered R2 keys use `inspections/{inspection_id}/...` prefix (guest uses `guest/{session_token}/...`).
- Retrieval endpoints are ownership-scoped with no time filter.
- 4 backend tests added (`TestRegisteredUserPersistenceBeyond24Hours`): no-expiry schema, cleanup isolation, photo listing/download after simulated >24h age.
- Backend suite now 117 passed (113 + 4 new), 1 pre-existing unrelated error; no regressions.

## Current State

- Model, data pipeline, and backend Milestones 2–5 implemented.
- Milestone 8 Tasks 1.1 (identity sync), 1.2 (reopen), 1.3 (photo listing), 1.4 (analysis persistence/versioning), 1.5 (registered-user image downloads), the photograph-upload deliverable, and the persistence-beyond-24h verification implemented as uncommitted working-directory changes against `main` @ `a834c33`. Task 6 (PDF reports) steps 1–5 are now also implemented (see Most Recent Work).

## Important Boundaries

- Do not modify the trained model, checkpoint, datasets, or inference pipeline for frontend work.
- The browser calls the FastAPI backend via the typed API client; it never loads the checkpoint or calls the inference service directly.
- Continue to distinguish AI predictions from inspector observations.
- Do not imply structural safety, introduce severity classifications, or report physical dimensions without calibration.
- Preserve Draft/Completed workflow; Completed inspections are read-only until reopened.
- Guest session creation/validation IS connected to the backend; photograph upload to an inspection IS connected (Milestone 8 upload deliverable). Inspection creation and PDF report generation/download actions are wired to the backend (verified against mocked tests); real-service integration remains deployment-time.
- Do not overwrite or stage unrelated existing untracked project files.

## Known Follow-up Work

- Milestone 7: Connect guest photo upload, analysis, and results to FastAPI backend (`POST /photos/{id}/analyse`, `GET /photos/{id}`, etc.).
- Milestone 8: Registered-user inspection management with persistence (largely complete; see Deliverable status in CURRENT_STATE.md).
- Milestone 9: Dashboard/history backed by real user data (connected and verified).
- Milestone 8 Task 6 (Deliverable 6 — COMPLETE): backend ReportLab generator + generate/download endpoints + FK cascade + R2 PDF cleanup on inspection deletion, plus frontend wiring (InspectionDetailPage report card, ReportsPage honest copy). Real-service integration verification of the FK migration and R2 cleanup remains deployment-time.
- Backend upload file-size/dimension limits need a configured source of truth.
- External Neon, R2, and Clerk integrations not configured for production validation.

## Most Recent Work

Completed Milestone 8, Task 4 — Implement backend date/structure-type/verification-status filters (Deliverable 8):

**Backend (`src/crack_detection/backend/routers/inspections.py`)**:
- Added `VALID_STATUSES`, `VALID_STRUCTURE_TYPES`, `VALID_VERIFICATION_STATUSES` constants.
- Added query params: `status` (alias `status_filter`), `structure_type`, `verification_status`, `date_from`, `date_to` (all optional).
- Invalid enum values → `ValidationError` (HTTP 400).
- Structure type + verification status filters use `EXISTS (SELECT 1 FROM photographs p WHERE p.inspection_id = i.id AND p.structure_type = %s / p.verification_status = %s)` subqueries.
- Date filter: `created_at >= date_from` (UTC midnight) and `created_at < date_to + 1 day` (exclusive upper bound → inclusive end date); absent params = no date filter.
- `total` in `InspectionListResponse` now returns filtered row count (separate count query), not page size; LIMIT/OFFSET pagination on the page query.

**Frontend (`frontend/src/services/api.ts`)****: `listInspections` accepts `search`, `status`, `structure_type`, `verification_status`, `date_from`, `date_to`, `limit`, `offset`; passes via URLSearchParams (undefined omitted).
**Frontend (`frontend/src/pages/HistoryPage.tsx`)****: Added verification-status filter select (snake_case values); `fetchInspections` passes all filter params to `apiClient.listInspections()`; `filtered` memo retains only client-side query + status; Clear filters resets all.

**Backend tests (`tests/unit/test_backend.py`)** — `TestInspectionListFiltering` class with 15 tests: unfiltered, search, status valid/invalid, structure_type valid/invalid, verification_status valid/invalid, date_from, date_to, combined AND filters, total-vs-page-size, owner isolation, guest, pagination.

**Frontend tests**: `api.test.ts` filter-param pass-through; `HistoryPage.test.tsx` 16 tests including new structure-type, verification-status, date, clear-filters interaction tests.

**Verification (actual, 2026-11-08):**
- Backend filtering tests: **15 passed** (genuine execution with `PYTHONPATH=src`; previously skipped due to import path). No production code defects — test infrastructure fixed only (`_SeqConn` count-row separation, `_sample_inspection_row` UUID derivation).
- Backend full suite: **135 passed, 1 pre-existing error** (unrelated `TestGuestSessionRouter` module-level `app` reference in `main.py`).
- Frontend: **57/57 passed**, `tsc --noEmit` clean, `npm run lint` clean.

Completed Milestone 8, Task 5 — Implement monthly allowance + fair-use protection (Deliverable 5):

**Config (`src/crack_detection/backend/config.py`)**:
- Added `registered_monthly_analyses_limit` setting (default 100, env `REGISTERED_MONTHLY_ANALYSES_LIMIT`).

**Database (`src/crack_detection/backend/database.py`)**:
- Added `user_usage` table `(user_id, month_key YYYY-MM, analyses_count, updated_at)` with composite PK `(user_id, month_key)` and FK to `users(id)`.
- Added `increment_user_analysis_count`, `decrement_user_analysis_count`, `get_user_monthly_usage`, `_current_month_key` helpers.

**Router (`src/crack_detection/backend/routers/photographs.py`)**:
- `analyse_photograph` checks/increments registered-user monthly allowance before persistence; raises HTTP 429 when limit exceeded; compensates (decrements) on failure so failed attempts never consume allowance.

**Tests (`tests/unit/test_backend.py`)** — 5 new registered-allowance tests in `TestAnalysisPersistence`, all **5/5 passed**.

**Verification (final, 2026-11-08):**
- Backend `TestAnalysisPersistence` registered-allowance tests: **5/5 passed**.
- Backend full suite: **140 passed, 1 pre-existing error** (unrelated `TestGuestSessionRouter` module-level `app` reference in `main.py`).
- Backend `TestInspectionListFiltering` (Task 4): **15/15 passed** (still verified).
- Inference tests: **17 passed**.
- Frontend: **57/57 passed**, `tsc --noEmit` clean, `npm run lint` clean.

Completed Milestone 8, Task 2 — Declare python-multipart and standardise ownership responses (Deliverable 2):

**Part A — `python-multipart` dependency:**
- `requirements.txt`: Added `python-multipart>=0.0.9,<0.0.11` in the "Backend dependencies (Milestone 2)" section, compatible with FastAPI 0.104–0.115. Declared for production deployments; not installed locally (documented environment issue).

**Part B — Standardise foreign-resource responses to opaque 404:**
- `src/crack_detection/backend/dependencies.py`: Modified `require_ownership` — guest rejection stays 403; foreign-resource case changed from 403 to 404 with detail "Resource not found". Foreign and nonexistent resources are now indistinguishable.
- This single shared-boundary change affects all callers: `upload_photograph`, `complete_inspection`, `update_inspection`, `delete_inspection`, `update_photograph`, `remove_photograph`, `reanalyse_photograph`, `analyse_photograph`.

**Tests:**
- Updated `test_foreign_inspection_ownership_rejected` to expect 404 (was 403).
- Added `TestForeignOwnershipStandardisation` (2 tests): `update_inspection` foreign → 404, `delete_inspection` foreign → 404.
- Added `test_update_photograph_foreign_ownership_rejected` in `TestRegisteredUserPhotographUpload`: `update_photograph` foreign → 404.

**Verification (actual):**
- Backend `tests/unit/test_backend.py`: 120 passed (117 prior + 3 new), 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`, documented, unrelated). No regressions.
- `tests/unit/test_inference.py`: 17 passed (unchanged).

**Updated deliverable statuses:**
- Deliverable 1 (inspection creation): COMPLETE — backend + frontend connected
- Deliverable 2 (photographs): COMPLETE — backend done + frontend connected; `python-multipart` declared; foreign-ownership status standardised to opaque 404
- Deliverable 3 (persist beyond 24h): COMPLETE (verified)
- Deliverable 4 (dashboard/history): COMPLETE — backend done + frontend connected with real authenticated data
- Deliverable 5 (monthly allowance): COMPLETE — guest 3-analysis limit; registered-user monthly allowance with atomic enforcement, failure compensation, and 429 on limit exceeded
- Deliverable 6 (PDF reports): COMPLETE — ReportLab generator, generate/download endpoints, FK cascade, R2 PDF cleanup on inspection deletion, and frontend wiring (InspectionDetailPage report card, ReportsPage honest copy); real-service integration remains deployment-time
- Deliverable 7 (history list/card): COMPLETE — views connected to real backend data; list/card views, search, filters tested
- Deliverable 8 (filtering): COMPLETE — backend date/structure-type/verification-status filters implemented with validation + EXISTS subqueries + correct total count; frontend filter UI wired to backend params

**Revised implementation sequence (recorded in ROADMAP.md Milestone 8):**
1. ✅ Connect frontend inspection creation to backend (Deliverable 1) — COMPLETE
2. ✅ Declare `python-multipart` + fix foreign-ownership status consistency (Deliverable 2) — COMPLETE
3. ✅ Connect dashboard + history to real backend data (Deliverables 4 & 7) — COMPLETE
4. ✅ Implement backend date/structure-type/verification filters (Deliverable 8) — COMPLETE
5. Implement monthly allowance + fair-use (Deliverable 5)
6. Implement PDF report generation/download (Deliverable 6)


## Current State

- Model, data pipeline, and backend Milestones 2–5 implemented per `CURRENT_STATE.md`.
- Milestone 8 Tasks 1.1 (identity sync), 1.2 (reopen), 1.3 (photo listing), 1.4 (analysis persistence/versioning), 1.5 (registered-user image downloads), the photograph-upload deliverable, the persistence-beyond-24h verification, and Task 4 (backend filters + frontend wiring) implemented as uncommitted working-directory changes against `main` @ `a834c33`. Task 6 (PDF reports) steps 1–5 also implemented.

## Important Boundaries

- Do not modify the trained model, checkpoint, datasets, or inference pipeline.
- The browser calls the FastAPI backend via the typed API client; it never loads the checkpoint or calls the inference service directly.
- Continue to distinguish AI predictions from inspector observations.
- Preserve Draft/Completed workflow; Completed inspections are read-only until reopened.
- Guest session creation/validation IS connected to the backend; photograph upload to an inspection IS connected. Dashboard/history real data connected via `apiClient.listInspections()`. Monthly allowance is NOT connected; PDF report actions ARE wired on InspectionDetailPage (calling apiClient) with backend contracts verified separately.
- Do not overwrite or stage unrelated existing untracked project files.

## Known Follow-up Work

- Milestone 7: Connect guest photo upload, analysis, and results to FastAPI backend (`POST /photos/{id}/analyse`, `GET /photos/{id}`, etc.).
- Milestone 8: Registered-user inspection management (largely complete; see Deliverable status in CURRENT_STATE.md).
- Milestone 9: Dashboard/history backed by real user data (connected and verified).
- Backend upload file-size/dimension limits need a configured source of truth.
- External Neon, R2, and Clerk integrations not configured for production validation.

