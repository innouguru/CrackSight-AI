# APPLICATION SPECIFICATION

## Product Overview

**Product Name**: Crack Detection Building Inspection Application

**Objective**: A responsive, public-facing web application that enables building inspection users to upload or capture photographs of building components and receive AI-assisted crack segmentation results. The application is an inspection product, not a model research or evaluation platform.

**Supported Structural Components**: Walls, beams, columns

**Safety Boundary**: The application must not claim to determine structural safety or replace professional structural engineering inspections. All outputs are AI-assisted predictions requiring human review.

## Target Users

- **Guests**: Non-registered users who want to try the application
- **Registered Users**: Users who register and sign in to save inspections and generate reports
- **Building Inspectors**: Ordinary users performing routine building component inspections

## Guest Capabilities

| Capability | Description |
|---|---|
| Try without registration | Full access to analysis without creating an account |
| Upload or capture photographs | Support JPEG, PNG, WebP formats |
| Analyse photographs | AI-assisted crack segmentation on uploaded images |
| View results | Original image, predicted mask, overlay, pixel measurements |
| Download results | Individual analysis results as files |
| Analysis limit | Maximum 3 photo analyses per guest session |
| Save inspections | Not available |
| Inspection history | Not available |
| Guest data expiration | 24 hours after creation |

## Registered User Capabilities

| Capability | Description |
|---|---|
| Register and sign in | Email/password or Google sign-in |
| Create inspections | New inspection creation with title and required info |
| Save inspections | Inspection records persist beyond 24 hours |
| Inspection history | Access saved inspections through dashboard |
| Generate PDF reports | Professional branded inspection reports |
| Monthly analysis allowance | Configurable, generous limit with fair-use protection |
| Unsaved analyses expiration | 24 hours |

## Guest vs Registered Transfer

Guest results cannot be transferred into a registered account. Users who register must re-upload and re-analyse their photographs to create saved inspections.

## User Workflows

### Workflow 1: Analyse First, Then Save

1. User uploads or captures a photograph
2. System runs AI crack segmentation analysis
3. User views results (original, mask, overlay, measurements)
4. User creates a new inspection with the analysed photograph
5. User adds structure type, observation, verification status
6. User saves the inspection

### Workflow 2: Create Inspection First, Then Analyse

1. User creates a new inspection with title (draft status)
2. User adds photographs to the inspection
3. For each photograph, system runs analysis
4. User adds structure type, observation, verification status
5. User saves results
6. User manually marks inspection as Completed when finished

## Functional Requirements

### Inspection Management

#### Required Inspection Information
- Inspection title (required)
- At least one photograph when inspecting
- Structure type for each photograph: wall, beam, or column (required)

#### Optional Inspection Information
- Building type
- Building location
- Inspection notes
- Inspection date (recorded automatically)

#### Per-Photograph Display
- Original photograph
- Predicted crack mask
- Overlay of predicted mask on original photograph
- Prediction information
- Model version
- Pixel measurements where available

#### Per-Photograph User Input
- Structure type (wall, beam, column)
- Observation text field (one per photograph)
- Verification status:
  - Correct detection
  - Incorrect detection
  - Partially correct
  - Not verified

#### Lifecycle Statuses
- **Draft**: Editable inspection (default)
- **Completed**: Read-only inspection, must be reopened to Draft before editing

**Note**: Only two statuses exist. Do not introduce additional workflow statuses without strong justification.

### Inspection Lifecycle Actions

Users can:

| Action | Description |
|---|---|
| Create inspections | New inspection creation |
| Edit draft inspections | Modify title, photos, observations, verification |
| Add photographs | Add new photos to draft inspection |
| Remove photographs | Remove photos from draft inspection |
| Change structure types | Update structure type per photo |
| Add/edit observations | Edit per-photograph observation text |
| Change verification statuses | Update per-photograph verification status |
| Reanalyse photographs | Re-run analysis on existing photograph |
| View previous predictions | Preserve previous predictions during reanalysis |
| Delete inspections | Delete inspection and all associated data |

### Reanalysis Behavior

When a photograph is reanalysed:
- Previous predictions are preserved as separate versions
- New prediction becomes the current/default view
- Users can compare versions if needed
- No silent overwriting of previous results

### Deletion Behavior

Deleting an inspection removes:
- Database records (inspection, photographs, observations, verification statuses)
- Associated original images from storage
- Associated masks from storage
- Associated overlays from storage
- Associated reports from storage

Partial failures must be documented and handled appropriately.

## Image Analysis Experience

### Supported Image Formats
- JPEG
- PNG
- WebP

### Image Processing
- Uploading
- Preparing image
- Running crack detection
- Generating results
- Complete

### Batch Processing
- Multiple-photo batch submission supported
- Each photograph processed independently
- Failed photographs can be retried individually
- Successful results retained even if some fail
- Users may cancel pending photographs or remaining batch work
- Completed results must be retained

### Progress Display
- Show actual processing stages (listed above)
- Do not display fabricated percentage progress

### Preview and Retake
- Smartphone camera capture supported
- Preview image before analysis
- Retake before final analysis

