# TECHNICAL DESIGN

## System Architecture

### Three-Tier Architecture

**Frontend** (React/TypeScript):
- Responsive web interface
- Communicates with Main Backend via HTTPS API
- Handles user interactions, image preview, camera capture
- Renders inspection views, dashboard, PDF report display

**Main Backend** (Python FastAPI):
- Entry point for all user requests
- Handles authentication verification (Clerk tokens)
- Manages inspection lifecycle
- Manages image upload, storage to R2, inference job orchestration
- Generates PDF inspection reports
- Enforces ownership checks

**Inference Service** (Private inference API):
- Separate service loading the trained U-Net ResNet-34 model
- Performs crack segmentation on demand
- Returns prediction results (original image, probability map, binary mask, overlay)
- CPU-only inference; timeouts and error handling
- Not directly exposed to end users

### Component Responsibilities

| Component | Responsibility |
|---|---|
| **Frontend** | User interface, image preview, camera capture, display of results, report rendering |
| **Main Backend** | API endpoints, auth integration, inspection CRUD, storage coordination, PDF generation |
| **Inference Service** | Model loading, crack segmentation, prediction output generation |
| **Neon PostgreSQL** | Application records (inspections, photos, observations, verification statuses, ownership) |
| **Cloudflare R2** | Object storage for images, masks, overlays, temporary guest files, PDF reports |

### Frontend ↔ Backend ↔ Inference Service Boundaries

**Frontend → Main Backend**:
- HTTPS REST API
- All user authentication flows
- Inspection creation/modification requests
- Image upload and analysis requests
- Report download requests

**Main Backend → Inference Service**:
- Private/internal API (not user-facing)
- Single-image inference requests (image data → prediction results)
- No direct user access to the inference service
- Token-based or internal communication

**Main Backend → Neon PostgreSQL**:
- All application data records
- Ownership associations
- Query and update inspection records

**Main Backend → Cloudflare R2**:
- Store and retrieve original images
- Store prediction results (masks, overlays)
- Temporary guest session files
- PDF report storage

### API Communication

#### Main Backend API Endpoints (design)

**Authentication** (`/auth`):
- `GET /auth/sign-in-url` - Generate Clerk sign-in URL
- `GET /auth/callback` - Clerk OAuth callback handler
- `POST /auth/verify` - Verify Clerk token

**Inspections** (`/inspections`):
- `POST /inspections` - Create new inspection
- `GET /inspections` - List inspections with filtering
- `GET /inspections/{id}` - Get inspection details
- `PATCH /inspections/{id}` - Edit draft inspection
- `POST /inspections/{id}/complete` - Mark as Completed
- `DELETE /inspections/{id}` - Delete inspection

**Photographs** (`/inspections/{id}/photos`):
- `POST /photos` - Upload/analyse photograph
- `GET /photos/{photo_id}` - Get photograph details
- `PATCH /photos/{photo_id}` - Update observation/verification status
- `DELETE /photos/{photo_id}` - Remove photograph
- `POST /photos/{photo_id}/reanalyse` - Re-run analysis

**Reports** (`/reports`):
- `POST /reports/generate` - Generate PDF report
- `GET /reports/{id}` - Download PDF report

#### Main Backend → Inference Service Request

Request format:
```json
{
  "image_path": "r2://bucket/key.jpg",  // or image data in body
  "config": {
    "checkpoint_path": "...",
    "image_size": [256, 256],
    "threshold": 0.5,
    "device": "cpu"
  }
}
```

Response format:
```json
{
  "original_image": "...",
  "probability_map": "...",
  "binary_mask": "...",
  "overlay": "...",
  "model_version": "...",
  "inference_time": ...
}
```

### Authentication and Authorization

**Clerk Integration**:
- Email/password and Google sign-in
- Clerk tokens verified by FastAPI backend
- Backend sets user session after token verification

**Ownership Checks**:
- Neon PostgreSQL stores ownership associations (user_id ↔ inspection ↔ photograph)
- Every inspection/photo read/write operation checks user ownership
- Guest sessions isolated by session token (not user account)
- R2 object keys isolated by guest session or user ID

**Access Control Matrix**:

| Action | Guest | Registered User |
|---|---|---|
| Upload photo and analyse | ✓ (3 limit) | ✓ |
| View own results | ✓ (24h) | ✓ |
| Save inspection | ✗ | ✓ |
| Generate PDF report | ✗ | ✓ |
| Edit/delete own inspections | ✗ | ✓ |
| Edit/delete others' inspections | ✗ | ✗ |
| Access dashboard/history | ✗ | ✓ |
| Cancel pending batch work | ✓ | ✓ |

