# CURRENT STATE — Implementation Snapshot

**Last updated:** 2026-11-02

## Implemented and Verified

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

### Frontend UX prototype — implemented and verified
- Standalone React + TypeScript + Vite app is under `frontend/`.
- Responsive design system and component patterns are documented in `docs/ui_ux_design.md`.
- Routes cover landing, sign-in/up placeholders, guest upload/results, dashboard, history, inspection create/details, report preview, access-denied, and not-found screens.
- Sample input/output assets are in `frontend/public/demo/`; the prediction images are static sample outputs.
- Prototype interactions are local-only: selected images are previewed in the browser, inspection state and guest allowance are held in React memory, and no backend/API/auth/inference/report operation is called.
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
- Mock data remains isolated in `src/data/mockData.ts` for features not yet connected to the backend (Milestones 7–10).

## Not Yet Implemented

- Full registered-user inspection management with persistence (Milestone 8).
- Dashboard/history backed by real user data (Milestone 9).
- PDF report generation/download (Milestone 10).
- Deployment (Milestone 12).

## Not Yet Implemented

- Production frontend API integration and persistent inspection data.
- Clerk React SDK sign-in/up and Google OAuth flows.
- Real guest-session creation/validation and backend-enforced allowance/expiry in the browser.
- Production upload/batch/camera flow connected to FastAPI.
- Backend-driven loading/retry/error states and user-owned dashboard/history data.
- Production PDF report generation/download.
- Deployment and real external-service configuration.

## Known Open Issues

- Inference checkpoint must be supplied to a deployment environment; it must not be committed.
- Inference hosting remains unresolved and requires CPU benchmarking before selection.
- Backend upload file-size/dimension limits still need a configured source of truth; the prototype's 10 MB cap is only a local UX example.
- External Neon, R2, and Clerk integrations are not configured for production validation.
- Backend integration tests have previously timed out when run together due to a shared session-scoped database connection; see prior task history.

## Project Constraints

- Preserve model architecture, training code, datasets, and checkpoints.
- Keep inference behind FastAPI; never load the checkpoint in browser code.
- The app is an inspection aid, not a structural safety assessment.
- Measurements are pixel-space only; no physical calibration or engineering conclusions.
- Preserve the two inspection statuses: Draft and Completed.
