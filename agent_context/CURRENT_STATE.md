# CURRENT STATE — Implementation Snapshot

**Last updated:** 2026-11-08

## Implemented and Verified

### Backend — Milestone 12 sub-deliverable 3: Backend deployment configuration (2026-11-09)
- New `.python-version`: `3.12.5` (Render Python runtime pin; matches local CPython 3.12.5).
- New `render.yaml`: minimal backend-only Web Service blueprint.
  - `type: web`, `env: python`, `rootDir: .`
  - `buildCommand: pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt && python scripts/download_checkpoint.py`
    - Step 1 installs CPU-only PyTorch 2.6.0+cpu explicitly from the official PyTorch CPU index (`2.6.0+cpu` exists only there — never on PyPI — so pip cannot resolve a CUDA or other PyPI distribution; no `--extra-index-url` resolver ambiguity for other packages).
    - Step 2 installs remaining requirements from PyPI (torch already satisfied; torchvision etc. from PyPI = CPU-only).
    - Step 3 runs the existing `scripts/download_checkpoint.py` (sub-deliverable 2) to fetch the checkpoint from private R2 via `MODEL_CHECKPOINT_URL`; build fails if the checkpoint cannot be downloaded or verified; downloader logs scheme+host only (never the URL/query/credentials).
  - `startCommand: uvicorn crack_detection.backend.main:app --host 0.0.0.0 --port $PORT` (`PYTHONPATH=src` declared as an env var so `crack_detection.backend.main:app` imports — verified import path).
  - `healthCheckPath: /live` (`/live` and `/ready` routes present in `routers/health.py`).
  - Secret env vars declared with `sync: false` (MODEL_CHECKPOINT_URL, MODEL_CHECKPOINT_SHA256, SECRET_KEY, DATABASE_URL, Clerk vars, R2 vars, ALLOWED_ORIGINS); values supplied via the Render dashboard, never in the file.
  - Non-secret vars: PYTHONPATH=src, DEBUG=false, INFERENCE_CHECKPOINT_PATH=<verified path>.
- CPU-only PyTorch: local torch verified as `2.6.0+cpu`, CUDA unavailable; strategy keeps that exact build.
- No requirements.txt changes (torch left as `torch>=2.3.0,<2.7.0`; exact CPU build pinned in the build command). No model, checkpoint, preprocessing, or inference changes.
- Verification: render.yaml parses as valid YAML; `/live` route present; import path `crack_detection.backend.main:app` valid with PYTHONPATH=src; downloader tests 19/19; inference tests unchanged. Live deployment NOT performed (deployment-time).
- Dependencies unavailable locally (fastapi/uvicorn not installed per AGENTS.md); backend tests skipped — not a regression.

### Backend — Milestone 12 sub-deliverable 4: Neon PostgreSQL configuration (2026-11-09)
- `config.py`: Added `database_url` field validator `_validate_database_url_sslmode` that fails fast if `DATABASE_URL` does not include `sslmode=require` (Neon requires TLS; psycopg2 would otherwise fall back to plaintext).
- `database.py`: No changes needed — `psycopg2.connect(settings.database_url)` works with both Neon direct and pooled connection strings.
- Neon endpoint strategy: **pooled endpoint recommended**. The app opens short-lived per-operation connections and closes them immediately (`get_db_connection`), uses no prepared statements/LISTEN/NOTIFY/advisory locks/temp tables — the textbook use case for Neon's pooled endpoint (PgBouncer transaction mode). Direct endpoint also works if a specific feature requires it.
- `render.yaml`: `DATABASE_URL` declared as `sync: false` secret (already present); comments added documenting pooled vs direct and sslmode=require.
- `.env.example`: `DATABASE_URL` already includes `sslmode=require`; comments added with pooled vs direct guidance.
- Tests: 3 new tests in `TestSettings` — missing DATABASE_URL raises validation error, DATABASE_URL without sslmode=require raises validation error, DATABASE_URL with sslmode=require is accepted.
- Live Neon connectivity NOT verified (deployment-time; free-tier limitations per AGENTS.md).

### Backend — Milestone 12 sub-deliverable 5: Object Storage configuration (2026-11-09)
- `storage.py`: `R2Storage` renamed to `ObjectStorage`; wraps boto3 S3-compatible client for object storage (Cloudflare R2 or Backblaze B2); all settings already wired via `get_settings()`.
- `config.py`: Added `object_storage_endpoint` field validator `_validate_object_storage_endpoint` (must be HTTPS URL) and `object_storage_bucket_name` field validator `_validate_object_storage_bucket_name` (must be non-empty) — fail fast on malformed object storage settings.
- `render.yaml`: Object storage env vars (`OBJECT_STORAGE_ACCOUNT_ID`, `OBJECT_STORAGE_ACCESS_KEY_ID`, `OBJECT_STORAGE_SECRET_ACCESS_KEY`, `OBJECT_STORAGE_BUCKET_NAME`, `OBJECT_STORAGE_ENDPOINT`) declared as `sync: false` secrets; comments added documenting bucket creation, API token setup, and endpoint format.
- `.env.example`: Object Storage section updated with setup instructions (create private bucket, create API token with Object Read & Write, endpoint format); placeholders only, no real credentials.
- No `requirements.txt` changes — `boto3>=1.28.0,<1.35.0` already declared.
- Tests: 3 new tests in `TestSettings` — `OBJECT_STORAGE_ENDPOINT` without `https://` raises error, `OBJECT_STORAGE_ENDPOINT` with `https://` accepted, empty `OBJECT_STORAGE_BUCKET_NAME` raises error.
- Live object storage connectivity NOT verified (deployment-time; free-tier limitations per AGENTS.md).
- Bucket remains private; objects accessed server-side only; backend enforces ownership checks on all read/write operations.

