# ACTIVE TASK — Current Work Item

**Task title:** Milestone 12 (deployment sub-deliverable 8): Clerk configuration
**Status:** Complete — implemented and verified 2026-11-09 (record below). Next: deployment sub-deliverable 9 (End-to-end live testing). External credential setup (Neon/R2/Clerk) remains deployment-time work.
**Audited:** 2026-11-08 (deployment-readiness audit) · **Implemented + verified:** 2026-11-09

## Milestone 12 — CORS + preflight handling (2026-11-08, verified)
**Sub-deliverable 1 = backend CORS/preflight.** COMPLETE (verified 2026-11-08; see history below).

## Milestone 12 — Model checkpoint availability on Render (2026-11-09, verified)
**Sub-deliverable 2 = build-time fetch from R2 via pre-signed URL; checkpoint itself never committed.** COMPLETE (verified 2026-11-09; see history below).

## Milestone 12 — Backend deployment configuration (2026-11-09, verified)
**Sub-deliverable 3 = Render Web Service configuration.** COMPLETE (verified 2026-11-09; see history below).

## Milestone 12 — Neon PostgreSQL configuration (2026-11-09, verified)
**Sub-deliverable 4 = Neon configuration (DATABASE_URL with sslmode=require; test branch for live testing).** COMPLETE.

## Milestone 12 — Cloudflare R2 configuration (2026-11-09, verified)
**Sub-deliverable 5 = R2 configuration (private bucket + Object Read & Write token).** COMPLETE.

## Milestone 12 — Backend smoke testing (2026-11-09, verified)
**Sub-deliverable 6 = Backend smoke testing.** COMPLETE (verified 2026-11-09; see history below).

## Milestone 12 — Frontend deployment on Render (2026-11-09, verified)
**Sub-deliverable 7 = Frontend deployment on Render Static Site.** COMPLETE.

**Root causes (established before changing):**
1. No Render Static Site configuration existed for the frontend.
2. The frontend uses `BrowserRouter` (client-side routing), requiring an SPA rewrite rule on Render for direct page refreshes.
3. Environment variables `VITE_API_URL` and `VITE_CLERK_PUBLISHABLE_KEY` needed to be identified and documented.
4. Backend `ALLOWED_ORIGINS` needs the deployed frontend URL for CORS to work in production.

**Changes:**
- `scripts/smoke_test_backend.py` (already existed from sub-deliverable 6) — reused for backend health verification.
- No frontend source code changes needed — the Vite + React app is already deployment-ready:
  - Build command `npm ci && npm run build` already in `package.json`
  - Publish directory `dist` is Vite default and gitignored
  - Environment variables `VITE_API_URL` and `VITE_CLERK_PUBLISHABLE_KEY` already in `.env.example` with placeholders
  - `vite.config.ts` already configured correctly (no `base` needed for root deployment)
- Documentation updates:
  - `ROADMAP.md`: sub-deliverable 7 marked COMPLETE with exact Render Static Site settings
  - `agent_context/CURRENT_STATE.md`: sub-deliverable 7 section added with local verification results
  - `agent_context/ACTIVE_TASK.md`: updated to mark sub-deliverable 7 complete
  - `agent_context/HANDOFF.md`: sub-deliverable 7 section added
  - `agent_context/TASK_HISTORY.md`: completion record added

**Render Static Site configuration (documented, not deployed):**
- Service type: Static Site
- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- Environment variables: `VITE_API_URL`, `VITE_CLERK_PUBLISHABLE_KEY` (secrets in Render dashboard)
- SPA rewrite: `/*` → `/index.html` (200 rewrite for client-side routing)

**Backend CORS dependency:**
- `ALLOWED_ORIGINS` must be set in Render backend dashboard to include the deployed frontend URL (sub-deliverable 1 already implemented the config; production default is fail-closed deny)

**Clerk configuration:**
- Production Clerk instance configuration is sub-deliverable 8, not part of this task.
- Frontend already uses `VITE_CLERK_PUBLISHABLE_KEY` via `import.meta.env` in `Providers.tsx`.
- Clerk sign-in redirect URLs will need the production frontend URL configured in Clerk dashboard (sub-deliverable 8).

**Verification (actual):**
- `npm run build`: built successfully in 2.67s, `dist/` produced with `index.html` + assets
- `npm run test` (vitest): 71 passed (8 test files)
- `npx tsc --noEmit`: clean
- `npm run lint` (oxlint): clean (warnings only, no errors)
- Live deployment NOT performed (deployment-time; free-tier limitations per AGENTS.md)
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ e4ede49).

**Scope respected:**
- No frontend redesign — existing Vite + React app used as-is
- No new dependencies added
- No secrets or production URLs hardcoded
- Backend CORS config not modified (sub-deliverable 1 already done)
- Clerk dashboard not configured (sub-deliverable 8)

## Milestone 12 — Clerk configuration (2026-11-09, verified)
**Sub-deliverable 8 = Clerk configuration (JWT issuer, JWKS URL, instance strategy).** COMPLETE.

**Root causes (established before changing):**
1. Clerk environment variables declared in `config.py` and `render.yaml` but without validation of JWT issuer format.
2. No documentation existed for development-versus-production Clerk instance strategy.
3. No guidance documented for Render environment variable configuration or Clerk dashboard setup.

**Changes:**
- `src/crack_detection/backend/config.py`: Added `clerk_jwt_issuer` field validator `_validate_clerk_jwt_issuer` that fails fast if `CLERK_JWT_ISSUER` is not a valid HTTPS URL; `clerk_jwks_url` derived from issuer when not explicitly set (`_derive_jwks_url`).
- `tests/unit/test_backend.py`: 2 new tests in `TestSettings` — `CLERK_JWT_ISSUER` without `https://` raises error, `CLERK_JWT_ISSUER` with `https://` accepted.
- `render.yaml`: Clerk env vars declared as `sync: false` secrets; comments documenting Clerk instance setup.
- `.env.example`: Clerk section already has placeholders; no changes needed.
- No changes to `middleware.py`, `routers/auth.py`, `dependencies.py`, or frontend Clerk SDK integration — existing implementation already supports both dev and production Clerk instances via environment variables.

**Clerk instance strategy:**
- Development: Use a Clerk development instance with test keys (`sk_test_*`, `pk_test_*`).
- Production: Create a separate Clerk production instance with production keys (`sk_live_*`, `pk_live_*`).
- The same codebase works for both — only environment variables differ.
- Frontend uses `VITE_CLERK_PUBLISHABLE_KEY` (public, safe in browser bundle).
- Backend uses `CLERK_SECRET_KEY` (secret, server-side only), `CLERK_JWT_ISSUER`, and optionally `CLERK_JWKS_URL`.