### Database Design (Neon PostgreSQL)

#### Proposed Entities and Relationships

**Users** (from Clerk integration):
- `id` (PK, string)
- `email` (string, unique)
- `created_at` (timestamp)
- `role` (enum: 'guest', 'registered')

**Inspections**:
- `id` (PK, string, UUID)
- `user_id` (FK → users.id, nullable for guests)
- `title` (string, required)
- `building_type` (string, optional)
- `building_location` (string, optional)
- `notes` (text, optional)
- `status` (enum: 'draft', 'completed', default 'draft')
- `created_at` (timestamp, default now())
- `completed_at` (timestamp, nullable)

**Photographs**:
- `id` (PK, string, UUID)
- `inspection_id` (FK → inspections.id, cascade delete)
- `user_id` (FK → users.id, nullable for guests)
- `structure_type` (enum: 'wall', 'beam', 'column', required)
- `observation` (text, optional)
- `verification_status` (enum: 'correct', 'incorrect', 'partial', 'not_verified', default 'not_verified')
- `original_image_key` (string, R2 object key)
- `prediction_mask_key` (string, R2 object key, nullable)
- `prediction_overlay_key` (string, R2 object key, nullable)
- `model_version` (string, e.g. 'm3_baseline_b1')
- `prediction_timestamp` (timestamp, nullable)
- `pixel_measurements` (jsonb, nullable)
- `created_at` (timestamp, default now())

**Prediction_Versions** (for reanalysis versioning):
- `id` (PK, string, UUID)
- `photograph_id` (FK → photographs.id)
- `version_number` (integer, sequential)
- `original_image_key` (string, R2 object key)
- `probability_map_key` (string, R2 object key)
- `binary_mask_key` (string, R2 object key)
- `overlay_key` (string, R2 object key)
- `model_version` (string)
- `prediction_timestamp` (timestamp, default now())
- `pixel_measurements` (jsonb, nullable)

**Reports**:
- `id` (PK, string, UUID)
- `inspection_id` (FK → inspections.id)
- `user_id` (FK → users.id)
- `report_pdf_key` (string, R2 object key)
- `generated_at` (timestamp, default now())
- `page_count` (integer, nullable)

### Relationship Diagram

```
Users (1) -- (*) Inspections
Inspections (1) -- (*) Photographs
Photographs (1) -- (*) Prediction_Versions
Inspections (1) -- (*) Reports
```

Key Constraints:
- `ON DELETE CASCADE` on inspection → photographs → prediction_versions
- Ownership check: `user_id` must match authenticated user or guest session token
- Guest `user_id` null, but isolated by session token

### Object Storage Design (Cloudflare R2)

#### R2 Key Structure

**Inspection Reports**: `reports/{report_id}.pdf`

**Photographs**: `inspections/{inspection_id}/originals/{photo_id}.jpg`

**Masks**: `inspections/{inspection_id}/masks/{photo_id}_{verification_status}.png`

**Overlays**: `inspections/{inspection_id}/overlays/{photo_id}_{verification_status}.png`

**Guest Session Files**: `guest/{session_token}/{file_type}/{original_name}`

#### Temporary File Lifecycle

| File Type | Storage Location | Expiration |
|---|---|---|
| Guest uploads | `guest/{session_token}/` | 24 hours after creation |
| Guest analysis results | `guest/{session_token}/analysis/` | 24 hours after creation |
| Unsaved registered user analyses | Temporary, R2 path | 24 hours after last interaction |
| Saved inspection photos/results | `inspections/{inspection_id}/` | Permanent until inspection delete |
| PDF reports | `reports/{report_id}.pdf` | Permanent until user deletes |

#### Cleanup Procedures

1. **Guest session cleanup**: Background task or on-login cleanup of sessions > 24 hours old
2. **Unsaved analysis cleanup**: On user sign-in, cleanup any temporary files older than 24 hours
3. **Inspection deletion**: Delete R2 objects matching key patterns for that inspection
4. **Partial failure handling**: If inspection deletion partially fails, log error and retain what can be cleaned up

### Inference Integration

#### Inference Service Design

**Service Interface**:
- POST `/predict` - Single image inference
- GET `/health` - Health check endpoint
- Configuration for checkpoint path, device, thresholds

**Model Loading**:
- Loads `UNetResNet34` architecture from `src/crack_detection/model.py`
- Loads checkpoint weights from `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`
- Runs on CPU exclusively
- Model kept in `eval()` mode

**Preprocessing** (matches existing pipeline exactly):
1. PIL `Image.open(...).convert("RGB")`
2. Resize to 256×256 with bilinear resampling
3. Convert to CHW tensor, scale to [0,1] by /255.0
4. Add batch dimension