### Backend — Milestone 12 sub-deliverable 6: Backend smoke testing (2026-11-09)
- New `scripts/smoke_test_backend.py`: standalone, stdlib-only (urllib) smoke-test script for a deployed Render Web Service. Takes `--base-url` or `SMOKE_TEST_BASE_URL` env var. Performs non-mutating GET checks on `/live` (expects HTTP 200 + `status: "alive"`) and `/ready` (expects HTTP 200; logs checks dict, does not fail on `not_ready` since deps may not be provisioned). Validates status codes and response structure; logs scheme+host only (never secrets/query params); reasonable timeouts; exits 0 on pass, 1 on failure, 2 on missing URL.
- Tests: 6 new tests in `TestHealthEndpoints` in `tests/unit/test_backend.py` — `/live` returns 200 + `status: "alive"`, `/live` response structure, `/ready` returns 200, `/ready` configured when env vars set, `/ready` not_configured when unset/CHANGE_ME, both endpoints require no auth.
- Live deployment smoke testing NOT performed (deployment-time; free-tier limitations per AGENTS.md).
- No model, checkpoint, preprocessing, inference, CORS, Neon, or R2 changes.

### Backend — Milestone 12 sub-deliverable 7: Frontend deployment on Render (2026-11-09)
- Frontend is a standalone React + TypeScript + Vite app under `frontend/`, already compatible with Render Static Site hosting:
  - Build command: `npm ci && npm run build` (already in `package.json`)
  - Publish directory: `dist` (Vite default, gitignored)
  - Root directory: `frontend`
  - Environment variables: `VITE_API_URL`, `VITE_CLERK_PUBLISHABLE_KEY` (placeholders in `.env.example`, no real secrets)
  - SPA rewrite `/*` → `/index.html` documented for Render dashboard (required for `BrowserRouter` client-side routes)
- Local verification (actual):
  - `npm run build`: built successfully in 2.67s, `dist/` produced with `index.html` + assets
  - `npm run test` (vitest): 71 passed (8 test files)
  - `npx tsc --noEmit`: clean
  - `npm run lint` (oxlint): clean (warnings only, no errors)
- Live deployment NOT performed (deployment-time; free-tier limitations per AGENTS.md)
- No changes to frontend source code needed — already deployment-ready
- Backend `ALLOWED_ORIGINS` must be set to the deployed frontend origin in Render dashboard (sub-deliverable 1 already implemented the config)

### Backend — Milestone 12 sub-deliverable 8: Clerk configuration (2026-11-09)
- config.py: Added clerk_jwt_issuer field validator _validate_clerk_jwt_issuer that fails fast if CLERK_JWT_ISSUER is not a valid HTTPS URL; clerk_jwks_url derived from issuer when not explicitly set (_derive_jwks_url).
- Clerk JWT verification middleware (middleware.py): verifies RS256 signature against Clerk JWKS with kid lookup, validates issuer and expiration (aud intentionally not verified), caches JWKS keys with 1-hour TTL; fails closed on any verification error.
- clerk_publishable_key, clerk_secret_key, clerk_jwt_issuer, clerk_jwks_url all declared as required fields in config.py (except jwks_url which is optional); all declared as sync: false secrets in render.yaml; values supplied via Render dashboard, never in the file.
- clerk_secret_key remains backend-only; frontend only uses VITE_CLERK_PUBLISHABLE_KEY (safe to expose in browser bundle).
- Email claim required for user identity synchronisation (ensure_registered_user in database.py): fail closed when missing email claim or no existing local record.
- Tests: 2 new tests in TestSettings — CLERK_JWT_ISSUER without https:// raises error, CLERK_JWT_ISSUER with https:// accepted.
- Live Clerk authentication NOT verified (deployment-time; free-tier limitations per AGENTS.md).
- No changes to authentication behavior, database schema, or frontend Clerk SDK integration.