**Environment variables:**
| Setting | Location | Secret? | Purpose |
|---|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Frontend `.env.example`, Render Static Site | Yes (browser-exposed but not sensitive) | Clerk publishable key for frontend SDK |
| `CLERK_SECRET_KEY` | Backend `render.yaml` | Yes (never exposed) | Clerk secret key for server-side verification |
| `CLERK_JWT_ISSUER` | Backend `render.yaml` | No | Clerk instance issuer URL (e.g. `https://<instance>.clerk.accounts.com`) |
| `CLERK_JWKS_URL` | Backend `render.yaml` | No | JWKS URL (derived from issuer if not set) |

**JWT verification:**
- Backend verifies RS256 signature against Clerk JWKS endpoint.
- Validates issuer (`iss`) and expiration (`exp`).
- JWKS keys cached with 1-hour TTL for key rotation support.
- Fails closed on any verification error.
- Audience (`aud`) intentionally not verified (Clerk doesn't always include it).

**User identity handling:**
- `ensure_registered_user()` in `database.py` maps Clerk `sub` to local `users` table.
- Requires email claim — fails closed if missing or no existing record.
- Email claim is required for user synchronisation; missing email = no local record = authentication rejected.

**Verification (actual):**
- `pytest tests/unit/test_backend.py -k TestSettings`: 12 passed (9 existing + 3 new Clerk config tests).
- `pytest tests/unit/test_backend.py -k TestClerkJWTVerification`: existing JWT verification tests pass (mocked JWKS, no live Clerk).
- Config validator verified: `CLERK_JWT_ISSUER` without `https://` → ValueError; with `https://` → accepted.
- render.yaml: parses as valid YAML; Clerk vars declared `sync: false`.
- Live Clerk authentication NOT performed (deployment-time; free-tier limitations per AGENTS.md).
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ e4ede49).

**Scope respected:**
- No Clerk dashboard access or configuration.
- No real Clerk credentials generated or used.
- No authentication behavior changes.
- No frontend Clerk SDK changes.
- Model architecture, checkpoint, preprocessing, inference behavior unchanged.

## Milestone 11 — database integration-suite repair (2026-11-08, verified) — records preserved below
---
- `tests/unit/test_backend.py`: 3 new tests in `TestSettings` — missing DATABASE_URL raises validation error, DATABASE_URL without sslmode=raise raises validation error, DATABASE_URL with sslmode=require is accepted.
- `render.yaml`: Comments added documenting DATABASE_URL sslmode=require requirement and Neon pooled vs direct endpoint recommendation.
- `.env.example`: Comments added with Neon pooled vs direct guidance; DATABASE_URL already includes sslmode=require.
- No changes to `database.py` — `psycopg2.connect(settings.database_url)` works with both Neon direct and pooled connection strings.

**Neon endpoint decision (pooled recommended):**
The application opens short-lived per-operation connections and closes them immediately (`get_db_connection` in database.py). It uses no prepared statements, LISTEN/NOTIFY, advisory locks, or temporary tables — all incompatible with PgBouncer transaction mode. This connection lifecycle is the textbook use case for Neon's pooled endpoint, which multiplexes many short-lived connections efficiently and avoids exhausting direct connection limits. Direct endpoint also works if a specific feature requires it.

**Verification (actual):**
- `pytest tests/unit/test_backend.py -k TestSettings`: **9 passed** (6 existing + 3 new).
- Config validator verified: missing DATABASE_URL → ValueError; missing sslmode=require → ValueError; with sslmode=require → accepted.
- render.yaml: parses as valid YAML; DATABASE_URL declared `sync: false`.
- Live Neon connectivity NOT performed (credentials unconfigured; free-tier limitations).
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ e4ede49).

## Milestone 11 — database integration-suite repair (2026-11-08, verified) — records preserved below
---

**Root causes (established empirically before changing):**
1. Production CORS was empty: `allow_origins=["*"] if settings.debug else []` (`main.py`) and no env var existed; `GET`/`POST` responses never carried `Access-Control-Allow-Origin` for the real frontend origin.
2. Middleware ordering: `add_middleware` inserts at index 0 (Starlette 0.46.2 — verified on installed version, not assumed), so the later-added `ClerkAuthMiddleware` was outermost and answered OPTIONS preflights with 401 (no JWT) **and** emitted authentication 401s without CORS headers — browsers could neither complete preflights nor read auth errors. Probe evidence: allowed-origin preflight → 401 ACAO=None; protected GET → 401 ACAO=None.
3. Latent masking bug found while testing: `main.py` instantiated `settings` at module import; `create_app` used that snapshot, so env changes after first import were ignored (initial test failures 400-vs-200 traced to this; also explains why some tests passed under prior-import env). Fixed: `create_app()` calls `get_settings()` itself; module-level `settings = get_settings()` removed (module import no longer eagerly validates env either).

**Changes:**
- `src/crack_detection/backend/config.py`: new `ALLOWED_ORIGINS` field + `_validate_allowed_origins` validator (comma-split, strip, trailing-slash removal, de-dup, wildcard entries stripped — production can never receive `*`) + `cors_allowed_origins` property (explicit config wins; `DEBUG=true` unset → Vite dev origins `http://localhost:5173`, `http://127.0.0.1:5173`; `DEBUG=false` unset → fail-closed `[]`).
- `src/crack_detection/backend/main.py`: CORS uses `settings.cors_allowed_origins`; `ClerkAuthMiddleware` registered **before** CORSMiddleware so CORS is outermost (preflights answered by CORS with no Clerk JWT; non-OPTIONS unchanged; 401s gain ACAO for allowed origins). Docstring comments pin the ordering rationale.
- `.env.example`: `ALLOWED_ORIGINS` section (format, production example, dev/prod fallback semantics).
- `tests/unit/test_backend.py`: `TestCorsAndPreflight` — 13 tests exercising the real stack (fresh `create_app()` per test; env set before importing main because `routers/auth.py:24` builds Settings at module import; cache cleared before/after; no leakage).

**Verification (actual):**
- `pytest tests/unit/test_backend.py -k TestCorsAndPreflight`: **13 passed**.
- Full `tests/unit/test_backend.py`: **213 passed, 0 errors** (was 200).
- Behaviour probe before fix: allowed preflight **401/ACAO None**, protected GET **401/ACAO None**; after fix: preflight 200 + ACAO + `Vary: Origin`; disallowed 400 + no ACAO; guest public preflight 200; 401 with ACAO for allowed origins. (Local TestClient only — live production CORS not yet verified.)
- Git: nothing staged or committed; working tree preserved (`main` @ `e4ede49`).

**Remaining limitations:** live CORS behaviour must be re-verified against the deployed Render backend; `ALLOWED_ORIGINS` must be set in Render env (the production default is fail-closed deny). Milestone 11 real-service validation stays blocked on credentials.