### Image Handling
- Configurable file-size and image-dimension limits
- Reject unsupported, corrupt, or invalid files
- Large images resized for inference; original photograph preserved
- Preprocessing matches existing trained model exactly

## Dashboard and History

### Dashboard
- Total inspections count
- Total photographs analysed count
- Recent inspections list
- New Inspection button

### Inspection History
- List view
- Card view

### Filtering
- Search by inspection title
- Date filtering
- Structure-type filtering (wall, beam, column)
- Verification-status filtering

## Inspection Details

### Inspection Details Page Contents
- Inspection and building information
- All photographs in the inspection
- Structure type per photograph
- Original, mask, and overlay views
- Pixel measurements per photograph
- Model version
- Inspector observation per photograph
- Verification status per photograph
- Prediction history (versioning)
- Individual result downloads (original, mask, overlay, summary)
- Edit and delete controls where appropriate
- Full PDF report download

### AI vs Inspector Distinction
- AI-generated predictions clearly distinguished from inspector-recorded observations
- Observations are manual text fields entered by the inspector
- Predictions are model outputs requiring verification

## Reports and Downloads

### PDF Inspection Report Contents
- Application branding
- Report ID and generation date
- Inspection and building information
- Summary of photographs analysed
- Original photographs and predicted overlays
- Available pixel measurements
- Model version
- Inspector observations
- Verification statuses
- Limitations and safety disclaimer
- Page numbers

### Report Constraints
- Professional, branded design
- Downloadable file only
- No public shareable report links
- No engineering recommendations
- No structural safety conclusions
- No AI vs observation confusion (clearly distinguished)

### Individual Photograph Result Downloads
- Original photograph
- Predicted mask
- Overlay
- Small analysis summary

## Usage Limits

### Guest Limits
- Maximum 3 photo analyses per guest session
- Guest results expire after 24 hours
- Cannot save inspections or access history

### Registered User Limits
- Configurable, generous monthly analysis allowance
- Fair-use protection
- Unsaved analyses expire after 24 hours
- Saved inspections remain until user deletes them

## Privacy and Retention Expectations

### Guest Files
- Stored in Cloudflare R2
- Expire automatically after 24 hours
- Must not be publicly accessible
- Isolated by guest session
- Abandoned uploads and failed analyses cleaned up

### Registered User Files
- Saved inspection files remain until user deletes inspection
- Temporary unsaved analyses expire after 24 hours
- Explicit user choice on which photographs/results to save

### Storage Security
- Secure storage access required
- Object ownership enforced in backend
- Cleanup for partial failures documented

## Non-Functional Requirements

### Interface
- Responsive: works on desktop, tablet, mobile
- Support photograph upload and smartphone camera capture

### Performance
- Batch processing with individual failure handling
- Cancellation support for pending work
- Processing stages displayed (not fabricated percentages)

### Error Handling
- Reject unsupported, corrupt, or invalid files
- Retry failed photographs individually
- Retain successful results when some fail

### Image Constraints
- Configurable file-size limits
- Configurable image-dimension limits
- Original photograph preserved after inference resizing
- Preprocessing matches existing trained model

## Product Exclusions

The following are NOT included in the initial version:

| Exclusion | Reason |
|---|---|
| Model evaluation workspace | Not an inspection product feature |
| Reference-mask uploads | Not needed for inspection workflow |
| CSV research exports | Not an inspection product feature |
| Manual segmentation-mask correction | Out of scope for initial version |
| Physical crack measurement or calibration | Out of scope |
| Structural safety certification | Not permitted by safety boundary |
| Engineering recommendations | Not permitted by safety boundary |
| Organization-level multi-user collaboration | Out of scope |
| Publicly shareable report links | Privacy/security concern |
| Complex inspection workflow states | Keep lifecycle simple |

## Acceptance Criteria

### Core Functionality
1. Guest user can upload photograph, run analysis, and view results without registration
2. Guest user limited to 3 analyses per session
3. Registered user can register/sign in with email/password or Google
4. Registered user can create, edit, and delete draft inspections
5. Inspection lifecycle follows Draft → Completed with Completed being read-only
6. Each photograph shows original, mask, overlay, pixel measurements, model version
7. Per-photograph observation text field available
8. Verification status settable per photograph (Correct, Incorrect, Partially correct, Not verified)
9. Reanalysis preserves previous predictions as versions
10. Deleting inspection removes all associated data

### Reports
11. PDF report generated with branding, report ID, date, inspection info, photos, measurements, model version, observations, verification statuses, disclaimer, page numbers
12. Individual photograph results downloadable as original, mask, overlay, and summary

### Accessibility
13. Application works on desktop, tablet, and mobile
14. Smartphone camera capture supported
15. Batch upload supported with independent per-photo processing

### Exclusions Verification
16. No manual mask editing provided
17. No physical measurements (mm/cm) reported
18. No structural safety conclusions
19. No public shareable report links
20. No model evaluation workspace

### Existing Work Preservation
21. Existing inference pipeline (`src/crack_detection/inference.py`) reused without modification
22. Existing model checkpoint preserved unchanged
23. Existing test suite passes unchanged