**Postprocessing**:
1. Sigmoid on logits
2. Resize probability map back to original dimensions (bilinear)
3. Binary mask at configurable threshold (default 0.5)
4. Overlay with red highlight (alpha=0.45)

**Error Handling**:
- Missing checkpoint: `FileNotFoundError`
- Invalid image: `ValueError`
- Missing image file: `FileNotFoundError`
- Invalid device hint: `ValueError`
- CUDA unavailable: `RuntimeError` (but service runs CPU-only)
- Timeout handling for long-running inferences

#### Batch Processing and Job Lifecycle

**Batch Job Flow**:
1. User uploads multiple photographs
2. Backend creates batch job record in PostgreSQL
3. Each photograph processed independently:
   - Image prepared
   - Inference request sent to inference service
   - Results stored to R2
   - Status updated in PostgreSQL
4. If some photographs fail:
   - Successful results retained
   - Failed photographs marked for retry
   - User can retry individual failed photographs
5. Users may cancel pending work
6. Completed results retained even if some fail

**Job Lifecycle States**:
- `pending`: Waiting in queue
- `processing`: Inference in progress
- `complete`: All photographs processed
- `partial`: Some succeeded, some failed
- `cancelled`: User cancelled

#### Prediction Versioning

**Versioning Strategy**:
- Each photograph can have multiple prediction versions
- Version 0: Initial analysis
- Version N: Nth reanalysis
- When reanalysis occurs:
  - New version created with incrementing version number
  - Previous versions preserved
  - New version becomes current/default
  - Backend stores all versions in `Prediction_Versions` table

**Backend Behavior**:
- On reanalysis: Create new version record + store new R2 objects
- On view: Default to latest version, but allow version selection
- On download: Download specified version or latest

### PDF Report Generation

#### Report Generation Flow

1. User requests PDF report for inspection
2. Backend retrieves inspection data from PostgreSQL
3. Backend retrieves photograph data (original images, masks, overlays from R2)
4. Backend generates PDF with the following sections:

**PDF Section Layout**:
- **Header**: Application branding, report ID, generation date
- **Inspection Information**: Title, building type, location, date, status
- **Summary**: Count and type of photographs analysed
- **Photograph Pages**: For each photograph:
  - Original photograph
  - Predicted overlay (mask blended on original)
  - Pixel measurements (if available)
  - Model version
  - Inspector observation
  - Verification status
- **Limitations and Safety Disclaimer**: Clear statement that AI predictions ≠ structural safety assessment
- **Footer**: Page numbers

#### Technical Requirements

**Libraries**: ReportLab or WeasyPrint for PDF generation

**Branding**: Application logo, color scheme, professional layout

**Constraints**:
- Downloadable file only (no public shareable links)
- Page numbers included
- Limitations/disclaimer clearly separated from observations
- AI-generated predictions clearly distinguished from inspector-recorded observations

#### Report Content Specifications

| Element | Format |
|---|---|
| Report ID | UUID or sequential ID |
| Generation date | ISO format timestamp |
| Inspection title | As entered by user |
| Building type/location | As entered (optional) |
| Photograph summary | Count + structure types |
| Original photographs | Embedded or thumbnail links |
| Predicted overlays | Rendered with mask transparency |
| Pixel measurements | Image-space pixels only |
| Model version | e.g. "m3_baseline_b1 (ResNet-34 U-Net)" |
| Inspector observations | Text as entered by user |
| Verification statuses | Text labels (correct, incorrect, partial, not_verified) |
| Disclaimer | "AI-assisted predictions require professional structural engineering review. Not a structural safety assessment." |
| Page numbers | Bottom of each page |

### Error Handling

#### Inference Service Errors

| Error Situation | HTTP Response | Backend Handling |
|---|---|---|
| Missing checkpoint | 500 | Return error to user, offer retry |
| Invalid image file | 400 | Show upload error, allow retry |
| Image too large / unsupported | 400 | Reject at upload, inform user |
| Inference timeout | 504 | Mark photograph as failed, allow retry |
| Inference service unavailable | 503 | Queue for retry, inform user |

#### Backend Error Handling

1. **Upload failures**: Reject unsupported/corrupt files, inform user
2. **Inference failures**: Mark photograph as failed, allow individual retry
3. **Storage failures**: Log error, attempt cleanup, inform user
4. **Report generation failures**: Log error, inform user, offer regenerate
5. **Ownership violations**: Return 403, prevent access

#### Error Response Format