## Milestone 11 (task 4) — database integration-suite repair (2026-11-08, verified) — records preserved below

---

## Milestone 11 — Database integration-suite repair (2026-11-08, verified)

**Root cause (investigated before changing anything):**
- The session-scoped `db_conn` fixture ran with autocommit disabled and never committed or rolled back around tests. Tests inserting via the shared connection left it **idle in transaction** when a later test began.
- `init_schema()` (fresh connection per call) executes DDL statements. On a database where `fk_reports_inspection` still lacked `ON DELETE CASCADE`, its guarded DO-block swap (`ALTER TABLE reports … ADD CONSTRAINT … REFERENCES inspections`) requests locks that conflict with the shared connection's uncommitted transaction on `inspections` → **indefinite wait** (the reproduction: first 3 tests passed, then `TestDatabaseCRUD::test_create_photograph` — whose `init_schema()` fired the swap — hung ≥150s).
- Causality confirmed today: holding an open uncommitted transaction while calling `init_schema()` now completes instantly because `xportra_test` already carries the CASCADE migration (executed in an earlier session's run before the hang). The lifecycle defect was real regardless: failed assertions left aborted transactions, and guest-helper rows (created+committed on their own connections) accumulated — 6 stale expired rows from 2026-11-02/03 were found in the DB.
- Fixture conclusion: the session-scoped connection is **not fundamentally unsuitable** once a transaction lifecycle wraps every test; the smallest reliable correction was a per-test rollback envelope, not a redesign.

**Fixture/test corrections (`tests/unit/test_database_integration.py` only; production code unchanged):**
1. New autouse function-scoped fixture `rollback_db_transaction(db_conn)`: rollback before **and** after every test. Removes lingering/aborted transactions (no idle-in-transaction → no DDL wait), releases row locks, and discards each test's uncommitted rows without destroying committed application data. Non-destructive by design (no TRUNCATE/DROP).
2. `_delete_test_guest_session(session_id)`: targeted cleanup deleting **only** the guest-session row created by a specific test (guest helpers commit on their own connections, outside the rollback envelope); every guest test now cleans up in `finally` → runs are idempotent and no longer accumulate.
3. CRUD tests use uuid-suffixed user ids/emails (fixed `user-1`/`user-2` collided across runs once rows persisted).
4. `test_foreign_key_constraint` rewritten: inserts a real user first (so only `fk_photographs_inspection` can be violated), expects exactly `psycopg2.errors.ForeignKeyViolation` (SQLSTATE 23503) — the old `pytest.raises(Exception)` swallowed its own `conn.commit()` NameError and proved nothing; a follow-up in-test rollback clears the aborted transaction and a COUNT assertion proves no partial write landed.
5. Placement repairs: `test_validate_guest_session_expiration` (was module-level) and `test_increment_analysis_count` (was nested and never collected) are now proper methods of `TestGuestSession`; the expiration UPDATE commits so `validate_guest_session`'s own connection observes it, then the row is deleted entirely.

**Verification (actual):** all connected to the real local PostgreSQL `xportra_test` (verified: connection host/db reported by `current_database()`; genuine psycopg2 throughout; no mocks added anywhere).
- Collection: **9 collected** (before: 8 collected; the never-collected `test_increment_analysis_count` is now among them).
- Each previously affected test individually: **5/5 passed** (`test_create_photograph`, `test_foreign_key_constraint`, `test_validate_guest_session_expiration`, `test_increment_analysis_count`, `test_create_and_read_inspection`).
- Full integration file run 1: **9 passed in 16.67s**.
- Full integration file run 2 (repeat): **9 passed in 11.24s** (and a third direct run: **9 passed in 9.26s**) — rerun independence confirmed. One verification attempt initially timed out at 300s, but three consecutive clean runs immediately after showed it was a shell-pipeline artifact of the harness command, not the suite (no idle-in-transaction remained; process activity check confirmed no lingering connections).
- Post-run DB integrity: `users`/`inspections`/`photographs` counts = **0** (test rows genuinely rolled back); `guest_sessions` count unchanged from the pre-existing 6 stale rows (**zero new accumulation**).
- Full backend regression suite `tests/unit/test_backend.py`: **200 passed, 0 errors** (unchanged).

**Remaining limitations:** the 6 stale expired guest_sessions rows from historical runs were deliberately left untouched (no broad cleanup was authorised; the product's own `cleanup_expired_guest_sessions()` would remove them — hygiene option, non-blocking). `TestGuestSessionRouter` inside the integration file remains a mocked duplicate of the unit-suite guest test (not an integration test; out of scope). Real Clerk/Neon/R2 end-to-end flows remain blocked on credentials.

## Milestone 11 — /auth endpoint behavioural tests (2026-11-08, verified)

**Actual endpoint behaviours (established by reading the implementation before writing tests):**
- `POST /auth/verify` (`routers/auth.py:53`): reads the `Authorization` header; missing, non-Bearer ("Bearer" without token/space, "Basic …"), or empty-Bearer credentials return **HTTP 200** with `{"valid": false, "user_id": null, "email": null}` (fail-closed identity shape, not 401). A Bearer token is verified via `_verify_clerk_jwt`: RS256 signature against Clerk JWKS (kid lookup), issuer and expiration validated (`aud` intentionally not verified), `email` optional; any verification error → the same invalid identity shape. The endpoint performs **no user synchronisation and no database access at all** — that responsibility lives in `get_current_user` (tested separately by `TestGetCurrentUserSync`/`TestEnsureRegisteredUser`).
- `GET /auth/sign-in-url`: derives `https://<issuer-without-scheme>/sign-in` when `CLERK_JWT_ISSUER` is set and does not contain `CHANGE_ME`; otherwise (placeholder or empty issuer) falls back to `https://clerk.accounts.com/sign-in`. HTTP 200, `{"sign_in_url": ...}`.
- `GET /auth/callback`: a **route-completeness placeholder** — returns `{"message": ..., "note": "Clerk handles sign-in, account creation, password handling, and Google OAuth via its hosted pages and frontend SDK."}`; it performs **no OAuth/token processing, no redirect, no auth-state change**. This limitation is documented and tested as-is; no tests imply it authenticates.

**Tests added (12, new `TestAuthEndpoints` in `tests/unit/test_backend.py`, placed after `TestClerkJWTVerification`):** boundaries mocked are JWKS retrieval (`middleware._fetch_jwks`), `database.get_db_connection`, and `dependencies.ensure_registered_user` (asserted never called — documents that verification alone never creates/synchronises users); everything else is real (endpoints via `TestClient(main.app)`, ClerkAuthMiddleware, RSA-keypair JWT signing, RS256 JWKS verification, `get_settings` cache lifecycle managed per test via a `_use_fresh_settings` helper).
- `/auth/verify` (8): valid token (fetch exactly once, exact identity body, exact response-model keys); missing/malformed/non-Bearer credentials ×4 sub-cases with zero JWKS fetches; invalid signature from a foreign key with matching kid (cache hit, no fetch); expired token; issuer mismatch; unknown kid; JWKS-retrieval failure (fails closed; `call_count == 2` documents that **middleware and endpoint each verify the Bearer token independently**); unconfigured issuer/JWKS → fail-closed before any fetch.
- `/auth/sign-in-url` (2): URL derived from configured issuer; placeholder (`CHANGE_ME`) and empty-issuer fallbacks.
- `/auth/callback` (2): exact placeholder body / no redirect / no DB; query parameters (`code`, `state`) ignored — same body.

**Verification (actual):**
- `TestAuthEndpoints` alone: **12 passed** (one initial assertion corrected by the failing run: the JWKS-failure case legitimately fetches twice because both the middleware and the endpoint perform verification).
- Combined authentication-related classes (`TestClerkJWTVerification`, `TestAuthEndpoints`, `TestGuestSessionRouter`, `TestGuestSession`, `TestApplicationFactory`, `TestEnsureRegisteredUser`, `TestGetCurrentUserSync`, `TestInspectionCreationBlockedOnSyncFailure`): **52 passed**.
- Full `tests/unit/test_backend.py`: **200 passed, 0 errors, 0 deselected** (was 188).
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ `a834c33`).
- Production code: **no changes, no defects found** in the auth endpoints. (One latent note reused from the previous task: `routers/guest.py` stale `Request` annotation.)

**Not claimed:** live Clerk authentication (test-key-signed JWTs + mocked JWKS are not real Clerk integration); frontend Clerk SDK flows (mock-tested only).

## Milestone 11 — Guest-session tests made genuine (2026-11-08, verified)

**Why this before the doc-listed `/auth` tests:** `ROADMAP.md` imposes no ordering within the open authentication criterion; remediating untrustworthy tests precedes new test areas per `agent_context/DEVELOPMENT_RULES.md` (corrective-first, §7–8). No dependency required `/auth` tests first. The forward list below reflects this reordering.

**Prior state:** all 5 `TestGuestSession` tests in `tests/unit/test_backend.py` were vacuous — each patched `database.create_guest_session` / `validate_guest_session` / `increment_guest_analysis_count`, called the patch, and asserted exactly the mocked return value. None of the real guest-session implementation was executed.

**Replaced with 11 genuine data-layer tests (boundary: `get_db_connection`/`psycopg2.connect` mocked; the real guest-session code is executed):**
- Creation (2): INSERT statement text + params (token generated by the real `secrets.token_urlsafe(32)` — 43 chars, no fabricated value — and ~24h expiry computed from `now(utc)`), returned row equality, commit; `expiration_hours=0` falls back to the configured default (24h per `config.py`).
- Validation (4): valid session returned, with SQL `(WHERE session_token = %s AND is_active = TRUE)` and **no commit** on the read path; unknown token → `None` with a single SELECT; expired (tz-aware) → `None` plus a second-connection `UPDATE guest_sessions SET is_active = FALSE WHERE id = %s` + commit; naive `expires_at` (tz-less) correctly interpreted as UTC.
- Increment (2): within-limit returns the new count, with the atomic guard predicates verified verbatim (`WHERE id = %s`, `AND is_active = TRUE`, `AND analyses_count < %s`, `AND expires_at > NOW()`, `RETURNING analyses_count`, params `(session_id, max_analyses)`) + commit; the guarded UPDATE yielding no row (session at limit) → `None`.
- Scaffold (2): connection failure wrapped as `DatabaseError` (no rollback possible, nothing committed); statement failure inside a real `get_db_connection` → rollback + close by the real scaffold, error wrapped in `DatabaseError`, never committed; a separate happy-path scaffold test proves commit + `finally` close when `psycopg2.connect` is patched and the real contextmanager runs.

**Plus 5 router tests in `TestGuestSessionRouter` (`TestClient(main.app)`; DB layer mocked only at the `routers.guest` namespace — an external boundary; router logic genuine):**
- `GET /guest/session/validate` with a valid session → `valid=true`, counts/remaining computed by the router, DB layer called with the header token verbatim.
- Missing header → `valid=false`, zero remaining, DB layer never contacted; invalid/expired token → `valid=false`.
- `POST /guest/session/consume-analysis` within allowance → `consumed=true`, count/remaining correct, increment called with `(session_id, max_analyses=3)`.
- At limit → `consumed=false`, remaining 0. Missing header → 401 "Guest session token required", DB layer never contacted.

**Verification (actual):**
- Targeted guest-session tests: **18 passed** (new + retained, `-k "TestGuestSession or guest_session"`).
- Full `tests/unit/test_backend.py`: **188 passed, 0 errors, 0 deselected** (was 177 after the entry-point fix).
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ `a834c33`).
- Two initial expectation errors in the new tests were caught by their own failing runs and corrected during the task: (a) `secrets.token_urlsafe` output may legitimately contain `-`/`_` (URL-safe base64 alphabet), so the token assertion is type+length only; (b) patching `get_db_connection` replaces the whole contextmanager and bypasses its real `finally` scaffold, so `closed` assertions are only meaningful when `psycopg2.connect` is patched instead — the scaffold is now exercised in the two dedicated scaffold tests.
- Production-code observation (flagged, deliberately not fixed): `src/crack_detection/backend/routers/guest.py` annotates `request: Request` without importing `Request` (line ~245). Empirically harmless (module import, `create_app()`, and a real uvicorn run all verified) because annotations are not evaluated eagerly; a latent-unstable pattern worth noting for a future cleanup, out of scope here.
- `tests/unit/test_database_integration.py` remains untouched and still hangs (separate task).

