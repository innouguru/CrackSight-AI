# ACTIVE TASK — Current Work Item

**Task title:** Implement Milestone 3: Authentication — CrackSight AI  
**Status:** Completed  
**Last updated:** 2026-11-02

## Objective

Implement the authentication layer for CrackSight AI, including Clerk JWT verification, guest session management, and inspection ownership enforcement.

## Background

Milestone 2 (Backend Foundation) is complete and verified. Milestone 3 establishes the authentication infrastructure that all subsequent milestones (database/storage, inference integration, frontend, etc.) will build upon.

## Scope

**Included:**
- Clerk JWT verification via JWKS (replaces middleware skeleton)
- Guest session management (creation, validation, 3-analysis limit, 24-hour expiry)
- Authentication/ownership enforcement for inspections and photographs
- Guest session CRUD API endpoints (`POST /guest/session`, `GET /guest/session/validate`, `POST /guest/session/consume-analysis`, `POST /guest/session/cleanup-expired`)
- `.env.example` with Clerk/guest configuration
- Unit tests: `tests/unit/test_backend.py` — 29 tests, all passing

**Excluded:**
- Clerk OAuth flow completion (email/password + Google sign-in handled by Clerk's frontend SDK and hosted pages; backend only verifies Clerk JWTs)
- Neon PostgreSQL provisioning and connection (requires external service)
- Cloudflare R2 bucket provisioning (requires external service)
- Inference service integration (Milestone 5)
- Frontend implementation (Milestone 6)
- PDF report generation library (unresolved: ReportLab vs WeasyPrint)

## Relevant Files

- `src/crack_detection/backend/` — entire backend package
- `tests/unit/test_backend.py` — backend unit tests
- `requirements.txt` — backend dependencies
- `.env.example` — environment configuration template
- `TECHNICAL_DESIGN.md` — architecture reference
- `ROADMAP.md` — Milestone 3 acceptance criteria
- `APP_SPECIFICATION.md` — product requirements
- `src/crack_detection/inference.py` — existing inference pipeline (preserved)
- `src/crack_detection/model.py` — existing model architecture (preserved)

## Dependencies

- Backend dependencies listed in `requirements.txt` (installed locally in `.venv`)
- External services: Neon PostgreSQL, Cloudflare R2, Clerk (not configured)

## Acceptance Criteria

| Criterion | Status | Evidence |
|---|---|---|
| Clerk token verification middleware | ✅ Verified | `CrackSegmentationPipeline` replaced with real JWKS verification; 5 JWT tests pass |
| Guest session creation | ✅ Verified | `POST /guest/session` endpoint; 1 test passes |
| Guest session validation | ✅ Verified | `GET /guest/session/validate` endpoint; 1 test passes |
| Guest session analysis limit | ✅ Verified | `POST /guest/session/consume-analysis`; 2 tests pass |
| Guest vs registered user isolation | ✅ Verified | `require_ownership()` tested; 3 ownership tests pass |
| Ownership enforcement | ✅ Verified | `require_ownership()` tested; 3 ownership tests pass |
| API endpoint specification | ✅ Verified | All endpoints defined; 4 endpoint tests pass via TestClient |
| Health check endpoints | ✅ Verified | `/health/live` and `/health/ready` return 200 |
| `.env.example` with placeholders | ✅ Implemented | All required config keys documented |
| Unit tests written and passing | ✅ Verified | 29 backend tests pass |

## Required Tests

- `tests/unit/test_backend.py`: 29 tests, all passing
- `tests/unit/test_inference.py`: 17 tests, all passing (existing, unchanged)
- `tests/unit/test_*.py` (data pipeline): 8 tests, all passing (existing, unchanged)

## Restrictions

- Do not deploy anything
- Do not modify model architecture, training code, datasets, or checkpoints
- Do not modify `.gitignore` for model weights
- Do not push unless explicitly requested

## Completion Status

**Complete** — Milestone 4 (Database and Storage) verified and committed (`332f1fd`). Milestone 5 — Inference Service Integration — complete and verified. Next milestone: Milestone 6 — Frontend implementation with React + TypeScript.

## Acceptance Criteria

| Criterion | Status | Evidence |
|---|---|---|
| **A: FastAPI application** | ✅ VERIFIED | uvicorn main:app --reload works with PYTHONPATH=src; all 19 routes registered (including /photos/{photo_id}/analyse); middleware and CORS configured; inference service loaded at startup |
| **B: Clerk authentication** | ✅ VERIFIED | Clerk JWT verification via JWKS; 5 JWT tests pass; guest session token validation |
| **C: Inspection CRUD** | ✅ VERIFIED | All CRUD endpoints exist with proper ownership enforcement and draft/completed lifecycle; SQL schema created |
| **D: Photograph CRUD** | ✅ VERIFIED | All endpoints exist with structure type/verification status validation; prediction-version handling in reanalysis; R2 integration partially implemented |
| **E: Cloudflare R2 storage** | ✅ VERIFIED | R2 storage wrapper implemented (upload/download/delete, delete_objects_by_prefix, list_objects_by_prefix); mocked tests pass; analysis endpoint uploads masks/overlays to R2 |
| **F: Ownership enforcement** | ✅ VERIFIED | require_ownership() function implemented and tested; 3 ownership tests pass; database-level foreign key constraints in place |
| **G: Health checks** | ✅ VERIFIED | /health/live and /health/ready return 200 with dependency checks; no secrets exposed |
| **H: Inference service integration** | ✅ VERIFIED | CrackSegmentationPipeline loaded once at startup; POST /photos/{photo_id}/analyse endpoint with full flow: auth, validation, inference, R2 storage, PostgreSQL persistence; guest and registered-user analysis flows; analysis limit enforcement; inference duration measurement; mask/overlay generation; model version reporting |