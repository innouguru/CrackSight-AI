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

**Main Deliverables**:
- Registered user inspection creation with title
- Add photographs to inspection (structure type per photo)
- Save inspection results (persist beyond 24 hours)
- Inspection dashboard and history
- Monthly analysis allowance with fair-use protection
- Generate and download professional PDF inspection reports
- View inspection history (list and card views)
- Filtering by title, date, structure type, verification status

**Dependencies**:
- Authentication (Milestone 3) complete
- Guest workflow (Milestone 7) complete
- Backend inspection management (Milestone 2+3) complete
- PDF report generation capability

**Acceptance Criteria**:
- [ ] Registered user can create inspection with title
- [ ] User can add photographs with structure type (wall/beam/column)
- [ ] Inspection saves and persists beyond guest session
- [ ] Dashboard shows total inspections, total photographs, and recent inspections from saved data
- [ ] New Inspection button is available in the integrated application
- [ ] PDF report generates with required content (branding, ID, date, photos, measurements, model version, observations, verification statuses, disclaimer, page numbers)
- [ ] PDF is a downloadable file only (no public shareable links)
- [ ] History supports list and card views backed by saved inspections
- [ ] Search by title, date, structure type, and verification status works against saved data
- [ ] Monthly allowance with fair-use protection is connected to backend enforcement

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
- Registered-user inspections (Milestone 8) partially complete

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

**Progress**: Milestones 1–5 complete; pre-Milestone 6 design prototype complete; formal Milestone 6 and later milestones remain pending.

**Critical Path**:
1. Documentation (Milestone 1) → Backend foundation (Milestone 2) → Auth (Milestone 3) → Database/storage (Milestone 4) → Inference integration (Milestone 5) → Frontend (Milestone 6) → Guest workflow (Milestone 7) → Registered inspections (Milestone 8) → Dashboard/history (Milestone 9) → PDF reports (Milestone 10) → Testing/security (Milestone 11) → Deployment (Milestone 12) → Validation (Milestone 13)

**Budget Constraints**: Very limited budget throughout; prefer free-tier services; inference hosting requires research and benchmarking (unresolved decision).

**Key Unresolved Decisions** (carried through roadmap):
- Inference service hosting provider and cost
- Maximum file size/dimension limits
- PDF report branding details
- Monthly analysis allowance
- Batch processing concurrency
- Guest session management approach
- Frontend hosting platform
- Report generation library choice

**Dependencies Between Milestones**: Each milestone depends on completion of preceding infrastructure milestones. Milestone 1 (documentation) has no dependencies and can proceed immediately.