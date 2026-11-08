# TASK HISTORY — Completion Records

## 2026-11-08 — Milestone 11: Database integration-suite repair (`tests/unit/test_database_integration.py`)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Task:** Fix the hanging database-integration suite, its ineffective foreign-key test, and its malformed test definitions; introduce proper transaction isolation/cleanup.

**Root cause (established before changing anything):**
1. The session-scoped `db_conn` fixture connected with autocommit disabled and had no commit/rollback lifecycle; tests that inserted via the shared connection (e.g. `test_create_and_read_inspection`) left the connection **idle in transaction**.
2. `init_schema()` executes DDL on its own connection. On a database where `fk_reports_inspection` lacked `ON DELETE CASCADE`, its guarded DO-block swap (`ALTER TABLE reports DROP CONSTRAINT …; ADD CONSTRAINT … ON DELETE CASCADE`) requests locks that conflict with the shared connection's uncommitted `inspections` transaction → indefinite wait. Historical reproduction: 3 tests passed, then `TestDatabaseCRUD::test_create_photograph` (whose `init_schema()` fires the swap) hung ≥150s in full-suite and isolated runs.
3. Causality probe today: an open uncommitted transaction held while calling `init_schema()` completed instantly, because `xportra_test` already carries the CASCADE FK (migrated during an earlier session's execution). The transaction-lifecycle defects remained real: aborted transactions after failed assertions, and guest-helper rows (created+committed on the helpers' own connections) accumulating — 6 stale expired rows from 2026-11-02/03 were present. Fixture conclusion: the session-scoped connection stays; the smallest reliable correction is a per-test transaction envelope.

**Files changed:** `tests/unit/test_database_integration.py` only. No production code changed.

**Corrections:**
- New autouse function-scoped fixture `rollback_db_transaction(db_conn)`: rollback before and after every test (no lingering/aborted transactions, no DDL waits possible, test rows never persisted; committed application data untouched — no TRUNCATE/DROP anywhere).
- `_delete_test_guest_session(session_id)`: targeted DELETE-by-id (own connection, commit) called in `finally` by each guest-session test, since guest helpers commit outside the shared connection's transaction. Runs are now idempotent; nothing accumulates.
- CRUD tests use uuid-suffixed user ids/emails for rerun idempotency (fixed `user-1`/`user-2` values).
- `test_foreign_key_constraint` rewritten: a real user is inserted first (only `fk_photographs_inspection` can then be violated), `pytest.raises(psycopg2.errors.ForeignKeyViolation)` (SQLSTATE 23503) replaces the old `pytest.raises(Exception)` that was actually catching its own `conn.commit()` NameError, an in-test `db_conn.rollback()` clears the aborted transaction, and a COUNT assertion proves no partial write.
- `test_validate_guest_session_expiration` moved OUT of module scope INTO `TestGuestSession`; the previously nested `def test_increment_analysis_count` (never collected) promoted to a real method. The expiration UPDATE commits so `validate_guest_session`'s separate connection observes the expiry; the created row is then deleted whole.

**Verification (actual; all against the real local PostgreSQL `xportra_test` — no mocked database calls):**
- Collection: **9 tests** (before: 8; the promoted `test_increment_analysis_count` newly collected).
- Previously affected tests individually: **5/5 passed**.
- Full integration file: **9 passed**, three consecutive runs — 16.67s, 11.24s, 9.26s (rerun-independent; no leftover state dependencies).
- Post-run DB integrity: `users`/`inspections`/`photographs` = 0 rows; `guest_sessions` = the same 6 pre-existing stale expired rows (zero new accumulation).
- Full backend regression: `tests/unit/test_backend.py` **200 passed, 0 errors**.
- One verification attempt (run 2, piped through the shell harness) occasioned a 300s timeout; the two immediately following runs completed quickly, and a process/activity check showed no lingering connections — concluded to be a shell-pipeline artifact of the harness, not the suite (documented honestly rather than hidden).

