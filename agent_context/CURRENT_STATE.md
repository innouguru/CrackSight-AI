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

**Pre-Milestone 6 UI/UX direction and browser prototype: complete.**

The prototype is a design-review deliverable, not completion of formal Milestone 6. The next milestone is production frontend foundation and integration with the existing backend and Clerk architecture.

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
- Guest-session cleanup automation and partial failures spanning storage/database need production hardening.
- External Neon, R2, and Clerk integrations are not configured for production validation.
- Backend integration tests have previously timed out when run together due to a shared session-scoped database connection; see prior task history.

## Project Constraints

- Preserve model architecture, training code, datasets, and checkpoints.
- Keep inference behind FastAPI; never load the checkpoint in browser code.
- The app is an inspection aid, not a structural safety assessment.
- Measurements are pixel-space only; no physical calibration or engineering conclusions.
- Preserve the two inspection statuses: Draft and Completed.