```json
{
  "error": " descriptive error title",
  "message": " user-friendly explanation",
  "action": " suggested user action (if any)",
  "retryable": true/false
}
```

### Security and Privacy

#### Authentication Security

- Clerk handles OAuth flow and token management
- Backend verifies Clerk JWT tokens on protected routes
- No password storage (Clerk manages this)
- Session tokens tied to authenticated user

#### Storage Security

- R2 objects not publicly accessible by default
- Object keys include user_id or session_token for isolation
- Backend enforces ownership checks on all read/write operations
- Guest session isolation by unique session token

#### Privacy Expectations

- Guest data expires after 24 hours (automatic cleanup)
- Registered user data retained until deletion
- Inspection data associated with user account
- No sharing of inspection data between users
- PDF reports downloaded privately

#### Data Protection

- Neon PostgreSQL access restricted to backend service
- R2 bucket configured for private access only
- No sensitive data stored in URLs
- All API endpoints require authentication (except guest limited endpoints)

### Testing Strategy

#### Unit Tests

- **Inference pipeline**: Existing `tests/unit/test_inference.py` verified
- **API endpoints**: Test FastAPI route handlers with mock data
- **Database operations**: Test PostgreSQL queries and relationships
- **PDF generation**: Test PDF output structure and content

#### Integration Tests

- **End-to-end workflows**: Guest analysis flow, registered user flow
- **Authentication flows**: Clerk sign-in, token verification
- **Inference integration**: Main backend → inference service requests
- **Report generation**: PDF output verification

#### Test Data

- Synthetic test images for unit tests
- Real inference results from existing model checkpoint
- Mock Clerk tokens for auth tests
- Test fixtures for PostgreSQL entities

#### Acceptance Criteria for Tests

1. All existing unit tests pass unchanged
2. Guest user can complete 3 analyses then session expires
3. Registered user can create, edit, delete inspections
4. PDF reports generate with correct content and structure
5. Reanalysis preserves previous prediction versions
6. Deletion removes all associated data

### Deployment Considerations

#### Free-Tier Service Selection

| Service | Status |
|---|---|
| Neon PostgreSQL | Already selected (free tier) |
| Cloudflare R2 | Already selected (free tier consideration) |
| Clerk | Already selected (free tier) |
| Inference hosting | **Unresolved - requires research** |

#### Inference Hosting (Unresolved)

**Requirements Research Needed**:
- CPU performance benchmarking (typical inference time per image)
- RAM requirements per inference request
- Cold start times (if using serverless)
- Concurrency handling (simultaneous requests)
- Request timeouts (per-image inference duration)
- Free-tier restrictions and cost implications beyond free tier

**Do not assume**: Inference hosting will be free or that a provider's free tier can reliably support persistent CPU inference.

#### Deployment Architecture

```
Production:
- Frontend: Static hosting (Netlify/Vercel free tier)
- Main Backend: FastAPI on cloud platform (Heroku free tier, Railway, or similar)
- Inference Service: Separate service (details TBD from benchmarking)
- Database: Neon PostgreSQL
- Storage: Cloudflare R2

Development:
- Local development with venv (Python 3.12.5)
- Inference service runs locally using existing pipeline
- Environment variables for configuration
```

#### Cost Constraints

- **Very limited budget**: Prefer free-tier services
- **Neon PostgreSQL**: Already selected, within free tier
- **Cloudflare R2**: Within free tier limits for object storage
- **Clerk**: Free tier sufficient for email/password + Google
- **Inference hosting**: Research required; cannot assume free tier suffices
- **Frontend hosting**: Static site, free tier expected

### Unresolved Technical Decisions

| Decision | Status | Notes |
|---|---|---|
| Inference service hosting provider | **Unresolved** | Requires benchmarking of CPU performance, cold starts, concurrency, free-tier restrictions |
| Maximum file size/dimension limits | **Unresolved** | Configurable; needs testing with real photographs |
| PDF report branding details | **Unresolved** | To be determined with application visual design |
| Monthly analysis allowance for registered users | **Unresolved** | Configurable; balance generosity vs cost |
| Batch processing concurrency limits | **Unresolved** | Depends on inference service capacity |
| Guest session token expiration mechanism | **Unresolved** | 24 hours; implementation approach TBD |
| Report generation library (ReportLab vs WeasyPrint) | **Unresolved** | Both viable; choose based on licensing/cost |
| Frontend hosting platform | **Unresolved** | Netlify vs Vercel vs self-hosted |
| Real-time camera capture flow | **Unresolved** | Mobile browser API compatibility |

**Important**: Do not make assumptions about any of the above. Document as unresolved and research during implementation phase.