## Next task (per ROADMAP.md Milestone 12)

Deployment sub-deliverable **2: model checkpoint availability on Render** (build-time fetch from the existing R2 bucket via a pre-signed URL; checkpoint is never committed), then sub-deliverable **3: Render backend service configuration** (Python 3.12.x, uvicorn start command, `/live` health check, torch CPU wheel index). Requires user-owned R2 account access; no code changes expected beyond a fetch script/build command. Earlier blockers remaining: real Clerk/Neon/R2 end-to-end flows (credentials).1. ~~Add `/auth` router endpoint tests~~ — COMPLETE (verified 2026-11-08; record above).
2. ~~Replace the vacuous `TestGuestSession` tests with genuine behaviour tests~~ — COMPLETE (verified 2026-11-08; record below).
3. ~~Diagnose/fix the `tests/unit/test_database_integration.py` hang~~ — COMPLETE (verified 2026-11-08; record above).
4. **Real-service (Neon/R2/Clerk) integration validation** — the only remaining Milestone 11 item at implementation level; BLOCKED on credentials (deployment-time). Non-blocking hygiene observations, each a separate smallest task if pursued: the stale `request: Request` annotation in `routers/guest.py` (~line 245); the 6 stale expired guest_sessions rows in `xportra_test` (removable via the product's own `cleanup_expired_guest_sessions()`).

## Milestone 11 — Application entry point fix (2026-11-08, verified)

**Root cause:** `main.py` defined `create_app()` but module-level `@app.on_event("startup")` and `@app.get("/")` referenced an `app` name never assigned → `NameError: name 'app' is not defined` on import; `TestGuestSessionRouter::test_create_guest_session` failed in setup; `uvicorn crack_detection.backend.main:app` could not work.

**Changes:**
- `src/crack_detection/backend/main.py` — `_startup_event` is now a module-level function registered inside `create_app()` via `app.add_event_handler("startup", ...)`; root `GET /` route moved inside `create_app()`; module-level `app = create_app()` added. Handler behaviour preserved verbatim.
- `tests/unit/test_backend.py` — new `TestApplicationFactory` (3 tests): factory wiring (startup handler, ClerkAuthMiddleware, key routes), module-level `app` import + distinct fresh instance, root endpoint served via `TestClient(main.app)`.

**Verification (actual):**
- Targeted (factory + guest-router): **4/4 passed**.
- Full `tests/unit/test_backend.py`, no deselect: **177 passed, 0 errors** (was 173 passed + 1 setup error).
- Import smoke: `main.app` is a FastAPI app titled "CrackSight AI" with `_startup_event` registered.
- Real Uvicorn run: `python -m uvicorn crack_detection.backend.main:app --port 8123` → startup complete, `GET /` → 200 `{"service":"CrackSight AI","version":"0.1.0","status":"operational"}`.
- `python-multipart==0.0.10` is installed in `.venv` (earlier context blaming it for the import failure is stale); `tests/unit/test_database_integration.py` untouched and still hangs (separate task).
- Git: nothing staged or committed; all pre-existing changes preserved (`main` @ `a834c33`).

## Approved decisions (2026-11-08)

- PDF library: **ReportLab**.
- Report generation: **registered users only**; guests excluded.
- Inspection status: **allow both Draft and Completed** inspections.
- Report ID: **full UUID**.
- Model version: display the existing **checkpoint epoch verbatim**, clearly labelled.
- Branding: text wordmark "CrackSight AI", navy `#18313b` / teal `#167f78`, matching existing frontend tokens.

## Objective

Enable registered users to generate and download professional PDF inspection reports containing: application branding, unique report ID, report generation date, inspection information, photographs with analysis results, available pixel measurements, model version, inspector observations, verification statuses, limitations/safety disclaimer, and page numbers.

## Audit findings

### Existing functionality (verified by code inspection)

- **Stub endpoints exist**: `src/crack_detection/backend/routers/reports.py` has `POST /reports/generate/{inspection_id}` (verifies ownership, inserts a `reports` row, returns `ReportGenerateResponse` — but generates NO PDF, explicit TODO) and `GET /reports/{report_id}/download` (verifies ownership but returns a JSON dict message, not a PDF, explicit TODO).
- **Schema exists**: `reports` table (`id, inspection_id, user_id, report_pdf_key, generated_at, page_count`) with FKs to `inspections`/`users`, index on `inspection_id`. Note: the `reports.inspection_id` FK has **no ON DELETE CASCADE**, and `delete_inspection` does a bare `DELETE FROM inspections` — once report rows exist, inspection deletion will raise an FK violation (500) and R2 PDFs under `reports/` will not be cleaned up.
- **Schemas exist**: `ReportGenerateResponse` (report_id, generated_at, download_url) in `schemas.py`.
- **Router registered**: `/reports` prefix in `main.py`.
- **No PDF library in `requirements.txt`**; no report tests in `tests/unit/test_backend.py` (only an unrelated reopen test asserting reports rows are untouched).
- **Frontend**: mock-only. `api.ts` has `generateReport()` wired to the stub endpoint (unused by pages). `ReportsPage.tsx` proves the expected report-sheet design: "CrackSight AI" wordmark header, report ID, generated date, image row, "AI-assisted prediction · Wall" section with pixel measurement + model version, "Inspector observation" section, "Limitations" disclaimer. `InspectionDetailPage.tsx` has per-photo "Download original" only — no report download action.

### Report-field-to-data-source mapping (all fields available, no fabrication)

| Report field | Source | Gap |
|---|---|---|
| App branding | `config.app_name` ("CrackSight AI") + frontend design tokens | None — text wordmark; no logo file exists anywhere |
| Report ID | `reports.id` UUID (stub already generates) | None |
| Generation date | `reports.generated_at` | None |
| Inspection info | `inspections` (title, building_type, building_location, notes, status, created_at) | None |
| Photographs + structure type | `photographs` rows (query pattern exists in `list_inspection_photographs`) | Report needs internal R2 keys (original/mask/overlay), so it cannot reuse the metadata-only response |
| Analysis artifacts | `R2Storage.download_file` on `original_image_key` / `prediction_mask_key` / `prediction_overlay_key` | None (existing storage API) |
| Pixel measurements | `photographs.pixel_measurements` JSONB (crack_pixel_count, crack_pixel_percentage, bounding_box, region_count) — persisted by Task 1.4 | None |
| Model version | `photographs.model_version` (from `pipeline.checkpoint_meta.get("epoch")` — a checkpoint **epoch number**, not a semantic version) | Present verbatim, labelled as checkpoint epoch; do not invent a semantic string |
| Inspector observation | `photographs.observation` | None |
| Verification status | `photographs.verification_status` (not_verified/correct/incorrect/partial) | None |
| Disclaimer | Static copy — reuse the prototype wording ("AI-assisted crack predictions are not a structural safety assessment… Measurements are image-space pixels only") | None |
| Page numbers | Generated in PDF footer | None |
| PDF bytes → R2 → download | New work: generate in-memory → upload `reports/{report_id}.pdf` → download streams bytes | PDF library + endpoint bodies |

### PDF library recommendation: ReportLab

- **ReportLab**: pure pip install (bundled platform wheels for CPython 3.12 / Windows), BSD-style license, programmatic Platypus flowables give native header/footer/page-number/table control, PNG/JPEG embedding straightforward, testable headlessly via `BytesIO`. Fits the project's constraints (Windows dev env, free/budget deployment, "avoid unnecessary dependencies and infrastructure").
- **WeasyPrint rejected**: requires system-level GTK/Pango/Cairo stack on Windows and heavier deployment dependencies; AGPL-or-commercial licensing is a budget/licensing risk.
- Decision was explicitly unresolved in `TECHNICAL_DESIGN.md`; approval sought below.

### Branding/layout recommendation (from existing materials; no new identity invented)

- Text wordmark "CrackSight AI" in navy `#18313b` with teal `#167f78` accent block (mirrors `.brand__mark` square treatment and `index.css` tokens).
- Sections: header (brand, report ID, generated date) → inspection information table → summary count (photos by structure type) → per-photograph blocks (original + overlay images, "AI-assisted prediction" measurements + model version distinctly separated from "Inspector observation", verification status) → limitations & safety disclaimer → footer with "Page N of M".
- Photographs without a successful prediction render as "Prediction not available" (never fabricated).

## Implementation plan (dependency order)

1. ~~Declare `reportlab` in `requirements.txt` and install into `.venv`~~ — **COMPLETE (verified 2026-11-08)**
2. ~~Create `src/crack_detection/backend/report_generator.py` — pure generator module + focused unit tests~~ — **COMPLETE (verified 2026-11-08)** (steps 1+2 delivered together; 31/31 tests pass)
3. ~~Implement `generate_report` endpoint: registered-user-only (`require_authenticated_user`), ownership, gather inspection + photographs (internal query incl. R2 keys), download images, generate PDF, upload to R2, insert `reports` row (with `page_count`), failure compensation~~ — **COMPLETE (verified 2026-11-08)** (see Step 3 record; includes 13 endpoint tests, so step 6's generation-side tests are also done)
4. ~~Implement `download_report` endpoint body: stream PDF bytes from R2 (pattern: `_download_registered_image`)~~ — **COMPLETE (verified 2026-11-08)** (see Step 4 record; 8 endpoint tests)
5. ~~Fix inspection-delete interplay: idempotent FK cascade migration for `reports.inspection_id` + per-row `report_pdf_key` R2 cleanup on inspection deletion~~ — **COMPLETE (verified 2026-11-08)** (see Step 5 record; 12 tests)
6. ~~Add `TestReportGeneration` tests in `tests/unit/test_backend.py`~~ — **COMPLETE (verified 2026-11-08)** (13 generation tests in step 3; 8 download tests in step 4; 12 deletion/migration tests in step 5)
6. ~~Add `TestReportGeneration` tests in `tests/unit/test_backend.py`~~ — **COMPLETE (verified 2026-11-08)** ...
7. ~~Frontend wiring (InspectionDetailPage report download action, ReportsPage real data) after backend verified.~~ — **COMPLETE (verified 2026-11-08)** — `downloadReportPdf` added to `frontend/src/services/api.ts` mirroring `downloadPhotographImage`; InspectionDetailPage gained an authenticated-users-only report card (generate + download, duplicate-prevention, inline errors, `cracksight-report-{report_id}.pdf` filename, blob URL revoked after click, Draft and Completed both allowed); ReportsPage kept as clearly-labelled sample content with its "Generate report" CTA navigating to `/app/history` and no fabricated report-list endpoint; `frontend/src/services/api.test.ts` extended (generateReport + downloadReportPdf, bearer header, blob URL, ApiError paths); new `InspectionDetailPage.test.tsx` (7 tests) and `ReportsPage.test.tsx` (3 tests).

## Step 1 record (2026-11-08, verified)

**Dependencies:**
- `requirements.txt`: added `reportlab>=4.2.0,<5.0.0` (backend section, with audit rationale comment), `pypdf>=4.0.0` (new test-only section), transitive pin `charset-normalizer==3.5.2`.
- Installed into `.venv`: **reportlab 4.5.1**, **pypdf 7.0.0** (transitive: charset-normalizer 3.5.2; existing Pillow 13.0.0 satisfies reportlab's `pillow>=9` requirement).

**Module (`src/crack_detection/backend/report_generator.py`, standalone — no FastAPI/DB/R2 imports):**
- Dataclasses: `PhotographReportEntry` (photo_id, structure_type, verification_status, observation, model_version, prediction_timestamp, pixel_measurements, original_image bytes, overlay_image bytes), `InspectionReportData`, `ReportMetadata`.
- `generate_inspection_report_pdf(report_data, report_metadata, *, disclaimer_html=DEFAULT_DISCLAIMER_HTML) -> bytes` — A4, branded header band on every page (teal accent square + navy wordmark), footer on every page (persistent safety note + `Page X of Y` via two-pass `_BrandedPageCanvas`).
- Sections: title block → report metadata table (Report ID, Generated at, Inspection ID, Inspection status) → inspection information table → photograph summary (count + per-structure-type breakdown) → per-photograph blocks ("Photograph N — Wall/Beam/Column", structure type, colored verification status, original+AI-predicted-overlay image pair with captions, "AI-assisted prediction (model output — requires verification)" block with `Model version (checkpoint epoch): <epoch>` + prediction time + `Image-space measurements (pixels)` lines [crack pixels formatted, coverage %, region count, bounding box], "Inspector observation (recorded by inspector)" block) → "Limitations and safety disclaimer" pale box (approved prototype wording verbatim).
- Graceful degradation: missing overlay/measurements/model version → explicit "Not available"/"Not recorded"; missing observation → "No observation recorded."; missing/corrupt image bytes → "…not available" placeholders (ImageReader failure caught); zero-crack-pixel measurement dict → "No crack pixels were detected"; zero-photograph inspections → summary "No photographs were analysed"; unknown verification statuses rendered verbatim; optional fields → "Not provided"; XML escaping on user text.
- No physical units anywhere (pixels only); no fabrication of any value.

**Tests (`tests/unit/test_report_generator.py` — new file, 31 tests in 5 classes):**
- Valid generation (%PDF signature, pypdf-parseable, PDF metadata title/author), page-number footer consistency, disclaimer (default + custom), footer safety note.
- Report metadata + inspection info presence, Draft/Completed status, "Not provided" fallbacks, completed-at missing, XML escaping.
- Multi-photograph presentation, structure-type summary, verification-status display incl. unknown-verbatim, multi-page output (4 photos → ≥2 pages with correct `Page N of M` per page), zero photographs, missing observation.
- AI vs inspector section separation/order, checkpoint-epoch label verbatim, model-version missing, image-space measurement lines, no physical units (mm/cm/millimetre regex absence), zero crack pixels, measurements missing, prediction timestamp.
- Image assets: missing original+overlay placeholders, corrupt bytes graceful, ≥2 image XObjects embedded for a complete photo, mixed missing/present.

## Verification (actual, 2026-11-08)

- New report-generator tests: **31/31 passed** (`PYTHONPATH=src`).
- Backend full suite (`tests/unit/test_backend.py`): **140 passed, 1 pre-existing error deselected** (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`, unrelated; no regressions).
- `tests/unit/test_inference.py`: **17 passed** (no regressions).
- Import smoke check: `crack_detection.backend.report_generator` imports cleanly against installed reportlab 4.5.1.
- No failures; nothing skipped by the new tests. Unit tests only — no integration tests were added (endpoint integration comes with step 3/6).

## Step 3 record (2026-11-08, verified)

**Generator extension (backwards compatible — 31/31 existing tests keep passing):**
- `generate_inspection_report_pdf(..., page_count_sink: Optional[List[int]] = None)` — after a successful build the total page count (from the two-pass branded canvas) is appended to the sink; the endpoint persists it into `reports.page_count` without parsing the PDF (pypdf stays test-only).

**Endpoint (`generate_report` in `src/crack_detection/backend/routers/reports.py`):**
- Access: `require_authenticated_user` dependency — guests → 403, no identity → 401; nothing is generated for either (verified: zero SQL executed).
- Ownership: inspection lookup (`SELECT id, user_id, title, building_type, building_location, notes, status, created_at, completed_at FROM inspections WHERE id = %s`); nonexistent → 404 "Inspection not found"; foreign → `require_ownership` plain-`HTTPException` 404 "Resource not found"; both opaque and identical to clients.
- Draft AND Completed inspections allowed for reporting.
- Photographs: one query incl. internal keys (`original_image_key`, `prediction_overlay_key`), ordered by `created_at, id`. Missing overlay key (photo never analysed) → `None` → graceful placeholder in PDF ("Predicted overlay not available"); `original_image_key` is NOT NULL by schema so it always downloads.
- Asset download failures (`StorageError`) → 500 "Failed to retrieve photograph assets: …" — no upload, no insert, nothing persisted.
- PDF built fully in memory via the real generator (`ReportMetadata` id/time, `report_content` dataclasses), uploaded to R2 at `reports/{report_id}.pdf` (`application/pdf`).
- Upload failure → 500 "Failed to upload generated report: …"; best-effort `delete_file` attempted (nothing uploaded in practice); no report row inserted.
- Persistence: `INSERT INTO reports (id, inspection_id, user_id, report_pdf_key, page_count) VALUES (...) RETURNING id, generated_at` + `conn.commit()`. DB failure → best-effort `delete_file(report_key)` (cleanup failures logged, never raised — original error preserved) → 500 "Failed to record report generation: …"; `committed` stays False in tests.
- Response: `ReportGenerateResponse(report_id=row["id"], generated_at=row["generated_at"], download_url=f"/reports/{row['id']}/download")` — the persisted row's id is used consistently (a mid-session bug where `download_url` referenced the local uuid4 was caught by the success test and fixed); internal R2 keys never appear in the response.
- `GET /reports/{report_id}/download` stub body left untouched (step 4).

**Tests (13 new tests in `TestReportGeneration`, `tests/unit/test_backend.py`, via `_reports_app` helper + `_report_storage` fake + `_SeqConn`):**
- Success: 200 body (report_id/download_url/generated_at), R2 upload recorded (key `reports/*.pdf`, content type, real PDF parseable), inspection text present in stored PDF, INSERT row (id↔key consistency, inspection_id, user_id, page_count == actual pypdf page count), `committed` True, internal keys absent from response.
- Draft & Completed labelled in PDF ("Draft"/"Completed"); zero-photo inspection → "No photographs were analysed" placeholder; multi-photograph (2 photos → 4 downloads, count rendered, persisted page count matches); missing overlay degrades (1 download, "Predicted overlay not available").
- Access control: guest → 403 with zero SQL/no upload; anonymous → 401; unknown inspection → opaque 404 with only one SELECT executed; foreign inspection → opaque 404 ("Resource not found", "Resource not found" via `require_ownership` plain HTTPException), no upload/insert.
- Failure stages: R2 asset download failure → 500 with no insert; PDF generation failure (generator monkeypatched to raise) → 500, no upload/insert; R2 upload failure → 500, no insert; DB persistence failure (wrapped cursor raises `DatabaseError` on `INSERT INTO reports`) → 500 + uploaded PDF deleted best-effort (`storage.deleted` contains the report key) + `committed` False.

## Verification (actual, 2026-11-08, steps 2–3)

- `TestReportGeneration`: **13/13 passed**.
- `tests/unit/test_report_generator.py`: **31/31 passed** (no regressions from the `page_count_sink` extension).
- `tests/unit/test_backend.py` full: **153 passed, 1 pre-existing error deselected** (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`, unrelated; was 140 before this step, +13 new).
- `tests/unit/test_inference.py`: **17 passed** (no regressions).
- Combined backend+generator run: **184 passed, 1 pre-existing error**.
- Git: nothing staged or committed; all prior uncommitted work preserved (`main` @ `a834c33`).

## Step 4 record (2026-11-08, verified)

**Endpoint (`download_report` in `src/crack_detection/backend/routers/reports.py`, stub body replaced):**
- Access: `require_authenticated_user` dependency (replaces the stub's `get_current_user`) — guests → 403, no identity → 401; zero SQL executed on either path.
- One query `SELECT r.report_pdf_key, i.user_id FROM reports r JOIN inspections i ON r.inspection_id = i.id WHERE r.id = %s` (narrowed from the stub's `r.*`); nonexistent → HTTPException 404 "Report not found"; foreign owner → `require_ownership` 404 "Resource not found" — both opaque, storage never contacted.
- PDF streamed from R2 via `storage.download_file(report_pdf_key)` (`report_pdf_key` is NOT NULL by schema, so no null-key branch). `StorageError` (incl. missing object) → 500 "Failed to retrieve report: {exc}" per the established `_download_registered_image` convention; internal key logged server-side only.
- Response: FastAPI `Response` with the actual PDF bytes — `Content-Type: application/pdf` (`_PDF_CONTENT_TYPE`), `Content-Disposition: attachment; filename="cracksight-report-{report_id}.pdf"`. No JSON, no download URL, no storage keys.
- Generation endpoint untouched.

**Tests (8 new tests in `TestReportDownload`, `tests/unit/test_backend.py`, reusing `_reports_app`/`_report_storage`/`_SeqConn` via mocked storage — clarifying: these are distinct mocked endpoint tests, not real R2/DB integration):**
- Success: 200 with actual PDF bytes, `application/pdf` content type, exact attachment disposition `attachment; filename="cracksight-report-{report_id}.pdf"`, correct R2 key downloaded, JOIN ownership query verified, `committed is False` (read-only), no internal key in any response header.
- Guest → 403 with zero SQL/no storage access; anonymous → 401 with zero SQL; nonexistent → 404 "Report not found" (one query only, no download); foreign → 404 "Resource not found" (one query only, no download).
- Missing R2 object (`NoSuchKey` StorageError) → 500 "Failed to retrieve report", no content-disposition header; general R2 failure → 500 same convention.
- Filename: dedicated test asserting disposition starts with "attachment", contains report ID, ends `.pdf"`.

## Verification (actual, 2026-11-08, step 4)

- `TestReportDownload`: **8/8 passed**.
- Combined backend + generator run: **192 passed, 1 pre-existing error** (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`, unrelated).
- `tests/unit/test_backend.py` with that error deselected: **161 passed** (was 153 before step 4, +8 new).
- `tests/unit/test_report_generator.py`: **31/31 passed** (contained in the 192).
- `tests/unit/test_inference.py`: **17 passed**.
- Git: nothing staged or committed; all prior uncommitted work preserved (`main` @ `a834c33`).
- All report/download tests are mocked endpoint tests; no real R2 or PostgreSQL integration tests were run (external services not configured locally).

## Step 5 record (2026-11-08, verified)

**FK cascade migration (`src/crack_detection/backend/database.py`):**
- `CREATE TABLE IF NOT EXISTS reports` FK updated to `fk_reports_inspection ... ON DELETE CASCADE` (fresh databases).
- Idempotent DO-block statement appended for **existing deployments** (a `CREATE TABLE IF NOT EXISTS` never alters an existing table): fires only when `information_schema.referential_constraints` shows `fk_reports_inspection` with `delete_rule <> 'CASCADE'`, then `ALTER TABLE reports DROP CONSTRAINT fk_reports_inspection;` + re-`ADD ... ON DELETE CASCADE`. Repeatable on fresh and existing databases; no rows touched, no tables recreated; no other FKs affected.
- Migration coverage is **mocked only**: `init_schema()` executed against a fake recording connection (`_SeqConn` with context-manager support); both new statements' text verified. Not executed against real PostgreSQL (no integration DB configured locally).

**Inspection deletion (`delete_inspection` in `routers/inspections.py`), failure semantics:**
- New step 1: `SELECT report_pdf_key FROM reports WHERE inspection_id = %s` — keys captured **before** any deletion.
- New step 2: per-key `storage.delete_file(report_pdf_key)` — idempotent (missing objects are no-ops by `R2Storage.delete_file` design), so retries/partial cleanup are safe. Any exception → logged (original error preserved) → 500 "Failed to delete associated report files; the inspection was not deleted." **before the DB DELETE** — committed `reports` rows keep their keys for retry.
- Chosen ordering rationale (documented in code): storage cleanup happens **before** the DB DELETE, following the endpoint's existing photograph-prefix cleanup order. PostgreSQL and R2 cannot share a transaction; the trade-off is a documented, recoverable inconsistency (if the DB DELETE/commit later fails, `get_db_connection` rolls back → inspection + report rows remain, pointing at now-deleted PDFs → those report downloads return 500 until deletion is retried, at which point the re-deletes are no-ops) instead of post-commit R2 orphans (rows deleted → keys unknown → orphaned PDFs unrecoverable).
- Step 3 (unchanged): photograph-prefix cleanup.
- Step 4 (unchanged shape): `DELETE FROM inspections WHERE id = %s` + commit — the FK cascade removes the inspection's report rows in the same transaction. No explicit `DELETE FROM reports`; deletion of an already-deleted inspection 404s (safe repetition).
- `report_pdf_key` is NOT NULL by schema; an `if not report_key` guard is retained defensively.

**Tests (12 new: `TestReportsForeignKeyCascadeMigration` 3 + `TestInspectionDeletionWithReports` 8 + `test_report_download_after_parent_inspection_deleted` in `TestReportDownload`):**
- Migration: fresh-DB CREATE TABLE declares cascade; single guarded DO-block swap statement; no unguarded `DROP CONSTRAINT` statements; `fk_photographs_inspection` untouched.
- Deletion: no reports → no `delete_file` calls, prefix cleanup + DELETE + commit intact (204); one report; multiple reports; keys retrieved before DELETE and R2 cleanup ordered before prefix cleanup; no explicit `DELETE FROM reports` (cascade expected).
- R2 report-PDF deletion failure → 500, `committed is False`, no inspection DELETE, prefix cleanup not reached.
- Retry after failure: attempt 1 (500; aborted at first key), attempt 2 (204; re-delete of key A is a safe no-op, key B deleted, rows committed) — 3 `delete_file` events total.
- Nonexistent → 404 with zero cleanup; foreign → 404 "Resource not found" with zero cleanup (existing ownership rule regression).
- Download after parent inspection deleted → report row gone (cascade) → opaque 404, storage never contacted.

## Verification (actual, 2026-11-08, step 5)

- New step-5 tests: **12/12 passed**.
- Combined backend + generator run: **204 passed, 1 pre-existing error** (`TestGuestSessionRouter::test_create_guest_session` — module-level `app` NameError in `main.py:82`, unrelated).
- `tests/unit/test_backend.py` with that error deselected: **173 passed** (was 161 before step 5, +12).
- `tests/unit/test_report_generator.py`: **31/31 passed**.
- `tests/unit/test_inference.py`: **17 passed**.
- All tests are mocked (FakeConnection/_SeqConn + in-memory storage fakes) — the FK migration and R2 cleanup have **not** been integration-tested against real PostgreSQL/R2 (services not configured locally).
- Git: nothing staged or committed; all prior uncommitted work preserved (`main` @ `a834c33`).

## Task outcome

Milestone 8 Task 6 (Deliverable 6 — PDF reports) is complete: backend steps 1–5, Step 6 verification, and Step 7 frontend wiring are all implemented and verified. All eight Milestone 8 deliverables are complete — see `CURRENT_STATE.md` and the `ROADMAP.md` Milestone 8 status table. All report/backend tests are mocked (FakeConnection + in-memory storage fakes); real-service (PostgreSQL/R2) integration testing remains deployment-time and is NOT marked complete.

## Verification (actual for this audit)

- No code changed. No dependencies installed. Git status inspected: `main` @ `a834c33` + all prior uncommitted work preserved.
- Documentation reconciled: `ROADMAP.md` deliverable/status rows and `agent_context/` files now reflect Deliverable 6 COMPLETE (frontend wiring included); real-service integration testing explicitly NOT marked complete.

## Legacy note (superseded by the Milestone 12 record above)

Milestone 11 (Testing and Security) is complete except real-service integration validation, which remains BLOCKED on Neon/R2/Clerk credentials (deployment-time work). All mocked-level gaps (`/auth` endpoint tests; `tests/unit/test_database_integration.py` hang repair) are closed.
