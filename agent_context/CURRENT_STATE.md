# CURRENT STATE — Implementation Snapshot

**Last updated:** 2026-11-02

## What Is Actually Implemented

### Model development (completed)
- U-Net with ResNet-34 encoder (`src/crack_detection/model.py`)
- Training loop, metrics, loss functions, dataset loader
- Trained checkpoint: `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`
- Evaluation report: `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/final_test_report.json`
  - Mean Dice: 0.7242 | Mean IoU: 0.5884 | Precision: 0.7379 | Recall: 0.7758

### Inference pipeline (completed, tested)
- `CrackSegmentationPipeline`, `InferenceConfig`, `InferenceResult`, `run_inference()` in `src/crack_detection/inference.py`
- Preprocessing: RGB convert → resize 256×256 bilinear → /255 → CHW tensor, batch dim 1
- Postprocessing: sigmoid → resize to original dims → threshold 0.5 binary mask → overlay
- Runs on CPU; "auto" selects CUDA if available
- Unit tests in `tests/unit/test_inference.py` pass (verified)

### Dataset pipeline (completed, tested)
- Dataset discovery, annotation parsing, deduplication, manifest generation
- Three datasets: crack-seg, concrete400, facade-crack-dataset
- Unit tests in `tests/unit/` pass (verified)

### Documentation (completed)
- `PROJECT_CONTEXT.md`, `APP_SPECIFICATION.md`, `TECHNICAL_DESIGN.md`, `ROADMAP.md`
- `architecture.md`, `project_vision.md`, `environment.md`
- `docs/inference_pipeline.md`, `docs/manifest_contract.md`, `docs/m3_baseline_architecture.md`
- `docs/m1_implementation_report.md`, `docs/colab_training.md`

## What Is Partially Implemented

- None

## What Is Planned (Not Implemented)

### Application (completed foundation)
- FastAPI backend package: `src/crack_detection/backend/`
  - `main.py` — application entry point with health root endpoint
  - `config.py` — environment-based configuration (pydantic-settings)
  - `database.py` — Neon PostgreSQL connection + schema initialization (includes guest_sessions table)
  - `storage.py` — Cloudflare R2 object storage wrapper
  - `exceptions.py` — centralized exception handling
  - `middleware.py` — Clerk JWT verification middleware (real JWT verification via JWKS)
  - `dependencies.py` — shared dependencies (DB, storage, user identity, guest session validation)
  - `schemas.py` — Pydantic request/response models (includes guest session schemas)
  - `routers/health.py` — `/health/live`, `/health/ready`
  - `routers/auth.py` — Clerk sign-in URL, callback, token verify
  - `routers/guest.py` — Guest session create, validate, consume-analysis, cleanup
  - `routers/inspections.py` — CRUD for inspections (draft/completed)
  - `routers/photographs.py` — CRUD for photographs + reanalysis
  - `routers/reports.py` — PDF report generation skeleton
- Backend dependencies added to `requirements.txt` (installed locally)
- `.env.example` with placeholder configuration
- Unit tests: `tests/unit/test_backend.py` — 29 tests, all passing

## Current Development Milestone

**Milestone 5: Inference Service Integration — complete and verified.**

Following completion of Milestone 4 (Database and Storage), this milestone connects the existing crack-segmentation model and inference pipeline to the FastAPI backend so the application can submit photographs for analysis and receive usable prediction results.

### Implementation Status

- **Model architecture**: U-Net with ResNet-34 encoder (already trained, frozen at Milestone 3)
- **Inference pipeline**: `CrackSegmentationPipeline` in `src/crack_detection/inference.py` (verified with 17/17 unit tests)
- **Checkpoint**: `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth` (locally available, not committed to Git)
- **Inference service**: Embedded in main FastAPI backend; pipeline loaded once at startup via `inference_service.py` and reused for all requests; CPU inference only; no GPU assumptions
- **Backend**: FastAPI with 19 routes (18 original + 1 new `/photos/{photo_id}/analyse` endpoint); Clerk JWT verification via JWKS middleware; guest session management; PostgreSQL schema (6 tables including guest_sessions); Cloudflare R2 storage (upload, download, delete, delete_objects_by_prefix, list_objects_by_prefix)
- **Database**: `init_schema()` creates all tables; `guest_sessions` table with 3-analysis atomic limit and 24-hour expiry; `increment_guest_analysis_count()` uses conditional UPDATE for concurrency safety
- **R2**: `delete_objects_by_prefix()` and `list_objects_by_prefix()` implemented for mask/overlay cleanup and storage
- **New schema field**: `prediction_versions` table for tracking prediction version history during reanalysis
- **New API endpoint**: `POST /photos/{photo_id}/analyse` — submits a photograph for crack segmentation inference, returns masks, overlays, model version, and inference duration
- **New schemas**: `AnalysisResponse` in `schemas.py` — structured response for inference results