**Remaining limitations:** the 6 stale expired guest_sessions rows from historical runs were left untouched (no broad cleanup authorised; removable via the product's `cleanup_expired_guest_sessions()`). `TestGuestSessionRouter` inside the integration file remains a mocked duplicate of a unit-suite test (not integration; left as-is). Registered-user end-to-end flows via real Clerk/Neon/R2 remain blocked on credentials.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 11: Behavioural tests for `/auth` router endpoints (`/auth/verify`, `/auth/sign-in-url`, `/auth/callback`)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Task:** Add genuine behavioural endpoint tests for the three `/auth` routes (previously untested at the HTTP level; `TestClerkJWTVerification` covered only the `_verify_clerk_jwt` middleware helper directly).

**Behavior established by inspection before writing tests (routers/auth.py, middleware.py):**
- `POST /auth/verify`: missing / non-Bearer / empty-Bearer credentials → **HTTP 200** `{"valid": false, "user_id": null, "email": null}` (fail-closed identity shape, not 401). Bearer tokens are verified through `_verify_clerk_jwt` (RS256 signature via Clerk JWKS with kid lookup, issuer + expiration enforced, `aud` not verified, optional email); any error → the same invalid identity shape. The endpoint performs **no identity synchronisation and no database access** — user-sync lives in `get_current_user` (covered by existing sync tests).
- `GET /auth/sign-in-url`: `https://<issuer-without-scheme>/sign-in` when the issuer is set and doesn't contain `CHANGE_ME`; fallback `https://clerk.accounts.com/sign-in` otherwise.
- `GET /auth/callback`: route-completeness **placeholder** — returns `{"message", "note"}` with no OAuth/token processing, no redirect, no auth-state change; sign-in is delegated to Clerk's hosted pages and frontend SDK. Tested as-is with this limitation documented; no test implies it authenticates.

**Files changed:** `tests/unit/test_backend.py` only (no production code changes).

**Tests (12, new `TestAuthEndpoints` after `TestClerkJWTVerification`):** external boundaries mocked — `middleware._fetch_jwks` (JWKS retrieval), `database.get_db_connection` and `dependencies.ensure_registered_user` (asserted **never called**, documenting that verification alone performs no user creation/sync). The real endpoints (via `TestClient(main.app)`), `ClerkAuthMiddleware`, the `get_settings` lru-cache lifecycle (`_use_fresh_settings` per-test context), and full RS256 JWKS verification over a generated RSA keypair all execute for real.
- `/auth/verify` ×8: valid token (identity body, exact response-model keys, fetch exactly once, no DB); missing/malformed credentials grouped ×4 sub-cases with zero fetches; invalid signature (foreign key, matching kid, cache hit → no fetch); expired token; issuer mismatch; unknown kid; JWKS retrieval failure → fail-closed (`fetch.call_count == 2` — middleware and endpoint each verify the Bearer token independently); unconfigured issuer/JWKS → fail-closed before any fetch. All failure tests assert the invalid identity shape and zero DB interaction.
- `/auth/sign-in-url` ×2: derived URL from configured issuer; `CHANGE_ME` and empty-issuer fallbacks.
- `/auth/callback` ×2: exact placeholder body, no `Location` header, no DB; query parameters (`code`/`state`) ignored (identical body).

**Verification (actual):**
- `TestAuthEndpoints`: **12/12 passed** (one initial assertion corrected by its failing run: the JWKS-failure case fetches twice because both the middleware and the endpoint verify the Bearer token — asserted as genuine behaviour, not weakened).
- Combined authentication-related classes (`TestClerkJWTVerification`, `TestAuthEndpoints`, `TestGuestSession`, `TestGuestSessionRouter`, `TestApplicationFactory`, `TestEnsureRegisteredUser`, `TestGetCurrentUserSync`, `TestInspectionCreationBlockedOnSyncFailure`): **52 passed**.
- Full `tests/unit/test_backend.py`: **200 passed, 0 errors, 0 deselected** (was 188).

**Not claimed complete:** Milestone 11 "Authentication flows are tested (guest + registered)" is now covered at mocked level (guest flows, Clerk-registered JWT verification, /auth endpoints, identity sync fail-closed behaviour), but real-Clerk-instance validation (and frontend Clerk SDK flows) is blocked on credentials and NOT claimed. Remaining Milestone 11 work: `tests/unit/test_database_integration.py` hang (next task); real-service integration validation (deployment-time).

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 11: Guest-session tests made genuine (`tests/unit/test_backend.py`)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Task:** Replace the 5 vacuous `TestGuestSession` tests — each patched `database.create_guest_session`/`validate_guest_session`/`increment_guest_analysis_count`, called the patch, and asserted the mocked return value — with genuine behavioural tests of the real implementation. Sequencing note: `ACTIVE_TASK.md` had listed `/auth` endpoint tests first, but `ROADMAP.md` imposes no ordering within the open authentication criterion (`:376`); per `agent_context/DEVELOPMENT_RULES.md` corrective-first practice, remediating untrustworthy tests preceded new test areas.

**Files changed:** `tests/unit/test_backend.py` only (no production code touched).

**Replaced with 11 genuine data-layer tests** (boundary `get_db_connection`/`psycopg2.connect` mocked; real guest-session code executed):
- Creation ×2: real `secrets.token_urlsafe(32)` token (43 chars; not fabricated), expiry ≈ now(utc)+24h, INSERT text (`VALUES (%s, %s, 0, TRUE)`, full RETURNING list) + params, returned row equality, commit; `expiration_hours=0` falls back to the configured default (24h).
- Validation ×4: valid session returned with `WHERE session_token = %s AND is_active = TRUE` SQL verified and no commit on the read path; unknown token → `None` (single SELECT); expired (aware) → `None` plus second-connection `UPDATE guest_sessions SET is_active = FALSE WHERE id = %s` + commit; naive (tz-less) `expires_at` interpreted as UTC.
- Increment ×2: within-limit → new count with the atomic guard verified verbatim (`WHERE id = %s` / `AND is_active = TRUE` / `AND analyses_count < %s` / `AND expires_at > NOW()` / `RETURNING analyses_count`, params `(session_id, max_analyses)`) + commit; 0-row (at limit) → `None`.
- Scaffold ×2: patched `psycopg2.connect` so the real `get_db_connection` contextmanager runs — connection failure → wrapped `DatabaseError` (no rollback possible, nothing committed); statement failure → rollback + close, wrapped in `DatabaseError`, never committed; plus a happy-path scaffold test proving commit + `finally` close. (Key learning: patching `get_db_connection` itself bypasses the real scaffold, so `closed` assertions are only valid with `psycopg2.connect` patched.)

**Plus 5 endpoint tests in `TestGuestSessionRouter`** (`TestClient(main.app)`; DB layer mocked at the `routers.guest` namespace — an external boundary; router logic genuine): `GET /guest/session/validate` — active session (`valid`/`session_id`/`analyses_count`/`analyses_remaining` computed by the router, header token passed verbatim), missing header → `valid=false` + zero remaining + no DB call, invalid/expired token → `valid=false`; `POST /guest/session/consume-analysis` — success (`consumed=true`, increment called with `(session_id, max_analyses=3)`), limit reached (`consumed=false`, remaining 0), missing header → 401 "Guest session token required" + no DB call.

**Verification (actual):**
- Targeted `-k "TestGuestSession or guest_session"`: **18 passed** (2 initial failures were in the new tests' own expectations and were corrected after inspecting real output: (a) `token_urlsafe` may legitimately contain `-`/`_` per the URL-safe base64 alphabet; (b) `closed`-state assertions moved out of `get_db_connection`-patched tests into `psycopg2.connect`-patched scaffold tests, since patching the contextmanager bypasses its real `finally`).
- Full `tests/unit/test_backend.py`: **188 passed, 0 errors, 0 deselected** (was 177 after the entry-point fix).

**Flagged production observations (no fix, out of scope):** `routers/guest.py` (~line 245) annotates `request: Request` without importing `Request` — harmless today because annotations are not evaluated eagerly (import/`create_app`/uvicorn verified), but unstable; `tests/unit/test_database_integration.py` also contains a nested test function that is never collected. The integration suite remains untouched and still hangs.

**Not claimed complete:** Milestone 11 "Authentication flows are tested (guest + registered)" remains open — next: `/auth` endpoint tests; then the integration-suite hang; real-service (Neon/R2/Clerk) validation stays blocked on credentials.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 11: FastAPI application entry point fix (`crack_detection.backend.main:app`)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Root cause:** `src/crack_detection/backend/main.py` defined `create_app()` but the module-level `@app.on_event("startup")` handler (line 82) and `@app.get("/")` root route referenced an `app` name that was never assigned — `from crack_detection.backend.main import app` raised `NameError: name 'app' is not defined`, `TestGuestSessionRouter::test_create_guest_session` failed in `setup_class`, and the documented `uvicorn crack_detection.backend.main:app` entry point could not work. (Note: despite several context notes blaming "missing python-multipart", `python-multipart==0.0.10` is installed in `.venv` and `import multipart` succeeds — multipart was never the cause.)

**Files changed:**
- `src/crack_detection/backend/main.py` — startup handler is now a plain module-level `async def _startup_event()` registered inside `create_app()` via `app.add_event_handler("startup", _startup_event)`; the root `GET /` route moved inside `create_app()`; new module-level `app = create_app()` at the end of the module exposes the Uvicorn entry point. Handler behaviour preserved verbatim (reset pipeline for testing, timed load, catch-and-log failure, `_pipeline_loaded_at` global).
- `tests/unit/test_backend.py` — new `TestApplicationFactory` (3 tests): `create_app()` wiring (FastAPI instance, title, `_startup_event` in `on_startup`, `ClerkAuthMiddleware` in `user_middleware`, root + `/guest/session` + `/reports/generate/{inspection_id}` routes), module-level `app` importable and distinct from a fresh `create_app()` instance, root endpoint served by `TestClient(main.app)` (200, `CrackSight AI` / `operational` / `0.1.0`).

**Verification (actual):**
- Targeted: `TestApplicationFactory` + `TestGuestSessionRouter::test_create_guest_session` → **4/4 passed** (one initial test-assertion fix: starlette `user_middleware` entries are `Middleware` wrappers — assert on `.cls`, not the instance class).
- Full `tests/unit/test_backend.py` with **no deselect**: **177 passed, 0 errors** (previously 173 passed + 1 pre-existing setup error; 174 original tests now all green + 3 new).
- Import smoke: `from crack_detection.backend.main import app` → `app.title == "CrackSight AI"`, startup handlers `['_startup_event']`.
- Real server check: `python -m uvicorn crack_detection.backend.main:app --port 8123` → "Application startup complete", `GET /` → **200** `{"service":"CrackSight AI","version":"0.1.0","status":"operational"}`.

**Not claimed complete:** Milestone 11 and its "Authentication flows are tested (guest + registered)" criterion remain NOT complete. Remaining gaps, left for subsequent tasks: no `/auth` router endpoint tests (`/auth/verify`, `/auth/sign-in-url`, `/auth/callback`); several `TestGuestSession` tests are vacuous (they patch `database.create_guest_session`/`validate_guest_session` then call the patch and assert the mock); `tests/unit/test_database_integration.py` still hangs on the session-scoped connection (untouched this task by instruction); frontend Clerk SDK flows are mock-tested only and external Neon/R2/Clerk credentials remain unconfigured.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 8, Task 6: PDF report frontend wiring — step 7 (Deliverable 6 complete on mocked-backend boundary)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `frontend/src/services/api.ts` — added `downloadReportPdf(reportId)` mirroring `downloadPhotographImage`: `GET /reports/{reportId}/download` with bearer token, `ApiError` on failure, PDF blob → `URL.createObjectURL`.
- `frontend/src/pages/InspectionDetailPage.tsx` — authenticated-users-only report card: `generatingReport`/`reportError`/`reportNotice`/`generatedReportId`/`downloadingReport` states; `handleGenerateReport` (duplicate-click prevention, retry after failure); `handleDownloadReport` (anchor click, `download="cracksight-report-{report_id}.pdf"`, blob URL revoked after click); renders for Draft AND Completed inspections; hidden for unauthenticated/guest users.
- `frontend/src/pages/ReportsPage.tsx` — honest copy: clearly-labelled sample content; "Generate report" CTA navigates to `/app/history`; no report-list endpoint fabricated (none exists on the backend).
- `frontend/src/services/api.test.ts` — added `generateReport` (URL/method/bearer; 404 → ApiError) and `downloadReportPdf` (URL, bearer, blob URL, ApiError) tests.
- `frontend/src/pages/InspectionDetailPage.test.tsx` — NEW, 7 tests: render intact, unauthenticated hiding, Draft+Completed visibility, generate success + duplicate prevention, generate failure + retry, download calls `downloadReportPdf` with report ID and filename assertion, download failure.
- `frontend/src/pages/ReportsPage.test.tsx` — NEW, 3 tests: honest demo messaging, navigation to `/app/history` without calling `generateReport`, download guidance calls no backend.

**Verification (actual):**
- Frontend `vitest run`: **71 passed** (8 files; baseline 57 + 14 new).
- Frontend `tsc --noEmit`: clean.
- Frontend `oxlint`: clean.
- Frontend `vite build`: OK.
- Backend suite unchanged (no backend changes this step): **173 passed** (1 pre-existing unrelated error deselected: `TestGuestSessionRouter::test_create_guest_session` module-level `app` NameError in `main.py:82`); `tests/unit/test_report_generator.py`: 31/31; `tests/unit/test_inference.py`: 17 passed.
- All frontend report tests mock the API client; real PostgreSQL/R2 integration remains deployment-time.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---


**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `src/crack_detection/backend/database.py` — `reports` CREATE TABLE FK `fk_reports_inspection` now includes `ON DELETE CASCADE` (fresh databases); new idempotent DO-block statement for existing deployments (guarded by `information_schema.referential_constraints` `delete_rule <> 'CASCADE'`, then DROP + re-ADD with cascade; repeatable, no data touched, no other FKs affected).
- `src/crack_detection/backend/routers/inspections.py` — `delete_inspection` extended: report-PDF keys fetched before any deletion (`SELECT report_pdf_key FROM reports WHERE inspection_id = %s`), each PDF deleted from R2 (idempotent `delete_file`; failure → logged with original error + 500 "Failed to delete associated report files; the inspection was not deleted." **before** the DB DELETE so committed rows retain keys for retry); existing photograph-prefix cleanup and `DELETE FROM inspections` + commit unchanged in shape (FK cascade removes report rows in-transaction). Added module logger.
- `tests/unit/test_backend.py` — `_SeqConn` gained context-manager support; 12 new tests: `TestReportsForeignKeyCascadeMigration` (3), `TestInspectionDeletionWithReports` (8), `test_report_download_after_parent_inspection_deleted` (1).
- `agent_context/ACTIVE_TASK.md`, `CURRENT_STATE.md`, `HANDOFF.md`, `ROADMAP.md` — updated (Deliverable 6: PARTIAL steps 1–5).

**Failure/retry semantics chosen (documented in code):**
- R2 cleanup deliberately happens **before** the database DELETE (matching the endpoint's pre-existing photograph-cleanup ordering). PostgreSQL and R2 do not share a transaction; the trade-off: if the DB DELETE/commit later fails, `get_db_connection` rolls back → inspection + report rows remain pointing at now-deleted PDFs (report downloads return 500 until deletion is retried; re-deletes are R2 no-ops). This is a recoverable, explicitly logged inconsistency — preferred over post-commit R2 orphans, where rows are gone and keys are unrecoverable.
- Deletion attempts are repeatable: an already-deleted inspection 404s; already-deleted PDFs re-delete as no-ops.

**Verification (actual):**
- Step-5 tests: 12/12 passed (`TestReportsForeignKeyCascadeMigration` 3, `TestInspectionDeletionWithReports` 8, download-after-deleted 1).
- Combined backend + generator run: 204 passed, 1 pre-existing unrelated error (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`).
- `tests/unit/test_backend.py` with that error deselected: 173 passed (was 161 before step 5, +12).
- `tests/unit/test_report_generator.py`: 31/31 passed. `tests/unit/test_inference.py`: 17 passed.
- Coverage note: ALL tests are mocked (fake connections + in-memory storage fakes). The FK migration and R2 cleanup have NOT been integration-tested against real PostgreSQL/R2 (services not configured locally) — remaining deployment-time verification.
- Deliverable 6 NOT marked complete — step 7 (frontend wiring) outstanding.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 8, Task 6: PDF report download endpoint — step 4 (Deliverable 6, partial)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `src/crack_detection/backend/routers/reports.py` — `download_report` stub body replaced: `require_authenticated_user` dependency (was `get_current_user`), narrowed ownership-scoped query (`SELECT r.report_pdf_key, i.user_id FROM reports r JOIN inspections i ON r.inspection_id = i.id WHERE r.id = %s`), `StorageError` → 500 "Failed to retrieve report" per established convention, actual PDF bytes returned via FastAPI `Response` with `Content-Type: application/pdf` and `Content-Disposition: attachment; filename="cracksight-report-{report_id}.pdf"`. Generation endpoint untouched.
- `tests/unit/test_backend.py` — 8 new tests in `TestReportDownload` + helpers (`_report_download_row`, `_report_download_url`).
- `agent_context/ACTIVE_TASK.md`, `CURRENT_STATE.md`, `HANDOFF.md`, `ROADMAP.md` — updated (Deliverable 6 status: PARTIAL steps 1–4).

**What was implemented:**
- Guests (403) and unauthenticated requests (401) are rejected by the dependency before any SQL or storage access.
- Nonexistent reports → HTTPException 404 "Report not found"; foreign-owned → `require_ownership` 404 "Resource not found"; both opaque; R2 never contacted on either path.
- PDF streamed from private R2 using the internal `report_pdf_key`; `StorageError` (incl. missing `NoSuchKey` objects) → 500; internal key never appears in the response (verified per-header in tests).
- Report generation endpoint behaviour unchanged.

**Verification (actual):**
- `TestReportDownload`: 8/8 passed (mocked storage/DB endpoint tests — no real R2 or PostgreSQL integration; external services not configured locally).
- Combined backend + generator run: 192 passed, 1 pre-existing unrelated error (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`).
- `tests/unit/test_backend.py` with that error deselected: 161 passed (was 153 before step 4, +8 new).
- `tests/unit/test_report_generator.py`: 31/31 passed (contained in the combined run).
- `tests/unit/test_inference.py`: 17 passed.
- All runs with `$env:PYTHONPATH="src"` under `.venv\Scripts\python.exe`.
- Deliverable 6 NOT marked complete — steps 5 (inspection-delete FK cascade + R2 PDF cleanup) and 7 (frontend wiring) outstanding.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 8, Task 6: PDF report generation — steps 1–3 (Deliverable 6, partial)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `requirements.txt` — Added `reportlab>=4.2.0,<5.0.0` (backend section) and `pypdf>=4.0.0` (test-only section), transitive pin `charset-normalizer==3.5.2` (step 1).
- `src/crack_detection/backend/report_generator.py` — NEW standalone pure generator module (no FastAPI/DB/R2 imports): dataclasses + `generate_inspection_report_pdf` A4 branded PDF builder (step 1); later extended with optional `page_count_sink` for page-count persistence (step 2 extension).
- `tests/unit/test_report_generator.py` — NEW, 31 unit tests across 5 classes (step 1).
- `src/crack_detection/backend/routers/reports.py` — `generate_report` endpoint implemented: registered-user-only, opaque 404s, data assembly incl. internal R2 keys, R2 download of originals/overlays, in-memory PDF generation, R2 upload `reports/{report_id}.pdf`, `INSERT INTO reports` incl. `page_count`, failure compensation (best-effort PDF delete on upload/persistence failure with logging, original error preserved). Download endpoint stub left untouched (step 3).
- `tests/unit/test_backend.py` — 13 new tests in `TestReportGeneration` + helpers (`_reports_app`, `_report_storage`, `_r2_storage_dep`, row factories, `_pdf_text`/`_pdf_page_count` via pypdf) (step 3).
- `agent_context/ACTIVE_TASK.md`, `CURRENT_STATE.md`, `HANDOFF.md` — updated (Deliverable 6 status: PARTIAL steps 1–3).

**What was implemented:**
- Approved decisions applied: ReportLab; registered users only; Draft+Completed allowed; full-UUID report IDs; checkpoint epoch verbatim; navy/teal token branding.
- Generator degrades gracefully for missing overlays/measurements/observations/images and zero-photo inspections; no physical units; no fabricated values; XML escaping on user text.
- Endpoint access control verified to execute zero SQL for 401/403 paths; nonexistent and foreign inspections both opaque 404; internal R2 keys never returned to clients; page count persisted matches actual PDF page count (verified against pypdf in tests).

**Verification (actual):**
- `TestReportGeneration`: 13/13 passed.
- `tests/unit/test_report_generator.py`: 31/31 passed (no regressions after the `page_count_sink` extension).
- `tests/unit/test_backend.py` full: 153 passed, 1 pre-existing unrelated error deselected (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`).
- `tests/unit/test_inference.py`: 17 passed.
- All runs with `$env:PYTHONPATH="src"` under `.venv\Scripts\python.exe` (CPython 3.12.5).
- Deliverable 6 NOT marked complete — steps 4 (download endpoint), 5 (FK cascade + R2 cleanup), 7 (frontend) outstanding.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-07 — Milestone 8, Task 1: Connect frontend inspection creation to backend (Deliverable 1)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `frontend/src/pages/NewInspectionPage.tsx` — Wired form submit to `apiClient.createInspection()`; added Clerk bearer token attachment via `getToken()`; success navigation to `/app/inspections/${created.id}` via `useNavigate`; loading state and duplicate-submission prevention; error handling via existing `prototype-alert` pattern; all existing UI elements preserved
- `frontend/src/pages/NewInspectionPage.test.tsx` — New test file with 10 tests (form rendering, required-field validation, correct API payload, bearer token attachment, success navigation, backend validation errors, network errors, duplicate submission prevention, values preserved after failure, loading state)

**What was connected:**
- `NewInspectionPage.tsx` form → `apiClient.createInspection()` (existing backend `POST /inspections` endpoint)
- Clerk bearer token → `apiClient.setToken()` via `useAuth().getToken()`
- Successful creation → navigation to inspection detail page using returned `id`

**Verification (actual):**
- TypeScript: `tsc --noEmit` — clean
- Lint: `oxlint` — clean (only pre-existing warnings)
- Build: `vite build` — successful
- Tests: `vitest run` — 32/32 passed (4 test files), including 10 new `NewInspectionPage` tests; no regressions
- Tests mock `apiClient` and `useAuth`; no real backend/Clerk integration (external services not configured locally)

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-07 — Milestone 8, Task 2: Declare python-multipart and standardise ownership responses (Deliverable 2)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `requirements.txt` — Added `python-multipart>=0.0.9,<0.0.11` in the "Backend dependencies (Milestone 2)" section. Compatible with FastAPI 0.104–0.115. Declared for production deployments; not installed locally (documented environment issue).
- `src/crack_detection/backend/dependencies.py` — Modified `require_ownership`: guest rejection stays 403; foreign-resource case changed from 403 to 404 with detail "Resource not found". Single shared-boundary change affects all callers (`upload_photograph`, `complete_inspection`, `update_inspection`, `delete_inspection`, `update_photograph`, `remove_photograph`, `reanalyse_photograph`, `analyse_photograph`).
- `tests/unit/test_backend.py` — Updated `test_foreign_inspection_ownership_rejected` to expect 404 (was 403). Added `TestForeignOwnershipStandardisation` (2 tests: `update_inspection` foreign → 404, `delete_inspection` foreign → 404 via real router/TestClient). Added `test_update_photograph_foreign_ownership_rejected` in `TestRegisteredUserPhotographUpload`: `update_photograph` foreign → 404.

**What was changed:**
- `python-multipart` declared as an explicit backend dependency for production multipart form parsing.
- `require_ownership` now returns opaque 404 for foreign resources (guest rejection stays 403), so foreign and nonexistent resources are indistinguishable — no existence disclosure. Matches the existing download/reopen/listing convention.

**Verification (actual):**
- Backend `tests/unit/test_backend.py`: 120 passed (117 prior + 3 new), 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`, documented, unrelated). No regressions.
- `tests/unit/test_inference.py`: 17 passed (unchanged).
- python-multipart not installed locally (per AGENTS.md preservation rules); declaration in `requirements.txt` for production.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-07 — Milestone 8 Complete Implementation Audit (audit/planning task; no application features implemented)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `ROADMAP.md` — Milestone 8 section revised from unordered bullet list to an ordered, numbered implementation sequence (Tasks 1–6) preserving the original objective, all eight deliverables and acceptance criteria, existing completed work (Deliverable 3 complete), explicit dependencies, and per-task status.
- `agent_context/ACTIVE_TASK.md`, `CURRENT_STATE.md`, `HANDOFF.md` — updated to reflect audit findings and revised sequence.
- No application source code modified; no files staged/committed/pushed.

**Audit findings (deliverable statuses):**
- Deliverable 3 (persist beyond 24h): COMPLETE (verified — no expiry on registered tables; guest cleanup isolated; 4 controlled-time tests).
- Deliverable 1 (inspection creation): PARTIAL — backend `POST /inspections` done + tested; frontend `NewInspectionPage` not connected to `apiClient.createInspection`.
- Deliverable 2 (photographs): PARTIAL — backend upload/list/download done + tested; frontend connected; `python-multipart` NOT in `requirements.txt`; foreign-ownership status inconsistent (403 vs 404 opaque).
- Deliverable 4 (dashboard/history): PARTIAL — backend `list_inspections` done; frontend `DashboardPage`/`HistoryPage` use mock data.
- Deliverable 5 (monthly allowance): NOT IMPLEMENTED — guest 3-limit only.
- Deliverable 6 (PDF reports): NOT IMPLEMENTED — no endpoint, no PDF library.
- Deliverable 7 (history list/card): PARTIAL — views exist, mock-backed.
- Deliverable 8 (filtering): PARTIAL — title search works; `structure_type` param ignored; date/verification absent.

**Recommended first implementation task:** Connect frontend inspection creation to backend (`NewInspectionPage.tsx` → `apiClient.createInspection` → navigate to detail page). Every remaining Milestone 8 deliverable depends on inspections existing.

**No tests were added or run during this audit.** Prior test results remain: backend suite 117 passed (1 pre-existing unrelated `python-multipart` error), inference 17 passed, frontend 22 passed.

---

## 2026-11-06 — Milestone 8, Task 1.4: Analysis persistence and versioning corrections

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `src/crack_detection/backend/routers/photographs.py`:
  - `analyse_photograph` persists actual calculated `pixel_measurements` (`psycopg2.extras.Json`) into `prediction_versions.pixel_measurements` and updates `photographs.pixel_measurements`; unavailable measurements stored as NULL (never `NULL` when valid measurements exist).
  - After success, `photographs` updated with `prediction_mask_key`, `prediction_overlay_key`, `model_version`, `prediction_timestamp`, `pixel_measurements`.
  - `version_number` assigned under a row lock: `SELECT id FROM photographs ... FOR UPDATE` then `COALESCE(MAX(version_number), 0) + 1`. First version = 1, subsequent increment; failed analyses consume nothing; concurrent attempts cannot collide.
  - `reanalyse_photograph` now runs a full analysis (inference + R2 upload + persist + photograph update) and creates the next version (previously archived the old prediction and returned version 1).
  - Registered-user idempotency: explicit `Idempotency-Key` header honoured when provided; deterministic key (`uuid.uuid5(NAMESPACE_DNS, "cracksight:analyse:{user_id}:{photo_id}")`) used as fallback so retries without a header are recognised. `/reanalyse` uses a fresh `uuid4()` key. Globally unique `idempotency_key` constraint retained. Guest idempotency (deterministic session+photo key) and the three-analysis allowance unchanged.
  - **Guest allowance correction:** `increment_guest_analysis_count` reserves the allowance before work; if `_persist_analysis` fails (inference, R2 upload, or DB persistence), `decrement_guest_analysis_count` compensates so a failed attempt never permanently consumes allowance. The atomic conditional UPDATE guarantees at most three successful reservations per session. Idempotent retries consume no additional allowance.
  - `probability_map_key` in `prediction_versions` made nullable via idempotent `ALTER TABLE ... DROP NOT NULL` (pipeline does not store probability maps standalone).
  - Fixed latent runtime defects: missing `numpy`/`uuid`/`StorageError`/`require_ownership` imports, `NAMESPACE_DNS` constant, `uuid.uuid5`/`np`/`datetime` NameErrors, missing `original_image_key` in `AnalysisResponse`, guest double-increment, guest `session` NameError during idempotency key generation.
- `src/crack_detection/backend/database.py`: added idempotent `ALTER TABLE prediction_versions ALTER COLUMN probability_map_key DROP NOT NULL`; added `decrement_guest_analysis_count()` for allowance compensation.
- `tests/unit/test_backend.py`: added `TestAnalysisPersistence` (23 tests) covering measurement persistence, photograph updates, version numbering, idempotency, guest allowance failure/success, and failure handling/R2 cleanup.

**Corrective review findings:**
- Confirmed defect: guest allowance was consumed (`increment_guest_analysis_count`) before inference/R2/DB work, so a failed attempt permanently consumed allowance. Fixed by reserving first and compensating with `decrement_guest_analysis_count` on any failure.
- Confirmed defect: frontend sends no `Idempotency-Key` header, and registered users fell back to fresh `uuid4()`, so retries created duplicate versions. Fixed by using a deterministic key (`user_id` + `photo_id`) as fallback so retries are deduped without a header.

**Tests (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -k "TestAnalysisPersistence" -q` → 23 passed.
- Full backend suite `tests/unit/test_backend.py` → 88 passed, 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`; not installed per scope). No regressions to Tasks 1.1/1.2/1.3.
- `tests/unit/test_inference.py` → 17 passed (model/inference unchanged).
- `tests/unit/test_database_integration.py` — not attempted (documented hang).

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing Task 1.1/1.2/1.3 changes preserved.

---

## 2026-11-06 — Milestone 8, Task 1.5: Registered-User Image Downloads

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `src/crack_detection/backend/routers/photographs.py`:
  - Added `GET /photos/{photo_id}/download/{image_type}` (`download_photograph_image`) plus helper `_download_registered_image`. Supported types: `original`, `mask`, `overlay`.
  - `require_authenticated_user` dependency: unauthenticated → 401; guest → 403; registered user proceeds (identity from verified Clerk state via `get_current_user` → `ensure_registered_user`).
  - Single ownership-scoped query `SELECT p.original_image_key, p.prediction_mask_key, p.prediction_overlay_key FROM photographs p JOIN inspections i ON p.inspection_id = i.id WHERE p.id = %s AND i.user_id = %s` → nonexistent and foreign photographs both return 404 (no existence disclosure). Authentication and ownership complete before any private R2 access.
  - Unsupported image type → 400 before any DB/storage access. `original` uses `original_image_key` (always available for an uploaded photograph); `mask`/`overlay` use `prediction_mask_key`/`prediction_overlay_key`; a NULL key → 404 "not available" (a photograph without a successful prediction still serves its original image).
  - Existing `R2Storage.download_file` (no presigned URLs; follows existing authenticated backend download pattern). `StorageError` (including missing R2 object) → 500. Returns image bytes via FastAPI `Response` with `Content-Disposition` attachment header, matching the existing guest download-response convention (`routers/guest.py:_download_guest_result`).
  - No changes to model, inference pipeline, schemas, authentication, guest allowance, or database. No new storage provider or abstraction.

**Tests:** new `TestRegisteredUserImageDownload` (12 tests) covering successful original-image download, successful mask download, successful overlay download, unauthenticated request (401), guest request (403), photograph belonging to another user (404 opaque), nonexistent photograph (404), unsupported image type (400), missing mask (404), missing overlay (404), R2 object missing (500), R2 storage failure (500).

**Test results (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\python.exe -m pytest tests/unit/test_backend.py -k "TestRegisteredUserImageDownload" -q` → 12 passed.
- Combined run (download + analysis persistence + photo listing + reopen) → 57 passed.
- Full backend suite `tests/unit/test_backend.py` → 100 passed, 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`; not installed per scope; unrelated to this task). No regressions to Tasks 1.1–1.4 (previous full suite was 88 passed + same 1 pre-existing error).
- `tests/unit/test_inference.py` → 17 passed (unchanged).
- `tests/unit/test_database_integration.py` — not attempted (documented hang).
- Storage is mocked in tests; this is NOT a live R2 integration test.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing Task 1.1–1.4 changes preserved.

**Scope respected:** no multipart uploads, no inference/model changes, no guest-allowance changes, no dashboard/history, no PDF reports, no historical prediction-version downloads.

---


## 2026-11-06 — Milestone 8, Task 1.3: Photograph listing endpoint

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `GET /inspections/{inspection_id}/photos` in `src/crack_detection/backend/routers/inspections.py` (`list_inspection_photographs()`).
- Single parameterised LEFT JOIN query (inspections LEFT JOIN photographs) establishes ownership and retrieves photographs in one round trip, scoped by inspection id + authenticated Clerk user id; ordered `p.created_at ASC, p.id ASC`.
- Zero rows → 404 (nonexistent/foreign indistinguishable); one NULL-photograph-id LEFT JOIN row → existing-but-empty (200, empty list, total 0).
- `require_authenticated_user`: guests → 403, unauthenticated → 401. Identity only from verified Clerk state.
- New schemas in `schemas.py`: `PhotographMetadataResponse` (id, inspection_id, structure_type, observation, verification_status, model_version, prediction_timestamp, pixel_measurements, created_at, prediction_available derived from `prediction_mask_key IS NOT NULL`) and `PhotographListResponse` (inspection_id, photographs, total). Internal R2 keys/bucket details excluded by design; NULL prediction fields returned as null (nothing fabricated).
- Test mocks `_SeqCursor`/`_SeqConn` extended with `fetchall`; `_reopen_app` docstring generalised (name kept, 1.2 call sites untouched).

**Tests:** new `TestInspectionPhotos` — 13 tests (owner retrieval, multiple photographs, empty list, oldest-first ordering + SQL assertion, single-round-trip ownership scoping, prediction metadata, NULL handling, storage-key secrecy via exact key-set + body-text assertions, foreign 404, nonexistent 404, guest 403, unauthenticated 401, DB failure → structured 500 no commit).

**Test results (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -k "TestInspectionPhotos" -q` → 13 passed.
- Full suite `tests/unit/test_backend.py` → 65 passed, 2 warnings, 1 error (`TestGuestSessionRouter::test_create_guest_session`: pre-existing missing `python-multipart`; unchanged; NOT installed). No Task 1.1/1.2 regressions.
- `tests/unit/test_database_integration.py` — not attempted (documented hang).

**Previous completion records (M6, 7/7.1, Task 1.1, Task 1.2) remain recorded below.**

## 2026-11-06 — Milestone 8, Task 1.2: Explicit inspection reopen endpoint

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `POST /inspections/{inspection_id}/reopen` in `src/crack_detection/backend/routers/inspections.py` (`reopen_inspection()`), following existing router conventions.
- Atomic conditional transition: single parameterised CTE statement `UPDATE ... SET status='draft', completed_at=NULL WHERE id AND user_id AND status='completed' RETURNING *` plus real photograph count — no check/update race window.
- Zero-row handling: ownership-scoped follow-up `SELECT status` → 404 (nonexistent or foreign; no existence disclosure), 400 (already draft), 409 (theoretical concurrent-status fallback). No third lifecycle state introduced.
- `require_authenticated_user` (guests → 403); identity from verified Clerk state only.
- Photographs, prediction versions, observations, verification statuses, reports untouched (no DELETE/INSERT; asserted in tests).

**Tests (tests/unit/test_backend.py):** new `TestInspectionReopen` (9 tests: owner reopen success, conditional SQL/status/completed_at/owner-scoping, data-preservation, already-draft 400, nonexistent 404, foreign-user 404 opaque, unauthenticated 401, guest 403, DB failure → structured 500 with no commit). Mock conn helpers `_SeqCursor`/`_SeqConn`/`_reopen_app`/`_reopened_row`; `_SimulateVerifiedClerkMiddleware` made configurable (`user_id=`); `_reopen_app` stubs identity sync AND hard-guards that no unit test opens a real DB connection.

**Test results (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -k "TestInspectionReopen" -q` → 9 passed.
- Full suite `tests/unit/test_backend.py` → 52 passed, 2 warnings, 1 error (`TestGuestSessionRouter::test_create_guest_session`: pre-existing missing `python-multipart` — import of `main`/routers package fails at `routers/guest.py:239`; unchanged from Task 1.1 report; NOT installed per task scope).
- `tests/unit/test_database_integration.py` — not attempted (documented hang).

**Status of preceding work preserved:** Task 1.1 changes (identity-sync fail-closed) remain present as unstaged modifications to database.py/dependencies.py/schemas.py/test_backend.py.

## 2026-11-03 — Milestone 6: Frontend Foundation

- Fixed and completed the interrupted Milestone 6 implementation (broken TypeScript, failing tests, incorrect Clerk SDK usage).
- Integrated Clerk React SDK via `AppProviders`; typed API client with Clerk bearer token, guest session token, 30s timeout, structured `ApiError`.
- Routing with `react-router-dom`: public, guest, and registered-user protected routes with auth guards and loading states; layouts (PublicLayout, GuestLayout, AppShell); all prototype pages rewired.
- Verified: `npm run build`, `npm run lint`, `npm run test` (18 tests) all pass in `frontend/`. Backend API contracts verified against backend schemas.
- Commit: `d851c3c` (Milestone 6 foundation); later guest-analysis commits `0faa07b`, `a834c33` (Milestone 7/7.1, recorded in CURRENT_STATE.md).

## 2026-11-06 — Task 1.1 (corrective review): Fail-closed registered-user identity synchronisation

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**What was found:**
- Confirmed the suspected failure path existed: `get_current_user()` (`src/crack_detection/backend/dependencies.py`) called `ensure_registered_user()` but ignored the boolean result, returning an authenticated identity even when synchronisation returned `False`. For a valid Clerk JWT with no `email` claim and no pre-existing local user record, inspection creation later failed on the `fk_inspections_user` foreign key (500 instead of a structured error).
- Database `DatabaseError` from synchronisation propagated unhandled (500) instead of a structured HTTP error.
- Missing Clerk `sub` was already fail-closed in middleware JWT verification (`middleware._verify_clerk_jwt` returns `None`), so it could not reach `get_current_user()` in normal flow; a dependency-level guard was added as defence-in-depth.

**What was changed:**
- `database.ensure_registered_user()` (database.py:287): when no email claim is present, confirms an existing local record with a read-only `SELECT 1 FROM users WHERE id = %s` and succeeds only if it exists (no email invented, nothing written); fails closed otherwise. The email-present path keeps the idempotent `INSERT ... ON CONFLICT (id) DO NOTHING`.
- `dependencies.get_current_user()` (dependencies.py:39): enforces synchronisation result — `False` raises `UnauthorizedError` (401 structured body), `DatabaseError` raises `ServiceUnavailableError` (503, retryable). Identity is returned only after successful sync/confirmation.

**Tests added/adjusted (tests/unit/test_backend.py):**
- Database level: missing-email read-only no-write; missing-email existing record confirmed (`True`); missing-email no record fails closed; plus prior insert/idempotency/sub/db-failure tests.
- Dependency level: successful sync returns identity (incl. confirmed existing user); guest not synchronised; unauthenticated 401; sync failure raises `UnauthorizedError` 401; `DatabaseError` surfaces as `ServiceUnavailableError` 503.
- End-to-end (real inspections router, mocked DB/app-level deps): inspection creation blocked with 401 and zero SQL executed when sync fails; succeeds with 201 when sync returns `True`. Router module is loaded directly from file via `_load_inspections_router()` to avoid the unrelated missing `python-multipart` dependency in `routers/__init__` import chain.

**Test results (actual):**
- Command: `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -k "EnsureRegisteredUser or GetCurrentUserSync or InspectionCreation" -q` → 15 passed.
- Full backend suite `tests/unit/test_backend.py` → 43 passed, 1 error (`TestGuestSessionRouter` — pre-existing missing `python-multipart` at `routers/guest.py:239` import; NOT fixed here per task scope).
- `tests/unit/test_database_integration.py` hung past 240s — matches the previously documented shared-session DB connection issue; not attempted further.

**Environment notes (not acted on):**
- `python-multipart` absent from `.venv`; blocks importing `crack_detection.backend.main`/`routers` package.
- Running pytest with `-v` inside this shell pipeline hangs (output/streaming artifact); `-q` works reliably.
- Tests require `$env:PYTHONPATH="src"` (src-layout, package not installed editable).

---

## 2026-11-07 — Milestone 8: Add photographs to an inspection (structure type per photo)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `src/crack_detection/backend/routers/photographs.py`:
  - Added `POST /photos/{inspection_id}/upload` (`upload_photograph`) plus helpers `_store_uploaded_photograph` and `_validate_uploaded_image`.
  - `require_authenticated_user`: unauthenticated → 401; guest → 403; registered user proceeds.
  - Inspection existence (404), ownership (403 opaque), draft eligibility (400 for completed — photographs are not added to completed inspections).
  - Structure type validated against `wall`/`beam`/`column`; file validated by extension, size (`max_upload_size_bytes` from settings), and PIL image content (not just filename/MIME).
  - Original image stored in private R2 at `inspections/{inspection_id}/originals/{photo_id}.{ext}`; photograph record persisted in PostgreSQL (user, inspection, structure type, `verification_status='not_verified'`), returned as `PhotographResponse`.
  - Failure handling: R2 upload failure → no photograph record; DB persistence failure after successful R2 upload → newly uploaded R2 object deleted (best-effort); prior photographs/prediction versions untouched.
  - Multipart body parsed via `await request.form()` (call-time) so the module stays importable where `python-multipart` is unavailable; production installs `python-multipart`.
- `frontend/src/types/index.ts`: added `PhotographMetadataResponse`, `PhotographListResponse`.
- `frontend/src/services/api.ts`: added `listInspectionPhotographs`, `uploadPhotograph` (multipart FormData + bearer token), `downloadPhotographImage` (blob URL).
- `frontend/src/pages/InspectionDetailPage.tsx`: connected to backend — photo list, upload form with preview/structure select/upload state/errors, refreshes list on success, completed inspections read-only, sign-in prompt.

**Tests:** new `TestRegisteredUserPhotographUpload` (13 backend tests) and 4 frontend API-client tests.

**Test results (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -q` → 113 passed, 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`, documented, unrelated). `TestRegisteredUserPhotographUpload` → 13 passed.
- `tests/unit/test_inference.py` → 17 passed (unchanged; no regressions).
- Frontend: `tsc -b` clean, `vite build` clean, `oxlint` clean (only pre-existing-pattern warnings), `vitest run` → 22 passed (18 original + 4 new).
- Storage is mocked in tests; no real R2 integration claimed; no tests against production Neon.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-07 — Milestone 8: Verify Registered Inspection Results Persist Beyond 24 Hours

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Finding:** The roadmap deliverable "Save inspection results (persist beyond 24 hours)" is ALREADY SATISFIED by the existing implementation. No code changes were necessary.

**Verification basis (code inspection + controlled-time tests):**
- Database: `users`, `inspections`, `photographs`, `prediction_versions` have NO `expires_at` column and NO time-based deletion rule; only `guest_sessions` carries `expires_at` + `is_active` (24-hour expiry applies exclusively to guests).
- Object storage: registered keys use `inspections/{inspection_id}/...`; guest keys use `guest/{session_token}/...` — distinguishable, isolated prefixes.
- Cleanup: `database.cleanup_expired_guest_sessions()` (database.py:309) only deactivates `guest_sessions` rows (`... expires_at <= NOW()`); never touches registered tables or R2 objects.
- Retrieval: `get_inspection`, `list_inspection_photographs`, `get_photograph`, `download_photograph_image` are ownership-scoped with NO time filter.

**Tests added:** `TestRegisteredUserPersistenceBeyond24Hours` (4 tests) in
`tests/unit/test_backend.py`:
1. `test_registered_tables_have_no_expiry_column` — registered tables lack expires_at; only guest_sessions has it.
2. `test_cleanup_expired_guest_sessions_only_touches_guest_sessions` — cleanup SQL targets only guest_sessions.
3. `test_registered_user_retrieves_photographs_after_simulated_24_hours` — ownership-scoped photo listing succeeds with creation timestamp >24h old.
4. `test_registered_user_downloads_photograph_after_simulated_24_hours` — original image downloadable from R2 after >24h; key uses inspections/ prefix.

**Test results (actual):**
- `$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/unit/test_backend.py -q` → 117 passed (113 prior + 4 new), 1 pre-existing error (`TestGuestSessionRouter` — missing `python-multipart`, documented, unrelated). `TestRegisteredUserPersistenceBeyond24Hours` → 4 passed.
- `tests/unit/test_inference.py` → 17 passed (unchanged; no regressions).
- Storage and DB are mocked in tests; no real R2 or production Neon used. Persistence verified via schema inspection, cleanup SQL scoping, and controlled-time retrieval (timestamp >24h old), not a real 24-hour wait.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

**Roadmap status:** This specific deliverable ("Save inspection results persist beyond 24 hours") is COMPLETE (verified). Next incomplete Milestone 8 deliverable: inspection creation/edit/complete/delete connected to real backend data (part of Milestone 8 registered-user inspection management), followed by Milestone 9 (dashboard/history) and Milestone 10 (PDF reports).

---

## 2026-11-08 — Milestone 8, Task 5: Implement monthly allowance + fair-use protection (Deliverable 5)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `src/crack_detection/backend/config.py` — added `registered_monthly_analyses_limit` setting (default 100, env `REGISTERED_MONTHLY_ANALYSES_LIMIT`).
- `src/crack_detection/backend/database.py` — added `user_usage` table `(user_id, month_key, analyses_count, updated_at)` with composite PK; added `increment_user_analysis_count`, `decrement_user_analysis_count`, `get_user_monthly_usage`, `_current_month_key`.
- `src/crack_detection/backend/routers/photographs.py` — `analyse_photograph` now checks/increments registered-user monthly allowance before persistence; raises HTTP 429 when limit exceeded; compensates (decrements) on failure.

**Tests:**
- Added 5 registered-user allowance tests in `TestAnalysisPersistence` (inference failure, R2 failure, DB persistence failure, success, monthly limit enforced). All **5 passed**.

**Verification (actual):**
- New registered-allowance tests: **5/5 passed**.
- Task 4 filtering tests: **15/15 passed** (still verified).
- Frontend: **57/57 passed**; `tsc --noEmit` clean; `npm run lint` clean.

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-08 — Milestone 8, Task 4: Implement backend date/structure-type/verification-status filters (Deliverable 8)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Implemented:**
- `src/crack_detection/backend/routers/inspections.py` — `list_inspections` now accepts:
  - `status` (alias `status_filter`): validated against `VALID_STATUSES` → `ValidationError` (400) if invalid.
  - `structure_type`: validated against `VALID_STRUCTURE_TYPES` (`wall`/`beam`/`column`) → 400 if invalid; filtered via `EXISTS (SELECT 1 FROM photographs p WHERE p.inspection_id = i.id AND p.structure_type = %s)`.
  - `verification_status`: validated against `VALID_VERIFICATION_STATUSES` → 400 if invalid; filtered via `EXISTS ... p.verification_status = %s`.
  - `date_from` / `date_to`: date params; `created_at >= date_from` (UTC midnight) and `created_at < date_to + 1 day` (exclusive upper bound → inclusive end date); absent params = no date filter.
- `InspectionListResponse.total` now returns filtered row count (separate count query) rather than page size; pagination (LIMIT/OFFSET) applied on page query; verified 5 rows + `limit=2` → `total=5`.

**Frontend wiring:**
- `frontend/src/services/api.ts` — `listInspections` accepts `search`, `status`, `structure_type`, `verification_status`, `date_from`, `date_to`, `limit`, `offset`; passes via URLSearchParams (undefined omitted).
- `frontend/src/pages/HistoryPage.tsx` — added verification-status filter select (snake_case values); `fetchInspections` passes all filter params; `filtered` memo retains only client-side query + status; Clear filters resets all.

**Tests:**
- `tests/unit/test_backend.py` — new `TestInspectionListFiltering` (15 tests: unfiltered, search, status valid/invalid, structure_type valid/invalid, verification_status valid/invalid, date_from, date_to, combined AND filters, total-vs-page-size, owner isolation, guest, pagination).
- `frontend/src/services/api.test.ts` — filter param pass-through test.
- `frontend/src/pages/HistoryPage.test.tsx` — structure-type, verification-status, date, clear-filters interaction tests; fixed status select value casing to snake_case; added `waitFor` guards for loading-state-driven re-renders.

**Verification (actual):**
- Frontend `vitest run`: **57/57 passed** (6 files: Dashboard 8, History 16, NewInspection 10, api 13, App 4, state 6).
- Frontend `tsc --noEmit`: clean.
- Frontend `npm run lint`: clean (pre-existing warnings only; none in changed files).
- Backend `TestInspectionListFiltering`: **15/15 passed** (genuine execution with `PYTHONPATH=src`; previously skipped due to missing `PYTHONPATH` on src-layout package). No production code defects — test infrastructure fixed only (`_SeqConn` count-row separation, `_sample_inspection_row` UUID derivation).
- Backend full suite `tests/unit/test_backend.py`: **135 passed, 1 pre-existing error** (unrelated `TestGuestSessionRouter::test_create_guest_session` module-level `app` reference in `main.py:82`).

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

---

## 2026-11-07 — Milestone 8 Task 3: Connect dashboard + history to real backend data (Deliverables 4 & 7)

**Branch/HEAD at completion:** `main` @ `a834c33` (working-directory changes only, not staged/committed)

**Files changed:**
- `frontend/src/pages/DashboardPage.tsx` — Replaced mock `initialInspections` import/data with real `apiClient.listInspections()`; mapped via shared `toInspectionView()` from `../types`; loading/error/empty states preserved; guest sign-in prompt preserved; retry via `ErrorState.onRetry`; metrics derived from real data.
- `frontend/src/pages/DashboardPage.test.tsx` — Fixed missing async `waitFor` on rendered content; added `fireEvent` import; replaced `any` type with typed `{ inspections: Inspection[]; total: number }`; added retry test (error → Try again → success re-fetch, asserts 2 `listInspections` calls). Total: 8 tests.
- `frontend/src/pages/HistoryPage.test.tsx` — Added retry test (error → Try again → success re-fetch, asserts 2 `listInspections` calls). Total: 12 tests.

**What was connected:**
- `DashboardPage.tsx` → `apiClient.listInspections()` (existing backend `GET /inspections` endpoint) with bearer token via `getToken()`
- `HistoryPage.tsx` → `apiClient.listInspections()` (same endpoint), preserving list/card views, search, status/component/date filters
- Both pages use `toInspectionView()` mapping from `Inspection` → `InspectionView`

**Verification (actual):**
- Frontend `vitest run`: 52/52 passed across 6 test files (8 Dashboard + 12 History + 10 NewInspection + 12 api + 4 App + 6 state)
- Frontend `tsc --noEmit`: clean
- Frontend `npm run lint`: clean (pre-existing warnings only)
- Frontend `npm run build`: successful
- Tests mock `apiClient` and `useAuth`; no real backend/Clerk integration (external services not configured locally)

**Deliverable statuses after this task:**
- Deliverable 4 (dashboard/history): COMPLETE — frontend connected to `apiClient.listInspections()`, both real data + tests
- Deliverable 7 (history list/card): COMPLETE — views exist with real data + test coverage

**Model integrity:** model architecture, weights, preprocessing, and inference algorithms not changed.

**Git:** nothing staged or committed; all pre-existing changes preserved.