- Deployment-readiness audit (2026-11-08, chat report) identified two Render blockers and both are fixed:
  1. `allow_origins=["*"] if settings.debug else []` (empty list in production) — replaced by `ALLOWED_ORIGINS` env (`config.py: allowed_origins`): comma-separated, trimmed, de-duplicated, trailing slashes removed, wildcard entries stripped; `Settings.cors_allowed_origins` property: explicit list wins, `DEBUG=true` with no config permits the Vite dev-server origins (`http://localhost:5173`, `http://127.0.0.1:5173`), `DEBUG=false` with no config = fail-closed (no cross-origin, never a wildcard).
  2. `ClerkAuthMiddleware` was outermost (added after CORSMiddleware) and rejected browser OPTIONS preflights (and emitted 401s without CORS headers). Empirically verified pin: Starlette 0.46.2 executes the most-recently added middleware first; fix registers ClerkAuthMiddleware FIRST, CORSMiddleware LAST so CORS is outermost. OPTIONS preflights never reach Clerk auth; non-OPTIONS requests still pass through Clerk authentication unchanged; 401 responses for allowed origins now carry `Access-Control-Allow-Origin` (so browsers can read authentication errors). With `allow_methods=*`/`allow_headers=*`, `acc-control-allow-headers` mirrors requested headers; disallowed origins get 400 + `Vary: Origin` with no ACAO.
  3. `main.py` no longer instantiates `settings` at module import; `create_app()` calls `get_settings()` itself (env-driven CORS/debug/title must reflect the active environment at app build, not an import snapshot — discovered empirically via a stale-settings probe and initially masked by pytest runs that imported the module under prior tests' env).
- Tests: 13-test `TestCorsAndPreflight` in `tests/unit/test_backend.py` (real middleware stack via `create_app()` + TestClient under per-test env: allowed-origin preflight 200 + ACAO; methods/headers/credentials advertised; unconfigured origin 400 + `Vary` + no ACAO; protected GET without JWT still 401 AND with ACAO for allowed origin; production-only-configured-origins; production-unset blocks all cross-origin while no-Origin requests work; public guest preflight; debug defaults; debug + explicit config; parsing/suffix/dedupe/wildcard-strip; wildcard-only collapses to empty). Env/cache isolation enforced in `_build_app` (env set BEFORE importing `main`, since `routers/auth.py:24` instantiates Settings at module import; `get_settings.cache_clear()` before/after).
- Verified: focused class 13 passed; full `tests/unit/test_backend.py` **213 passed, 0 errors** (was 200). Not verified: live production CORS against a deployed Render service (deployment-time).
- Docs: `.env.example` (new `ALLOWED_ORIGINS` section with format + example), `ROADMAP.md` Milestone 12 deployment sub-deliverables list (deliverable 1 marked COMPLETE with this evidence).

### Backend — Milestone 11: database integration-suite repair (2026-11-08)
- `tests/unit/test_database_integration.py` no longer hangs. Root cause: the session-scoped `db_conn` never ended transactions (idle-in-transaction) while `init_schema()` requested DDL locks — decisively when the guarded `fk_reports_inspection` cascade swap needed locks held by the shared connection's uncommitted transaction. The FK is now CASCADE in `xportra_test` (migrated by an earlier run), and a causality probe (open uncommitted txn + `init_schema()` completing instantly) confirmed which statement historically blocked.
- Fixture: session-scoped `db_conn` retained, wrapped by a new autouse per-test rollback fixture (`rollback_db_transaction` — rollback before and after every test: no lingering/aborted transactions, no DDL wait, no test-row persistence). Guest-session helper rows get targeted per-test cleanup (`_delete_test_guest_session`); CRUD ids uuid-suffixed for rerun idempotency.
- Repaired: `test_foreign_key_constraint` now proves a genuine `psycopg2.errors.ForeignKeyViolation` (23503) with a real user and nonexistent inspection (the old test swallowed its own `NameError` and proved nothing); `test_validate_guest_session_expiration` moved into `TestGuestSession` (was module-level); never-collected nested `test_increment_analysis_count` promoted to a real test method.
- Real PostgreSQL (`xportra_test`) throughout — no mocks. Collected **9** (was 8); full file **9 passed** ×3 consecutive runs (16.67s / 11.24s / 9.26s); previously affected tests **5/5 passed** individually; post-run counts: users/inspections/photographs 0, guest_sessions unchanged at 6 stale expired rows; backend suite still **200 passed**.
- Known stale hygiene note (pre-existing, fixed here): earlier "backend integration tests hang" lines in this file were superseded by this section.

### Backend — Milestone 11: /auth endpoint tests (2026-11-08)
- New `TestAuthEndpoints` (12 tests) in `tests/unit/test_backend.py` exercises the **real** `/auth` endpoints through `TestClient(main.app)`; only JWKS retrieval (`middleware._fetch_jwks`), `database.get_db_connection`, and `dependencies.ensure_registered_user` are mocked (asserted never called).
- Actual behaviours verified: `POST /auth/verify` returns HTTP 200 `{"valid": false, ...}` (fail-closed identity shape, not 401) for missing/malformed/non-Bearer credentials and for any JWT verification failure (RS256+JWKS+issuer+expiry verified for real with a generated RSA keypair); the endpoint performs **no user synchronisation / DB access**. `GET /auth/sign-in-url` derives `https://<issuer>/sign-in` and falls back to `https://clerk.accounts.com/sign-in` for placeholder (`CHANGE_ME`) or empty issuers. `GET /auth/callback` is a documented **placeholder** (no OAuth processing, no redirect); query params ignored.
- `get_settings` (`lru_cache`) lifecycle managed per test (`_use_fresh_settings` helper) so env-dependent cases are deterministic and don't leak into other tests.
- `tests/unit/test_backend.py`: **200 passed, 0 errors, 0 deselected** (was 188 after the guest-session task).
- Real Clerk authentication remains unvalidated (credentials unconfigured) — mocked-boundary tests only.

### Backend — Milestone 11: guest-session tests made genuine (2026-11-08)
- All 5 vacuous `TestGuestSession` tests in `tests/unit/test_backend.py` (patch-the-helper-then-assert-the-mock) replaced by 11 genuine data-layer tests (only the DB boundary mocked; the real guest-session implementation executed): creation (INSERT text/params incl. real 43-char token + 24h expiry + fallback default), validation (valid/unknown/expired-deactivation/naive-tz, SELECT predication verified, read path never commits), increment (atomic guard predicates verified verbatim, within-limit and at-limit), and connection scaffold (DatabaseError wrapping, rollback+close on statement failure, commit+close on success with the real `get_db_connection`).
- `TestGuestSessionRouter` extended with 5 endpoint tests (`GET /guest/session/validate` valid/missing-header/invalid-token; `POST /guest/session/consume-analysis` success/at-limit/401-no-token) — DB layer mocked at the `routers.guest` namespace only.
- `tests/unit/test_backend.py`: **188 passed, 0 errors, 0 deselected** (was 177).
- Known production-code observation (flagged, not fixed): `routers/guest.py` (`upload_guest_photograph`, ~line 245) annotates `request: Request` without importing `Request` — harmless today (annotations not evaluated eagerly; import/uvicorn verified) but unstable.
- NOT complete (Milestone 11): `/auth` router endpoint tests, `tests/unit/test_database_integration.py` hang fix, real-service integration (credentials still unconfigured).

### Backend — Milestone 11: application entry point fix (2026-11-08)
- `src/crack_detection/backend/main.py` now exposes a module-level `app = create_app()`; the startup handler (`_startup_event`) is registered inside `create_app()` via `app.add_event_handler` and the root `GET /` route moved inside the factory. No module-level code dereferences `app` before creation.
- `from crack_detection.backend.main import app` works; real `uvicorn crack_detection.backend.main:app` serves (verified: startup complete, `GET /` 200).
- `tests/unit/test_backend.py`: **177 passed at the time of the fix** (superseded by the 188 above after the guest-session task); the fix resolved the former setup error in `TestGuestSessionRouter` — caused by the missing binding, not by `python-multipart`, which is installed as 0.0.10 in `.venv`.
- New `TestApplicationFactory` (3 tests) covers factory wiring, module-level app import/detached instance, and root-endpoint serving.

### Model and data pipeline
- U-Net with ResNet-34 encoder and training/evaluation code remain unchanged.
- Baseline checkpoint and evaluation report are in `model_artifacts/` (checkpoint stays excluded from Git).
- `src/crack_detection/inference.py` provides the reusable `CrackSegmentationPipeline`; preprocessing and output behavior match the existing model contract.
- Dataset manifests, annotation handling, validation, and deduplication are implemented in `src/crack_detection/data/` and `scripts/`.
- Existing inference and data-pipeline tests were previously verified; see the task history for recorded results.

### Backend — Milestones 2–5
- FastAPI package: `src/crack_detection/backend/`.
- Clerk JWT verification, guest session lifecycle, and ownership checks are implemented.
- Inspection and photograph routes follow the Draft/Completed lifecycle and support prediction versioning.
- PostgreSQL schema and Cloudflare R2 wrappers are implemented.
- The backend analysis endpoint invokes the existing inference pipeline; the model is not run in the browser.
- Prior context records backend, inference, and integration tests as verified; external service credentials are not configured here.

### Backend — Milestone 8, Task 4: Inspection list filtering (2026-11-08)
- `GET /inspections` (`list_inspections` in `src/crack_detection/backend/routers/inspections.py`) now supports:
  - `status` (alias `status_filter`): validated against `VALID_STATUSES`.
  - `structure_type`: validated against `VALID_STRUCTURE_TYPES` (`wall`/`beam`/`column`).
  - `verification_status`: validated against `VALID_VERIFICATION_STATUSES`.
  - `date_from` / `date_to`: date-only params; `created_at >= date_from` and `created_at < date_to + 1 day` (UTC midnight to exclusive next-day → inclusive end date); absent params = no date filter.
- Structure type + verification status filtering use `EXISTS (SELECT 1 FROM photographs p WHERE p.inspection_id = i.id AND ...)` subqueries.
- Invalid enum values → `ValidationError` (HTTP 400).
- `total` in `InspectionListResponse` now returns the filtered row count (separate count query) rather than the page size; LIMIT/OFFSET pagination on page query is correct (verified: 5 filtered rows + `limit=2` → `total=5`).

### Backend verification (genuine execution, 2026-11-08)
- Backend `TestInspectionListFiltering`: **15/15 passed** (previously skipped because `crack_detection` module was unimportable without `PYTHONPATH=src`; test-infrastructure defects identified and fixed only: `_SeqConn`/`_SeqCursor` count-row separation + `_sample_inspection_row` UUID derivation; no production code was changed).
- Backend full suite: **140 passed, 1 pre-existing error** (since **fixed 2026-11-08** — see the entry-point fix section below; `main.py` lacked a module-level `app` binding).
- Backend `TestAnalysisPersistence` (Task 5 registered-user monthly allowance): **5/5 new tests passed**.
- No production code defects in `list_inspections` or `analyse_photograph`; all filtering and allowance tests confirm correct behaviour.

### Backend — Milestone 8, Task 5: Registered-user monthly analysis allowance (2026-11-08)
- `config.py`: Added `registered_monthly_analyses_limit` setting (default 100, env `REGISTERED_MONTHLY_ANALYSES_LIMIT`).
- `database.py`: Added `user_usage` table `(user_id, month_key YYYY-MM, analyses_count, updated_at)` with composite PK `(user_id, month_key)` and FK to `users`. Added `increment_user_analysis_count`, `decrement_user_analysis_count`, `get_user_monthly_usage`, `_current_month_key` helpers.
- `routers/photographs.py`: `analyse_photograph` now checks/increments registered-user monthly allowance before persistence (mirrors guest allowance pattern). Raises HTTP 429 when limit exceeded; compensates (decrements) on failure so failed attempts never consume allowance.
- Tests: 5 new registered-user allowance tests added to `TestAnalysisPersistence` — all **5/5 passed**.
- Test infrastructure: `_photos_app` now accepts `mock_allowance=False` parameter so tests can set their own allowance mocks. `test_registered_allowance_consumed_once_on_success` completed with full success-path assertions.

### Frontend — Milestone 8, Task 4: filtering wiring (2026-11-08)
- `frontend/src/services/api.ts`: `listInspections` accepts `search`, `status`, `structure_type`, `verification_status`, `date_from`, `date_to`, `limit`, `offset`; passes via URLSearchParams (undefined params omitted).
- `frontend/src/pages/HistoryPage.tsx`: added verification-status filter select (snake_case values); `fetchInspections` passes all filter params to `apiClient.listInspections()`; `filtered` memo retains only client-side query + status logic; Clear filters resets all.
- Tests: `TestInspectionListFiltering` (15 backend tests, verified passed with genuine execution), `api.test.ts` filter-param test, `HistoryPage.test.tsx` filter interaction tests (structure-type, verification-status, date, clear filters).

### Backend — Task 1.1 fail-closed identity synchronisation (2026-11-06)
- `get_current_user()` now enforces the result of `ensure_registered_user()`: a registered Clerk identity is only returned after the local `users` record exists or was inserted successfully; otherwise requests fail closed with a structured 401 (`UnauthorizedError`), and database `DatabaseError` surfaces as 503 (`ServiceUnavailableError`, retryable).
- `ensure_registered_user()` confirms an existing record read-only when no email claim is present; it never invents an email or writes when the claim is missing. Missing Clerk `sub` also fails closed (middleware already rejects JWTs without `sub`).
- Inspection creation is proven blocked (401, zero SQL) when synchronisation fails, via end-to-end tests using the real inspections router with mocked DB.
- Known environment issues status: `python-multipart` is installed in `.venv` (0.0.10) and imports fine — older notes here blaming its absence were stale and are corrected above (2026-11-08); the integration-suite hang was fixed 2026-11-08 (section above); tests need `$env:PYTHONPATH="src"`.

### Frontend UX prototype — implemented and verified
- Standalone React + TypeScript + Vite app is under `frontend/`.
- Responsive design system and component patterns are documented in `docs/ui_ux_design.md`.
- Routes cover landing, sign-in/up placeholders, guest upload/results, dashboard, history, inspection create/details, report preview, access-denied, and not-found screens.
- Sample input/output assets are in `frontend/public/demo/`; the prediction images are static sample outputs.
- Prototype interactions are local-only: selected images are previewed in the browser, inspection state and guest allowance are held in React memory, and no backend/API/auth/inference operation is called (report actions on InspectionDetailPage call apiClient methods against the verified backend contracts).
- Build and lint passed during the 2026-11-02 prototype task. Browser smoke checks covered the main routes, guest 3-analysis limit, sample result tabs, inspection create/complete/reopen, and a 390 px mobile viewport.
- Local review URL: `http://localhost:5173/` (start with `cd frontend; npm run dev`).

## Current Milestone

**Milestone 7.1: Guest analysis reliability and idempotency — implemented and verified.**

The guest analysis workflow is functionally complete and connected to real backend functionality:

- Guest session creation with 24-hour expiration.
- Photo upload with server-side validation (file type, size, content integrity via PIL).
- Structure type selection (wall/beam/column).
- Real U-Net ResNet-34 inference via the backend FastAPI pipeline.
- Results display with pixel measurements (crack pixel count, percentage, bounding box, region count).
- Individual result-file downloads (original, mask, overlay) with ownership verification.
- Three-analysis guest allowance with atomic enforcement and compensation for concurrent requests.
- Idempotency key mechanism to prevent duplicate analysis results and allowance consumption on retries.
- Guest ownership checks: guests can only access their own photographs.
- Expired guest sessions are rejected; 24-hour session expiry is enforced.
- Frontend build, lint, and 18 tests all pass.

### Changes from Milestone 6

- Orphaned R2 object cleanup on storage failures (best-effort cleanup with logging).
- Analysis retry idempotency via deterministic idempotency keys and database uniqueness constraint.
- Guest 24-hour expiration and R2 cleanup behaviour documented.
- Middleware `PUBLIC_PATHS` design explained via code comment.
- All changes are working directory modifications against Milestone 6 commit `d851c3c`.

### Frontend UX prototype — preserved
- The approved visual prototype (commit `916f64f`) design tokens, colour palette, typography, and layouts are preserved.
- Mock data remains isolated in `src/data/mockData.ts` for features not yet connected to the backend; `InspectionDetailPage` photograph upload/list is connected to the real backend (Milestone 8 upload deliverable).

### Backend — Milestone 8, Task 1.2 reopen endpoint (2026-11-06)
- `POST /inspections/{inspection_id}/reopen` implemented in `src/crack_detection/backend/routers/inspections.py`: owner-only explicit completed → draft transition, `completed_at` cleared, atomic conditional UPDATE scoped by inspection id + authenticated user id + status 'completed' (CTE also returns real photograph count).
- Zero-row update → ownership-scoped status lookup: 404 for nonexistent or foreign inspections (no existence disclosure), 400 for already-draft, 409 theoretical race fallback. Guests rejected via `require_authenticated_user` (403).
- No deletion/modification of photographs, prediction versions, observations, verification statuses, or reports; completion endpoint untouched; only Draft/Completed statuses exist.
- 9 focused reopen tests pass (`TestInspectionReopen`, mocked DB with a real-connection guard).

### Backend — Milestone 8, Task 1.4 analysis persistence and versioning (2026-11-06)
- `analyse_photograph` persists actual calculated `pixel_measurements` (via `psycopg2.extras.Json`) into both `prediction_versions.pixel_measurements` and `photographs.pixel_measurements`; unavailable measurements stored as NULL.
- After a successful analysis, the `photographs` record is updated with `prediction_mask_key`, `prediction_overlay_key`, `model_version`, `prediction_timestamp`, and `pixel_measurements`.
- `version_number` is assigned under a row lock (`SELECT ... FOR UPDATE` on the photograph) as `COALESCE(MAX(version_number), 0) + 1`, so the first version is 1, subsequent versions increment, and concurrent attempts cannot collide. Failed analyses do not consume a version.
- The `reanalyse_photograph` endpoint now runs a full analysis (inference + R2 upload + persist + photograph update) and creates the next version, instead of archiving the old prediction.
- Registered-user idempotency: an explicit `Idempotency-Key` header is honoured when provided; otherwise a deterministic key (`uuid.uuid5(NAMESPACE_DNS, "cracksight:analyse:{user_id}:{photo_id}")`) is used so retries are recognised without a header. Reanalysis uses a fresh `uuid4()` via `/reanalyse`.
- Guest allowance: `increment_guest_analysis_count` reserves the allowance before work; if `_persist_analysis` fails (inference, R2 upload, or DB persistence), `decrement_guest_analysis_count` compensates so a failed attempt never permanently consumes allowance. The atomic conditional UPDATE guarantees at most three successful reservations per session. Idempotent retries do not consume additional allowance.
- `probability_map_key` in `prediction_versions` made nullable via idempotent `ALTER TABLE ... DROP NOT NULL` (pipeline does not store probability maps standalone).
- Fixed latent runtime defects: missing `numpy`/`uuid`/`StorageError`/`require_ownership` imports, `NAMESPACE_DNS` constant, `uuid.uuid5`/`np`/`datetime` NameErrors, missing `original_image_key` in `AnalysisResponse`, guest double-increment, guest `session` NameError during idempotency key generation.

23 focused tests added (`TestAnalysisPersistence`) covering measurement persistence, photograph updates, version numbering, idempotency, guest allowance failure/success, and failure handling/R2 cleanup.

### Backend — Milestone 8, Task 1.3 photograph listing (2026-11-06)

### Backend — Milestone 8, Task 1.5 registered-user image downloads (2026-11-06)
- `GET /photos/{photo_id}/download/{image_type}` (`download_photograph_image`) + helper `_download_registered_image` in `src/crack_detection/backend/routers/photographs.py`. Supported types: `original`, `mask`, `overlay`.
- `require_authenticated_user`: unauthenticated → 401; guest → 403; registered user proceeds (identity from verified Clerk state via `get_current_user` → `ensure_registered_user`).
- Single ownership-scoped query `... JOIN inspections i ... WHERE p.id = %s AND i.user_id = %s` → nonexistent and foreign photographs both return 404 (no existence disclosure). Auth + ownership enforced before any R2 access.
- Unsupported image type → 400 before any DB/storage access. `original` → `original_image_key` (always available); `mask`/`overlay` → `prediction_mask_key`/`prediction_overlay_key`; NULL key → 404 "not available" (photo without a successful prediction still serves its original).
- Existing `R2Storage.download_file` (no presigned URLs; follows existing authenticated backend download pattern). `StorageError` (incl. missing R2 object) → 500. Returns image bytes via FastAPI `Response` with `Content-Disposition` attachment header, matching the existing guest download-response convention.
- No changes to model, inference pipeline, schemas, authentication, guest allowance, or database. No new storage provider/abstraction.
- 12 focused tests added (`TestRegisteredUserImageDownload`) covering successful original/mask/overlay download, unauthenticated (401), guest (403), foreign photograph (404), nonexistent photograph (404), unsupported type (400), missing mask/overlay (404), R2 object missing (500), R2 storage failure (500).

### Backend — Milestone 8, Task 6: PDF report generation — steps 1–3 (2026-11-08)
- **Step 1** (verified): `reportlab>=4.2.0,<5.0.0` declared in `requirements.txt` (reportlab 4.5.1 installed, pypdf 7.0.0 test-only); standalone `src/crack_detection/backend/report_generator.py` (pure module — no FastAPI/DB/R2 imports) with dataclasses `PhotographReportEntry`/`InspectionReportData`/`ReportMetadata` and `generate_inspection_report_pdf(...) -> bytes`: A4 branded layout (navy `#18313b`/teal `#167f78` matching frontend tokens), branded header band + `Page X of Y` footer on every page via two-pass `_BrandedPageCanvas`, report metadata/inspection info tables, photograph summary, per-photograph blocks (original+overlay images, "AI-assisted prediction" with `Model version (checkpoint epoch): <epoch>` + image-space pixel measurements, separately-labelled "Inspector observation"), limitations/safety disclaimer box; graceful degradation for missing overlays/measurements/observations/images and zero-photograph inspections; no physical units; no fabrication. 31/31 unit tests (`tests/unit/test_report_generator.py`).
- **Step 2 (extension)**: generator gained optional `page_count_sink: Optional[List[int]]` — the two-pass canvas total page count is appended after build so the endpoint can persist `reports.page_count` without parsing the PDF (pypdf stays test-only). Backwards compatible; 31/31 tests re-verified.
- **Step 3 (verified)**: `generate_report` endpoint implemented in `src/crack_detection/backend/routers/reports.py`:
  - `require_authenticated_user` (guests → 403, no identity → 401); inspection lookup → 404 "Inspection not found" (nonexistent) / 404 "Resource not found" via `require_ownership` (foreign) — both opaque; Draft AND Completed inspections allowed.
  - Photographs fetched with internal R2 keys; originals + available overlays downloaded from R2; missing overlay key → None → PDF placeholder; asset `StorageError` → 500 "Failed to retrieve photograph assets".
  - PDF built in memory → uploaded to R2 at `reports/{report_id}.pdf` (`application/pdf`) → `INSERT INTO reports (id, inspection_id, user_id, report_pdf_key, page_count) RETURNING id, generated_at` + commit; response `ReportGenerateResponse(report_id=row["id"], generated_at=row["generated_at"], download_url f"/reports/{row['id']}/download")` — internal R2 keys never exposed.
  - Failure compensation: upload failure → best-effort PDF delete, no row; DB persistence failure → best-effort PDF delete (cleanup failures logged, never raised), 500 with original error preserved; generation failure → no side effects. `GET /reports/{report_id}/download` stub left untouched (step 4 outstanding).
  - 13 new endpoint tests (`TestReportGeneration` in `tests/unit/test_backend.py`) using `_reports_app` helper, `_report_storage` recording fake, `_SeqConn`.
- **Step 4 (verified 2026-11-08)**: `download_report` endpoint implemented — `require_authenticated_user` (guest 403 / anonymous 401); single query `SELECT r.report_pdf_key, i.user_id FROM reports r JOIN inspections i ON r.inspection_id = i.id WHERE r.id = %s`; nonexistent → 404 "Report not found", foreign → 404 "Resource not found" via `require_ownership` (opaque, storage never contacted); PDF streamed from R2 with `StorageError` → 500 "Failed to retrieve report" (established `_download_registered_image` convention, incl. missing objects); response is the actual bytes via FastAPI `Response` with `Content-Type: application/pdf` and `Content-Disposition: attachment; filename="cracksight-report-{report_id}.pdf"`; internal R2 keys never exposed. 8 new tests (`TestReportDownload`).
- **Step 5 (verified 2026-11-08)**: FK cascade + deletion cleanup — `database.py` reports FK now `ON DELETE CASCADE` (fresh DBs) plus an idempotent guarded DO-block constraint-swap statement for existing deployments (fires only when `fk_reports_inspection` lacks the cascade rule; mocked-only coverage via `init_schema` against a fake recording connection). `delete_inspection` in `routers/inspections.py` now retrieves all `report_pdf_key` values before deleting, deletes each report PDF from R2 (`delete_file` is idempotent; failures logged and aborted with 500 **before** the DB DELETE so rows remain for retry), keeps the existing photograph-prefix cleanup and `DELETE FROM inspections` + commit (report rows removed by the cascade in the same transaction). Storage-before-DB ordering is documented: PostgreSQL and R2 don't share a transaction; a later DB failure leaves rows pointing at deleted PDFs (recoverable/retryable, logged) instead of unrecoverable post-commit R2 orphans. 12 new tests (`TestReportsForeignKeyCascadeMigration`, `TestInspectionDeletionWithReports`, + download-after-inspection-deleted).
- **Step 6 (frontend wiring, verified 2026-11-08)**: `frontend/src/services/api.ts` gained `downloadReportPdf(reportId)` mirroring `downloadPhotographImage` (bearer token, R2-streamed PDF bytes → `URL.createObjectURL` blob). `frontend/src/pages/InspectionDetailPage.tsx` gained an authenticated-users-only report card: generate + download actions, duplicate-click prevention, inline errors, anchor download named `cracksight-report-{report_id}.pdf`, blob URL revoked after click; Draft AND Completed inspections both allowed; unauthenticated/guest users see no report actions. `frontend/src/pages/ReportsPage.tsx` kept as clearly-labelled sample content — its "Generate report" CTA navigates to `/app/history`; no report-list endpoint was fabricated (none exists on the backend). New tests: `frontend/src/pages/InspectionDetailPage.test.tsx` (7 tests), `frontend/src/pages/ReportsPage.test.tsx` (3 tests), plus `generateReport`/`downloadReportPdf` cases in `frontend/src/services/api.test.ts`. Frontend: **vitest 71 passed (8 files)**, `tsc --noEmit` clean, `oxlint` clean, `vite build` OK. All frontend report tests mock the API client — no real R2/PostgreSQL integration claimed; that remains deployment-time.

### Backend — Milestone 8: add photographs to an inspection (2026-11-07)
- `POST /photos/{inspection_id}/upload` (`upload_photograph`) + helper `_store_uploaded_photograph` and `_validate_uploaded_image` in `src/crack_detection/backend/routers/photographs.py`.
- `require_authenticated_user`: unauthenticated → 401; guest → 403; registered user proceeds.
- Inspection existence (404), ownership (403 opaque), draft eligibility (400 for completed — photographs are not added to completed inspections).
- Structure type validated against `wall`/`beam`/`column` (400 otherwise).
- File validation: extension (jpg/jpeg/png/webp), size (`max_upload_size_bytes` from settings), and image content via PIL `verify()`/`convert("RGB")` — content validated, not just filename/MIME type.
- Original image stored in private R2 at `inspections/{inspection_id}/originals/{photo_id}.{ext}`.
- Photograph record persisted in PostgreSQL (user, inspection, structure type, `verification_status='not_verified'`), returned as `PhotographResponse`.
- Failure handling: R2 upload failure → no photograph record; DB persistence failure after successful R2 upload → newly uploaded R2 object deleted (best-effort); prior photographs/prediction versions untouched.
- Multipart body parsed via `await request.form()` (call-time) so the module stays importable where `python-multipart` is unavailable; production installs `python-multipart`.
- 13 focused tests added (`TestRegisteredUserPhotographUpload`) covering successful upload, structure-type persistence, owned inspection, foreign inspection (403), nonexistent inspection (404), completed inspection (400), unsupported structure type, invalid image content, unsupported format, file-size limit, R2 upload failure, DB persistence failure + R2 cleanup, unauthenticated (401), guest (403).
- Multipart parsing via `request.form()` rather than `File()`/`Form()` route parameters so the module stays importable where `python-multipart` is not installed (production installs it).

### Backend — Milestone 8: registered-user persistence beyond 24 hours (verified 2026-11-07)
- Requirement "Save inspection results (persist beyond 24 hours)" is ALREADY SATISFIED; no code changes necessary.
- `users`, `inspections`, `photographs`, `prediction_versions` tables have NO `expires_at` column and NO time-based deletion rule; registered records persist until explicitly owner-deleted.
- `guest_sessions` is the ONLY table with `expires_at` + `is_active`; 24-hour expiry applies exclusively to guests.
- R2 keys: registered = `inspections/{inspection_id}/...`; guest = `guest/{session_token}/...` — distinguishable, isolated prefixes.
- `cleanup_expired_guest_sessions()` (database.py:309) only deactivates `guest_sessions` rows; never touches registered tables or R2 objects.
- Retrieval endpoints (`get_inspection`, `list_inspection_photographs`, `get_photograph`, `download_photograph_image`) are ownership-scoped with NO time filter.
- 4 focused tests added (`TestRegisteredUserPersistenceBeyond24Hours`): no-expiry schema, cleanup isolation (guest_sessions only), photo listing after simulated >24h age, original-image download after simulated >24h age.

## Milestone 8 Audit Status (audited 2026-11-07)

| # | Deliverable | Status | Key gap |
|---|-------------|--------|---------|
| 1 | Registered-user inspection creation with title | COMPLETE | Backend `POST /inspections` implemented + tested; frontend `NewInspectionPage` connected to `apiClient.createInspection` — registered user can submit, create an inspection, and navigate to its detail page |
| 2 | Add photographs to inspection (structure type per photo) | COMPLETE | Backend upload/list/download implemented + tested; frontend connected; `python-multipart` declared in `requirements.txt`; foreign-ownership status standardised to opaque 404 across upload/complete/update/delete/download/reopen endpoints via `require_ownership` shared helper |
| 3 | Save inspection results (persist beyond 24 hours) | COMPLETE | Verified — no expiry on registered tables; `guest_sessions` is the only expiry table; `cleanup_expired_guest_sessions()` never touches registered data or R2 |
| 4 | Inspection dashboard and history | COMPLETE | Backend `GET /inspections` implemented; frontend `DashboardPage`/`HistoryPage` connected to `apiClient.listInspections()` with real authenticated data + tests |
| 5 | Monthly analysis allowance with fair-use protection | COMPLETE | `registered_monthly_analyses_limit` (default 100), `user_usage` table + increment/decrement helpers, `analyse_photograph` 429 enforcement with decrement compensation; 5/5 allowance tests passed |
| 6 | Generate and download PDF inspection reports | COMPLETE | ReportLab installed; generator + 31 unit tests; `POST /reports/generate/{inspection_id}` + 13 tests; `GET /reports/{report_id}/download` + 9 tests; FK cascade migration + R2 PDF cleanup on inspection deletion + 12 tests. Frontend wiring complete: `downloadReportPdf` in `api.ts`, InspectionDetailPage report card (authenticated-only, Draft+Completed, duplicate prevention, `cracksight-report-{report_id}.pdf` download), ReportsPage kept as clearly-labelled sample content with its CTA navigating to `/app/history` (no report-list endpoint fabricated); 14 new frontend tests, all passing. |
| 7 | View inspection history (list and card views) | COMPLETE | Views connected to real backend data; list/card views, search, status/component/date filters preserved + tested |
| 8 | Filtering (title/date/structure type/verification status) | COMPLETE | Backend `list_inspections` supports `status`, `structure_type`, `verification_status`, `date_from`, `date_to` with enum validation; EXISTS subqueries for structure type / verification status; correct total count; frontend filter UI wired to backend params |

## Not Yet Implemented

- Deployment (Milestone 12).

- Production frontend API integration and persistent inspection data.
- Clerk React SDK sign-in/up and Google OAuth flows.
- Real guest-session creation/validation and backend-enforced allowance/expiry in the browser.
- Production upload/batch/camera flow connected to FastAPI.
- Production PDF report generation/download.
- Deployment and real external-service configuration.

## Known Open Issues

- Inference checkpoint must be supplied to a deployment environment; it must not be committed.
- Inference hosting remains unresolved and requires CPU benchmarking before selection.
- Backend upload file-size/dimension limits still need a configured source of truth; the prototype's 10 MB cap is only a local UX example. Note: `MAX_IMAGE_DIMENSION` (`config.py`) is currently **declared but never enforced by any code** (flagged by the 2026-11-08 deployment-readiness audit — separate deployment sub-deliverable).
- External Neon, R2, and Clerk integrations are not configured for production validation.
- External CORS origins must be configured at deployment (`ALLOWED_ORIGINS`); unset in production = cross-origin refused by design (fail closed).

## Project Constraints

- Preserve model architecture, training code, datasets, and checkpoints.
- Keep inference behind FastAPI; never load the checkpoint in browser code.
- The app is an inspection aid, not a structural safety assessment.
- Measurements are pixel-space only; no physical calibration or engineering conclusions.
- Preserve the two inspection statuses: Draft and Completed.