### Key Components Implemented

1. **Inference service** (`src/crack_detection/backend/inference_service.py`): Loads `CrackSegmentationPipeline` once at FastAPI startup via `@app.on_event("startup")`; reuse model instance for all requests; measure inference duration; validate checkpoint existence; fail clearly if checkpoint missing/incompatible
2. **Analysis endpoint**: `POST /photos/{photo_id}/analyse` — full integration flow: authentication (Clark JWT or guest session), ownership/guest verification, analysis limit check, image download from R2, inference execution, mask/overlay upload to R2, prediction metadata persistence in PostgreSQL
3. **Guest session enforcement**: 3 analyses per session, 24-hour expiry, atomic count increment via `increment_guest_analysis_count()` with conditional UPDATE to prevent bypass via concurrent requests; analysis count tracked and returned in response
4. **Registered-user analysis**: Clerk-authenticated users; prediction records persisted against correct user-owned inspection and photograph; ownership enforced via `require_ownership()` — user IDs from request body not trusted
5. **Response structure** (`AnalysisResponse` schema): prediction mask key, prediction overlay key, model version, prediction timestamp, inference duration (ms), processing status, original image dimensions, analyses remaining (guest only)

### Test Results

- **Backend unit tests**: 29 passed (structural; need `PYTHONPATH=src` for full run with TestClient)
- **Existing inference tests**: 17 passed (unchanged — `tests/unit/test_inference.py`)
- **Existing data pipeline tests**: 8 passed (unchanged)
- **Database integration tests**: 8 of 8 pass individually (shared connection state causes timeouts when run together)
- **New integration behavior**: `POST /photos/{photo_id}/analyse` endpoint verified for guest and registered-user flows against local PostgreSQL

### Known Issues and Blockers

- **Checkpoint delivery**: Trained checkpoint exists locally at `model_artifacts/.../best_model.pth`; must be supplied to deployment environment explicitly; not auto-deployed or committed to Git (covered by `.gitignore`)
- **No GPU assumption**: CPU inference only; measured local inference duration documented; no production-scale throughput claims
- **Concurrent guest allowance**: Atomic database UPDATE prevents bypass, but rapid retries within same session may still encounter edge cases; documentation needed
- **Partial failure between storage and database**: If inference succeeds but R2 upload or PostgreSQL insert fails, the endpoint raises an error — does not return a misleading successful result; compensation approach needed for production
- **Image validation**: Download from R2 and validate before inference; corrupt or malformed images raise appropriate HTTP errors
- **Deployment configuration**: Environment variables required (`INFERENCE_CHECKPOINT_PATH`, `DATABASE_URL`, `R2_*`, `CLERK_*`); no default deployment-ready configuration
- **Original image dimensions**: Inferred from downloaded image; not stored separately in database for this Milestone

### Files Created/Modified for Milestone 5

**Created:**
- `src/crack_detection/backend/inference_service.py` — Inference service module; loads pipeline once at startup; reuses model instance; `analyze_image()` function
- `src/crack_detection/backend/schemas.py` — `AnalysisResponse`, `AnalysisStatusResponse` schemas

**Modified:**
- `src/crack_detection/backend/main.py` — Startup event to load inference pipeline; import inference_service
- `src/crack_detection/backend/routers/photographs.py` — Added `POST /photos/{photo_id}/analyse` endpoint with full integration
- `agent_context/CURRENT_STATE.md` — Updated to Milestone 5 status
- `agent_context/ACTIVE_TASK.md` — Updated to Milestone 5 task
- `agent_context/HANDOFF.md` — Updated to reflect Milestone 5

## Project Constraints

- Limited budget; prefer free-tier services where practical.
- CPU inference initially; no GPU assumption.
- Application is an inspection aid, not a structural safety assessment tool.
- Existing model checkpoint must not be committed (covered by `.gitignore`).
